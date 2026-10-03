"""Private TLS worker. Run from an immutable deployment with private configuration.

Only built-in FLUX and bounded LTX graphs are accepted. Renderer stays on loopback. Persistent
submission intent is reconciled, never blindly replayed after an uncertain POST.
"""
import copy, hashlib, hmac, io, json, os, ssl, threading, time, uuid
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse
from PIL import Image
from dashboard_access import Access
from background_runtime import InstanceLock
from engine import Engine, memory_headroom
from processing_services import Services
from store import Store
from worker_protocol import contract, digest, validate, ID, video_missing
import render_progress

ACTIVE=('queued','running','waiting','submitting','cancelling')

class WorkerServices(Services):
    def reader(self,c,checks):
        checks.append({'name':'Scope','detail':'FLUX images and bounded LTX video share one renderer queue. No OCR or detection services started.'})

class Worker:
    def __init__(self,root,private,renderer):
        self.root=Path(root);self.private=Path(private);self.private.mkdir(parents=True,exist_ok=True)
        self.store=Store(self.private/'state');self.lock=self.store.lock
        self.store.db['settings']['comfy_url']=renderer
        self.store.db.setdefault('transfers',{});self.store.db.setdefault('worker_paused',False)
        self.engine=Engine(self.store,self.root);self.services=WorkerServices(self.engine,self.private/'logs')
        self.engine.services=self.services;self.stop=self.engine.stop
        self.inputs=self.private/'inputs';self.inputs.mkdir(exist_ok=True)
        self.outputs=self.private/'outputs';self.outputs.mkdir(exist_ok=True)
        self.watchers={}
        self.store.save()
    def snapshot(self):
        d=self.services.snapshot()
        with self.lock:
            return {**d,**contract(self.root),'paused':self.store.db['worker_paused'],
                    'transport':'TLS 1.2+; pinned local certificate; private LAN',
                    'maintenance':self.store.db.get('worker_maintenance',False),
                    'active_jobs':sum(j['status'] in ACTIVE for j in self.store.db['jobs'].values())}
    def upload(self,data):
        if not 0<len(data)<=32*1024*1024:raise ValueError('Input must be at most 32 MB.')
        with Image.open(io.BytesIO(data)) as im:
            if im.format not in ('PNG','JPEG','WEBP') or im.width*im.height>32_000_000:raise ValueError('Use a PNG, JPEG or WebP image of at most 32 megapixels.')
            im.verify()
        aid=hashlib.sha256(data).hexdigest()
        with self.lock:
            if aid in self.store.db['transfers'] and self.store.db['transfers'][aid].get('dimensions'):return {'id':aid}
            p=self.inputs/(aid+'.png')
            # Normalize container; the ID still identifies the exact original bytes.
            with Image.open(io.BytesIO(data)) as im:
                dimensions=list(im.size);im.convert('RGB').save(p)
            name=self.engine.upload(p)
            self.store.db['transfers'][aid]={'comfy_name':name,'sha256':aid,'dimensions':dimensions}
            self.store.save();return {'id':aid}
    def submit(self,body):
        with self.lock:
            key=body.get('id');fingerprint=digest(body)
            old=self.store.db['jobs'].get(key)
            if old:
                if old.get('cancel_before_submission'):return self.job(key)
                if old['request_hash']!=fingerprint:raise ValueError('Job ID already has different inputs. Create a new version instead.')
                return self.job(key)
            if self.store.db.get('worker_maintenance'):raise ValueError('PC worker is in maintenance. Resume after deployment; no job was accepted.')
            graph=validate(self.root,body,self.store.db['transfers'])
            self.engine.validate_graph(graph)
            if body['kind']=='video':
                missing=video_missing(self.root,self.engine.get('/object_info'))
                if missing:raise ValueError('Video components unavailable: '+', '.join(missing))
            job={'id':key,'kind':body['kind'],'status':'queued','stage':'Queued on PC',
                 'created':time.time(),'request_hash':fingerprint,'graph':graph,
                 'output_node':str(body['output_node']),'comfy_id':str(uuid.uuid4()),'attempts':0}
            if body['kind']=='video':job['video_settings']=copy.deepcopy(body['video_settings'])
            self.store.db['jobs'][key]=job;self.store.save();return self.job(key)
    def job(self,jid):
        with self.lock:
            j=self.store.db['jobs'].get(jid)
            if not j:raise ValueError('Worker job not found. No generation was started.')
            return copy.deepcopy({k:v for k,v in j.items() if k not in ('graph','history','request_hash')})
    def action(self,action):
        with self.lock:
            if action=='maintenance':
                if any(j['status'] in ACTIVE for j in self.store.db['jobs'].values()):raise ValueError('Finish or cancel worker jobs before maintenance.')
                self.store.db.update(worker_paused=True,worker_maintenance=True);self.store.save()
            elif action in ('pause','resume'):
                self.store.db['worker_paused']=action=='pause';self.store.save()
                if action=='resume':self.store.db['worker_maintenance']=False;self.store.save()
            elif action=='prepare':self.services.prepare()
            elif action in ('release','stop'):
                if any(j['status'] in ACTIVE for j in self.store.db['jobs'].values()):raise ValueError('Finish or cancel queued worker jobs first.')
                (self.services.release if action=='release' else self.services.stop_services)()
            else:raise ValueError('Unsupported action.')
        return self.snapshot()
    def cancel(self,jid):
        with self.lock:
            if not ID.fullmatch(jid):raise ValueError('Invalid persistent job ID.')
            j=self.store.db['jobs'].get(jid)
            if j is None:
                # A cancellation racing the first submit must win persistently.
                j={'id':jid,'status':'cancelled','stage':'Cancelled before submission','cancel_before_submission':True,'attempts':0,'finished':time.time()}
                self.store.db['jobs'][jid]=j;self.store.save();return self.job(jid)
            if j['status'] not in ACTIVE:return self.job(jid)
            if j.get('submission_intent'):
                self.reconcile(j)
                if j['status'] not in ACTIVE:return self.job(jid)
                if not j.get('prompt_id'):raise ValueError('Submission outcome uncertain. Reconcile before cancelling; no unrelated inference was interrupted.')
                # Installed Comfy supports targeted interrupt; never use a global interrupt.
                self.engine.post('/interrupt',{'prompt_id':j['prompt_id']})
                self.engine.post('/queue',{'delete':[j['prompt_id']]})
                j.update(status='cancelling',stage='Cancellation requested')
            else:j.update(status='cancelled',stage='Cancelled before submission',finished=time.time())
            self.store.save();return self.job(jid)
    def reconcile(self,j):
        pid=j.get('prompt_id') or j['comfy_id']
        history=self.engine.get('/history/'+pid).get(pid)
        if history:
            if history['status']['status_str']!='success':
                j.update(status='cancelled' if j['status']=='cancelling' else 'failed',stage='Renderer stopped',finished=time.time())
            else:
                try:self.collect(j,history)
                except ValueError as exc:j.update(status='failed',stage='Output validation failed; renderer files retained',error=str(exc),finished=time.time())
            self.store.save();return
        q=self.engine.get('/queue')
        rows=q['queue_running']+q['queue_pending']
        matches=[r[1] for r in rows if r[1]==pid or len(r)>3 and r[3].get('pixeloid_worker_job')==j['id']]
        if matches:
            j['prompt_id']=matches[0]
            if j['status']!='cancelling':
                j['status']='running'
                if not j.get('render_tracking',{}).get('last_event'):j['stage']='Running on PC' if any(r[1]==matches[0] for r in q['queue_running']) else 'Queued in renderer'
                self.watch(j)
        elif time.time()-j.get('submission_intent',0)>15:
            j.update(status='cancelled' if j['status']=='cancelling' else 'interrupted',
                     stage='Submission absent from renderer; not rerun',finished=time.time())
        self.store.save()
    def collect(self,j,history):
        result=copy.deepcopy(history);saved={}
        for node,row in result.get('outputs',{}).items():
            for key in ('images','videos','gifs'):
                for entry in row.get(key,[]):
                    # Comfy versions may put SaveVideo entries under images or videos.
                    ext=Path(entry.get('filename','')).suffix.lower()
                    if ext not in ('.png','.jpg','.jpeg','.webp','.mp4'):raise ValueError('Unsupported renderer output container.')
                    if j['kind']=='video' and str(node)==j['output_node'] and ext!='.mp4':raise ValueError('Expected MP4 video output.')
                    r=self.engine.session.get(self.engine.url+'/view',params=entry,timeout=180);r.raise_for_status()
                    raw=r.content
                    if ext=='.mp4' and (len(raw)<12 or raw[4:8]!=b'ftyp'):raise ValueError('Invalid MP4 container; output not marked complete.')
                    aid=hashlib.sha256(raw).hexdigest();p=self.outputs/(aid+ext)
                    temporary=p.with_suffix(ext+'.part');temporary.write_bytes(raw);temporary.replace(p)
                    media_type={'.png':'image/png','.jpg':'image/jpeg','.jpeg':'image/jpeg','.webp':'image/webp','.mp4':'video/mp4'}[ext]
                    saved[aid]={'sha256':aid,'bytes':len(raw),'extension':ext,'content_type':media_type}
                    entry.clear();entry.update(worker_asset=aid,content_type=media_type,bytes=len(raw))
        selected=result.get('outputs',{}).get(j['output_node'],{})
        if not any(selected.get(k) for k in ('images','videos','gifs')):raise ValueError('Renderer returned no requested media output.')
        if j.get('video_settings',{}).get('capture'):
            from video_capture import evidence
            manifest=evidence(result,j['id'])
            if manifest.get('mp4',{}).get('sha256') not in saved:raise ValueError('Capture MP4 checksum differs from collected output.')
            j['capture_summary']={'profile':manifest['profile'],'pc_relative_directory':manifest['pc_relative_directory'],'state':'complete'}
        j.update(status='completed',stage='Ready to retrieve',finished=time.time(),history=result,outputs=saved)
    def output(self,aid):
        if not ID.fullmatch(aid):raise ValueError('Invalid output identity.')
        with self.lock:
            metadata=next((j.get('outputs',{}).get(aid) for j in self.store.db['jobs'].values() if aid in j.get('outputs',{})),None)
            if not metadata:raise ValueError('Output not found.')
            # Original image workers stored PNGs without extension metadata.
            ext=metadata.get('extension','.png')
            if ext not in ('.png','.jpg','.jpeg','.webp','.mp4'):raise ValueError('Invalid output metadata.')
            raw=(self.outputs/(aid+ext)).read_bytes()
            if hashlib.sha256(raw).hexdigest()!=aid:raise ValueError('Stored output checksum mismatch.')
            return raw,metadata.get('content_type','image/png')
    def watch(self,j):
        if self.watchers.get(j['id']) and self.watchers[j['id']].is_alive():return
        ws=self.engine.connect_events(j['id'])
        if not ws:return
        def receive():
            try:
                while not self.stop.is_set() and j['status'] in ACTIVE:
                    try:
                        raw=ws.recv()
                        if isinstance(raw,str):
                            with self.lock:
                                fields=render_progress.event_fields(j,json.loads(raw),j['graph'],time.time())
                                if fields:j.update(fields);self.store.save()
                    except __import__('websocket').WebSocketTimeoutException:continue
                    except Exception:break
            finally:ws.close()
        thread=threading.Thread(target=receive,daemon=True,name='worker-sampling-events');self.watchers[j['id']]=thread;thread.start()
    def tick(self):
        with self.lock:
            jobs=list(self.store.db['jobs'].values())
            active=next((j for j in jobs if j['status'] in ACTIVE and j.get('submission_intent')),None)
            if active:self.reconcile(active);return
            if self.store.db['worker_paused'] or not self.services.prepared:return
            j=next((j for j in jobs if j['status']=='queued'),None)
            if not j:return
            q=self.engine.get('/queue')
            if q['queue_running'] or q['queue_pending']:
                j['stage']='Waiting for shared renderer';self.store.save();return
            ram,commit=memory_headroom()
            # Cached Comfy allocations are reusable. Free VRAM alone would deadlock
            # the second job; Comfy handles model offload and reports real OOMs.
            if ram<12 or commit<20:
                j['stage']='Waiting for shared PC memory';self.store.save();return
            # Only our live owned process may receive /free. External Comfy manages
            # its own offload; never restart it or unload another user's cache.
            family='video' if j['kind']=='video' else 'image'
            from video_workflow import PREVIEW
            automatic_release=j.get('video_settings',{}).get('preset')!=PREVIEW
            if automatic_release and self.services.process and self.services.process.poll() is None and self.services.last_model_kind!=family:
                self.engine.post('/free',{'unload_models':True,'free_memory':True})
            self.services.last_model_kind=family
            # Persist intent BEFORE submission. UUID survives lost responses/restarts.
            j.update(status='submitting',stage='Submitting on PC',submission_intent=time.time(),attempts=1,prompt_id=j['comfy_id'])
            j.update(render_progress.initialize(j,j['graph']));self.watch(j)
            self.store.save()
            try:
                r=self.engine.post('/prompt',{'prompt':j['graph'],'prompt_id':j['comfy_id'],
                   'client_id':j['id'],'extra_data':{'pixeloid_worker_job':j['id']}})
                if r.get('node_errors'):j.update(status='failed',stage='Workflow rejected')
                else:j.update(prompt_id=r['prompt_id'],status='running',stage='Running on PC')
            finally:self.store.save()
    def run(self):
        while not self.stop.wait(1):
            try:self.tick()
            except Exception:
                # No automatic re-submission, and no prompts/tokens in logs.
                self.services.message='Worker lost contact with the renderer. Saved submissions will be reconciled; do not create duplicates.'

class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def respond(self,value,status=200):
        raw=json.dumps(value).encode();self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(raw)));self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(raw)
    def handle_request(self):
        try:
            self.server.access.origin(self.headers,self.client_address[0])
            if self.headers.get('Origin'):raise PermissionError('Use your local dashboard backend, not direct browser worker requests.')
            if not hmac.compare_digest(self.headers.get('Authorization',''),'Bearer '+self.server.token):raise PermissionError('Worker authentication required.')
            w=self.server.worker;path=urlparse(self.path).path;method=self.command
            if method=='GET':
                if path=='/v1/status':return self.respond(w.snapshot())
                if path=='/v1/nodes':return self.respond(w.engine.get('/object_info'))
                parts=path.strip('/').split('/')
                if len(parts)==3 and parts[:2]==['v1','jobs']:return self.respond(w.job(parts[2]))
                if len(parts)==4 and parts[:2]==['v1','jobs'] and parts[3]=='result':
                    with w.lock:j=w.store.db['jobs'][parts[2]];result=copy.deepcopy(j.get('history'))
                    if not result:raise ValueError('Result not ready.')
                    return self.respond(result)
                if len(parts)==3 and parts[:2]==['v1','outputs'] and ID.fullmatch(parts[2]):
                    raw,media_type=w.output(parts[2]);self.send_response(200);self.send_header('Content-Type',media_type);self.send_header('Content-Length',str(len(raw)));self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(raw);return
            if method=='POST':
                n=int(self.headers.get('Content-Length','0'));limit=32*1024*1024 if path=='/v1/inputs' else 1000000
                if not 0<n<=limit:raise ValueError('Invalid request size.')
                raw=self.rfile.read(n)
                if len(raw)!=n:raise ValueError('Incomplete request.')
                if path=='/v1/inputs':return self.respond(w.upload(raw))
                body=json.loads(raw)
                if path=='/v1/jobs':return self.respond(w.submit(body))
                if path.startswith('/v1/actions/'):return self.respond(w.action(path.split('/')[-1]))
                parts=path.strip('/').split('/')
                if len(parts)==4 and parts[:2]==['v1','jobs'] and parts[3]=='cancel':return self.respond(w.cancel(parts[2]))
            return self.respond({'error':'Unknown worker endpoint'},404)
        except PermissionError:return self.respond({'error':'Worker access denied'},403)
        except (ValueError,KeyError,FileNotFoundError) as exc:return self.respond({'error':str(exc)[:400]},400)
        except Exception:return self.respond({'error':'Processing service unavailable. Check PC worker status and retry the same job ID.'},503)
    do_GET=handle_request
    do_POST=handle_request

def serve(config_path):
    c=json.loads(Path(config_path).read_text(encoding='utf-8-sig'));root=Path(__file__).resolve().parent
    private=Path(c['private_dir']);private.mkdir(parents=True,exist_ok=True)
    lock=InstanceLock(private/'worker.lock')
    http=ThreadingHTTPServer((c['lan_ip'],c['port']),Handler);http.daemon_threads=True
    http.access=Access(private/'access',c['port'],c['lan_ip'],c['subnet'])
    http.token=Path(c['token_file']).read_text().strip()
    if len(http.token)<40:raise ValueError('Create a strong local pairing credential.')
    ctx=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);ctx.minimum_version=ssl.TLSVersion.TLSv1_2
    ctx.load_cert_chain(c['certificate'],c['private_key']);http.socket=ctx.wrap_socket(http.socket,server_side=True)
    http.worker=Worker(root,private,c['comfy_url'])
    threading.Thread(target=http.worker.run,daemon=True,name='PC render worker').start()
    (private/'worker.pid').write_text(str(os.getpid()))
    try:http.serve_forever()
    finally:http.worker.stop.set();http.server_close()

if __name__=='__main__':
    import sys
    sys.path.insert(0,str(Path(__file__).resolve().parent))
    serve(sys.argv[1])
