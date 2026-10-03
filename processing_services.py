"""Dashboard-owned local service lifecycle; no downloads and no shell endpoint."""
import importlib.util, json, logging, logging.handlers, os, socket, subprocess, threading, time
from pathlib import Path
from standalone import config, renderer_address, workflow_requirements

class Services:
    def __init__(self,engine,directory):
        self.engine=engine;self.directory=Path(directory);self.directory.mkdir(parents=True,exist_ok=True)
        self.lock=threading.RLock();self.process=None;self.preparing=False;self.prepared=False
        self.state='Not prepared';self.message='Prepare Studio when you need processing.';self.checks=[]
        self.last_model_kind=None;self.vision_process=None
    def snapshot(self):
        with self.lock:
            connected=self.engine.health().get('connected')
            if self.prepared and not connected:
                self.prepared=False;self.set('Error','Renderer became unavailable. Existing outputs are retained. Retry preparation.')
            active=[j for j in self.engine.store.db['jobs'].values() if j['status'] in ('queued','running','waiting')]
            state='Busy' if active and self.prepared else self.state
            return {'state':state,'message':self.message,'prepared':self.prepared,'ownership':'dashboard' if self.process and self.process.poll() is None else 'external' if connected else 'none','model_residency':'not verified; loaded lazily','checks':self.checks,'active_jobs':len(active)}
    def set(self,state,message):
        with self.lock:self.state=state;self.message=message
    def prepare(self):
        with self.lock:
            if self.preparing:return self.snapshot()
            self.preparing=True;self.prepared=False;self.set('Checking dependencies','Checking installed local components. No downloads.')
            threading.Thread(target=self._prepare,daemon=True,name='studio-prepare').start()
            return self.snapshot()
    def _launch(self,c):
        host,port=renderer_address(self.engine.url)
        with socket.socket() as sock:
            sock.settimeout(.5)
            if sock.connect_ex((host,port))==0:raise ValueError('Configured renderer port is occupied by an incompatible or unresponsive service. No duplicate started.')
        python=Path(c.get('comfy_python',''));root=Path(c.get('comfy_root',''))
        if not python.is_file() or not (root/'main.py').is_file():raise ValueError('Renderer executable or ComfyUI folder is missing. Connect the installed components in Settings.')
        if self.process and self.process.poll() is None:raise ValueError('Owned renderer is still starting. Retry after the startup timeout; no duplicate started.')
        args=[str(python),str(root/'main.py'),'--disable-auto-launch','--disable-api-nodes','--disable-all-custom-nodes','--listen','127.0.0.1','--port',str(port)]
        env=os.environ.copy();env.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_HUB_DISABLE_TELEMETRY='1',DO_NOT_TRACK='1')
        self.process=subprocess.Popen(args,cwd=str(root),env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        (self.directory/'owned-renderer.json').write_text(json.dumps({'pid':self.process.pid,'started':time.time(),'command':args,'note':'Only this live Popen handle may stop the process. After dashboard restart it is treated as external, never killed by PID alone.'},indent=2),encoding='utf-8')
        self._log_process(self.process,'renderer')
    def _log_process(self,proc,name):
        def drain():
            handler=logging.handlers.RotatingFileHandler(self.directory/(name+'.log'),maxBytes=4*1024*1024,backupCount=3,encoding='utf-8')
            try:
                for line in iter(proc.stdout.readline,b''):handler.emit(logging.LogRecord(name,logging.INFO,'',0,line.decode('utf-8','replace').rstrip(),(),None))
            finally:handler.close();proc.stdout.close()
        threading.Thread(target=drain,daemon=True,name=name+'-log').start()
    def _prepare(self):
        try:
            c=config(self.engine.app_root);checks=[]
            for module in ('PIL','numpy','requests','websocket'):
                if not importlib.util.find_spec(module):raise ValueError('Missing Python dependency: '+module+'. Restore the installed runtime in Settings.')
            from engine import available_vram, memory_headroom
            gpu=available_vram()
            if gpu is None:raise ValueError('NVIDIA GPU probe failed. Check the installed driver in Diagnostics.')
            from hardware_status import sample
            checks.append(sample(memory_headroom()[0],gpu))
            self.set('Checking dependencies','Checking configured renderer and workflow.')
            if not self.engine.health(force=True).get('connected'):
                self.set('Starting services','Starting the installed renderer invisibly. Models are not loaded yet.')
                self._launch(c)
                deadline=time.monotonic()+min(180,max(5,int(c.get('startup_timeout',120))))
                while time.monotonic()<deadline and not self.engine.stop.is_set():
                    if self.process.poll() is not None:raise ValueError('Renderer exited during startup. Read renderer.log in Diagnostics, then Retry.')
                    if self.engine.health(force=True).get('connected'):break
                    self.engine.stop.wait(1)
                else:raise ValueError('Renderer startup timed out. Inspect renderer.log; Retry checks the existing process before starting anything.')
            self.set('Checking dependencies','Checking real workflow nodes and registered model files.')
            specs=self.engine.get('/object_info');types,models=workflow_requirements(self.engine.app_root)
            # Video availability is separate; missing video weights must not claim image readiness failed.
            image=json.loads((self.engine.app_root/'templates/flux.json').read_text(encoding='utf-8-sig'))
            required={n['class_type'] for n in image.values()}|{'ImagePadForOutpaint','VAEEncode','ImageCrop','SolidMask','FeatherMask','MaskComposite','SetLatentNoiseMask','ImageCompositeMasked','ReferenceLatent','SplitSigmasDenoise'}
            missing=sorted(required-set(specs))
            for n in image.values():
                for key in ('unet_name','clip_name','vae_name'):
                    if key in n['inputs']:
                        choices=specs.get(n['class_type'],{}).get('input',{}).get('required',{}).get(key,[[]])[0]
                        if not isinstance(choices,list) or n['inputs'][key] not in choices:missing.append(n['inputs'][key])
            if missing:raise ValueError('Image workflow is missing installed components: '+', '.join(missing)+'. Nothing downloaded.')
            video_missing=sorted(types-set(specs))
            for cls,key,name in models:
                choices=specs.get(cls,{}).get('input',{}).get('required',{}).get(key,[[]])[0]
                if not isinstance(choices,list) or name not in choices:video_missing.append(name)
            checks.extend([{'name':'Images','detail':'Required workflow nodes and model filenames available; no inference run.'},{'name':'Video','detail':'Missing: '+', '.join(video_missing) if video_missing else 'Required nodes and model filenames available; generation not tested by readiness.'}])
            self.reader(c,checks)
            self.checks=checks;self.prepared=True;self.set('Ready','Ready — model loads on first generation')
        except Exception as exc:self.prepared=False;self.set('Error',str(exc)[:700])
        finally:
            with self.lock:self.preparing=False
    def reader(self,c,checks):
        url=self.engine.store.db['settings'].get('vision_url','http://127.0.0.1:11434');host,port=renderer_address(url)
        session=self.engine.session
        def probe():
            r=session.get(url+'/api/tags',timeout=2);r.raise_for_status();return r.json()['models']
        try:models=probe()
        except Exception:
            exe=Path(c.get('ollama_executable',''))
            if not exe.is_file():
                checks.append({'name':'Object reader','detail':'Unavailable: connect an installed local reader in Settings. Image generation is available.'});return
            with socket.socket() as sock:
                sock.settimeout(.5)
                if sock.connect_ex((host,port))==0:raise ValueError('Reader port is occupied by an incompatible service. No duplicate started.')
            if self.vision_process and self.vision_process.poll() is None:raise ValueError('Reader is already starting; retry later.')
            env=os.environ.copy();env.update(OLLAMA_HOST=f'{host}:{port}',OLLAMA_MODELS=str(Path(c['comfy_root'])/'models/vision/ollama'),OLLAMA_KEEP_ALIVE='0',OLLAMA_NUM_PARALLEL='1',OLLAMA_NO_CLOUD='1')
            self.vision_process=subprocess.Popen([str(exe),'serve'],cwd=str(exe.parent),env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            self._log_process(self.vision_process,'reader')
            (self.directory/'owned-reader.json').write_text(json.dumps({'pid':self.vision_process.pid,'started':time.time(),'command':[str(exe),'serve']}),encoding='utf-8')
            deadline=time.monotonic()+30
            while time.monotonic()<deadline:
                if self.engine.stop.is_set() or self.vision_process.poll() is not None:raise ValueError('Reader stopped during startup. Inspect reader.log and Retry.')
                try:models=probe();break
                except Exception:self.engine.stop.wait(1)
            else:raise ValueError('Local reader startup timed out. Inspect installed reader configuration; Retry will not start a duplicate.')
        selected=self.engine.store.db['settings'].get('vision_model')
        available=selected in {m['name'] for m in models}
        checks.append({'name':'Object reader','detail':'Selected local model available; loads only for analysis.' if available else 'Selected visual model is missing. Analysis unavailable; no model download attempted.'})
    def reader_ready(self):
        url=self.engine.store.db['settings']['vision_url'];renderer_address(url)
        r=self.engine.session.get(url+'/api/tags',timeout=3);r.raise_for_status();return r.json()
    def idle(self):
        if self.preparing:raise ValueError('Preparation is in progress. Wait for it to finish.')
        if any(j['status'] in ('queued','running','waiting') for j in self.engine.store.db['jobs'].values()):raise ValueError('An activity is active. Finish it, or explicitly cancel it in Activity before stopping services.')
        if self.engine.health(force=True).get('connected'):
            q=self.engine.get('/queue')
            if q['queue_running'] or q['queue_pending']:raise ValueError('Renderer has active work. It was not interrupted.')
    def release(self):
        with self.lock:
            self.idle()
            if not self.process or self.process.poll() is not None:raise ValueError('This renderer is externally owned. Its models were left untouched.')
            self.engine.post('/free',{'unload_models':True,'free_memory':True});self.last_model_kind=None
            self.message='Models released — loads on next generation';return self.snapshot()
    def stop_services(self):
        with self.lock:
            self.idle()
            if not self.process or self.process.poll() is not None:raise ValueError('No dashboard-owned renderer is running. External services were left untouched.')
            if self.vision_process and self.vision_process.poll() is None:
                self.vision_process.terminate();self.vision_process.wait(timeout=15);self.vision_process=None
            self.process.terminate();self.process.wait(timeout=15);self.process=None;self.prepared=False
            self.engine.health_cache={};self.set('Not prepared','Processing renderer stopped. Dashboard and saved projects remain available.');return self.snapshot()
    def before_model(self,job):
        if not self.prepared:raise ValueError('Click Prepare Studio before starting processing.')
        if not self.engine.health(force=True).get('connected'):
            self.prepared=False;self.set('Error','Renderer disconnected. Retry preparation before recovering the job.')
            raise ValueError(self.message)
        if self.process and self.process.poll() is None and self.last_model_kind!=job['kind']:
            q=self.engine.get('/queue')
            if not q['queue_running'] and not q['queue_pending']:self.engine.post('/free',{'unload_models':True,'free_memory':True})
        self.last_model_kind=job['kind']
