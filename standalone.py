"""Local component checks and guarded startup, independent of assistant runtimes."""
from pathlib import Path
import importlib, json, os, socket, subprocess, sys, threading, time
from urllib.parse import urlparse

ROOT=Path(__file__).resolve().parent
START_LOCK=threading.Lock()
ACTIVE=('queued','waiting','running')

def config(root=ROOT):
    p=Path(root)/'studio.local.json'
    value=json.loads(p.read_text(encoding='utf-8-sig')) if p.exists() else {}
    value.setdefault('comfy_url','http://127.0.0.1:8190')
    return value

def renderer_address(value):
    u=urlparse(value)
    if u.scheme!='http' or u.hostname not in ('localhost','127.0.0.1') or u.username or u.password or u.path not in ('','/') or u.query or u.fragment:raise ValueError('Renderer startup supports a local HTTP address only.')
    return u.hostname,u.port or 80

def run_hidden(args,**kw):
    return subprocess.run(args,capture_output=True,text=True,timeout=30,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0),**kw)

def running_comfy_processes():
    # Refuse another launch while any ComfyUI process is starting or unresponsive.
    script="Get-CimInstance Win32_Process | Where-Object { $_.Name -match '^python(w)?\\.exe$' -and $_.CommandLine -match 'ComfyUI[\\\\/]main\\.py' } | Select-Object ProcessId,CommandLine | ConvertTo-Json -Compress"
    result=run_hidden(['powershell.exe','-NoProfile','-Command',script])
    if result.returncode:raise ValueError('Windows denied the renderer process check. Startup was stopped to avoid a duplicate. Retry from Setup after restoring process-query permission.')
    rows=json.loads(result.stdout) if result.stdout.strip() else []
    return rows if isinstance(rows,list) else [rows]

def start_renderer(engine,root=ROOT):
    root=Path(root)
    with START_LOCK:
        if engine.health(force=True).get('connected'):return {'state':'connected','message':'Using the existing local renderer.'}
        c=config(root);host,port=renderer_address(engine.url)
        with socket.socket() as sock:
            sock.settimeout(.8)
            if sock.connect_ex((host,port))==0:raise ValueError('The renderer port is already occupied but is not responding as ComfyUI. No second process was started.')
        record=root/'logs'/'renderer-start.json'
        if record.exists() and time.time()-record.stat().st_mtime<180:return {'state':'starting','message':'Renderer startup is already in progress. Check again shortly.'}
        if running_comfy_processes():raise ValueError('An installed renderer is already running or starting but is not ready at the configured address. Check readiness in Setup; no duplicate was started.')
        base=Path(c.get('comfy_root',''));python=Path(c.get('comfy_python',''))
        if not (base/'main.py').is_file() or not python.is_file():raise ValueError('The local renderer location is missing. Open Setup and connect installed local components.')
        logs=root/'logs';logs.mkdir(exist_ok=True)
        args=[str(python),str(base/'main.py'),'--disable-auto-launch','--disable-api-nodes','--disable-all-custom-nodes','--listen','127.0.0.1','--port',str(port)]
        environment=os.environ.copy()
        environment.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_HUB_DISABLE_TELEMETRY='1',DO_NOT_TRACK='1')
        with (logs/'renderer.log').open('ab') as log:
            process=subprocess.Popen(args,cwd=str(base),env=environment,stdout=log,stderr=log,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        record.write_text(json.dumps({'pid':process.pid,'started':time.time(),'command':args},indent=2),encoding='utf8')
        return {'state':'starting','message':'Starting the installed local renderer. Models load only when needed.'}

def workflow_requirements(root):
    graphs=[json.loads((Path(root)/'templates'/f).read_text(encoding='utf-8-sig')) for f in ('flux.json','ltx.json')]
    types={n['class_type'] for g in graphs for n in g.values()}
    types.update(('ImagePadForOutpaint','VAEEncode','SplitSigmasDenoise','SolidMask','FeatherMask','MaskComposite','SetLatentNoiseMask','ImageCompositeMasked','LTXVAddGuide','LTXVCropGuides'))
    models=[]
    for g in graphs:
        for n in g.values():
            for key in ('unet_name','clip_name','vae_name'):
                if key in n['inputs']:models.append((n['class_type'],key,n['inputs'][key]))
    return types,sorted(set(models))

def job_findings(jobs,queue,stamp):
    present={row[1] for row in queue.get('queue_running',[])+queue.get('queue_pending',[])} if queue is not None else None
    result=[]
    for job in jobs.values():
        if job['status'] not in ACTIVE:continue
        prompt=job.get('prompt_id');last=job.get('render_tracking',{}).get('last_event') or job.get('started') or job.get('created',stamp)
        if prompt and present is not None and prompt not in present and stamp-last>45:
            result.append({'status':'warning','name':'Render awaiting reconciliation','detail':job['id']+' is absent from the queue. Its worker checks saved history before taking action. Do not submit a duplicate.'})
        elif prompt and stamp-last>600:
            result.append({'status':'warning','name':'No recent render progress','detail':job['id']+' has no new renderer event for over 10 minutes. It may be loading or decoding; no process was stopped or duplicate submitted.'})
    return result

def diagnostics(store,engine,root=ROOT):
    root=Path(root);checks=[]
    def add(name,status,detail):checks.append({'name':name,'status':status,'detail':detail})
    add('Local dashboard','ready','Runs in your browser on this PC. Codex and cloud accounts are not required.')
    for label,module in [('Images','PIL'),('Drawing geometry','numpy'),('Video reader','av'),('Renderer connection','requests'),('Live progress','websocket'),('PDF import','pypdfium2'),('Vector PDF reader','pymupdf'),('CAD DXF reader','ezdxf')]:
        try:importlib.import_module(module);add(label,'ready','Local component available.')
        except ImportError:add(label,'error','Component missing. Restore runtime/ and vendor/ from the local application package.')
    node=Path(os.environ.get('PIXELOID_NODE') or root/'runtime'/'node'/'node.exe')
    try:
        env=os.environ.copy();env['NODE_PATH']=os.pathsep.join(filter(None,[str(node.parent/'node_modules'),env.get('NODE_PATH')]))
        r=run_hidden([str(node),'-e',"require('sharp')({create:{width:2,height:2,channels:3,background:'#fff'}}).png().toBuffer().then(b=>console.log(b.length)).catch(e=>{console.error(e);process.exitCode=1})"],cwd=str(root),env=env)
        if r.returncode:raise ValueError(r.stderr[:200])
        add('Vector drawing export','ready','Bundled drawing engine passed a live export check.')
    except Exception:add('Vector drawing export','error','Restore runtime/node from the application package. Drawing edits cannot be exported until repaired.')
    health=engine.health(force=True);queue=None
    if not health.get('connected'):add('FLUX and LTX renderer','error','Offline. Start the local renderer in Setup. Your projects remain available.')
    else:
        add('FLUX and LTX renderer','ready','Connected to '+engine.url+'. Existing process is reused.')
        try:
            specs=engine.get('/object_info');types,models=workflow_requirements(root);missing=sorted(types-set(specs))
            add('Workflow components','error' if missing else 'ready','Missing: '+', '.join(missing) if missing else 'All FLUX, LTX and protected-edit nodes are available.')
            absent=[]
            for cls,key,name in models:
                choices=specs.get(cls,{}).get('input',{}).get('required',{}).get(key,[[]])[0]
                if not isinstance(choices,list) or name not in choices:absent.append(name)
            add('Model files','error' if absent else 'ready','Missing in ComfyUI: '+', '.join(absent) if absent else f'{len(models)} required model files are registered in ComfyUI. No model downloads or duplicate copies needed.')
            queue=engine.get('/queue')
        except Exception as exc:add('Workflow readiness','warning','Could not finish the renderer checks: '+str(exc)[:180])
    db=store.snapshot();missing_assets=[a for a in db['assets'].values() if not Path(a['path']).is_file()]
    add('Saved project files','warning' if missing_assets else 'ready',f'{len(missing_assets)} files are missing. Restore their project folders before rendering.' if missing_assets else f"{len(db['assets'])} saved files found; {len(db['projects'])} projects indexed.")
    checks.extend(job_findings(db['jobs'],queue,time.time()))
    failed=[j for j in db['jobs'].values() if j['status']=='failed']
    if failed:add('Previous activities','info',f'{len(failed)} previous activities need attention. Open Activity for their saved errors. They are never resubmitted automatically.')
    warned=[j for j in db['jobs'].values() if j.get('video_check',{}).get('warnings')]
    if warned:add('Video quality observations','warning',f'{len(warned)} clips have measured detail or brightness warnings. Check their full playback before approval; they have not been automatically repaired or accepted.')
    add('Visual accuracy','info','Completion is not visual approval. Check object design, placement, detail and the full video. Protected image edits verify the unchanged background; later video frames can still drift.')
    report={'checked':time.time(),'checks':checks,'status':'attention' if any(c['status'] in ('error','warning') for c in checks) else 'ready','renderer_connected':bool(health.get('connected')),'codex_required':False}
    (root/'logs').mkdir(exist_ok=True);(root/'logs'/'last-system-check.json').write_text(json.dumps(report,indent=2),encoding='utf8')
    return report
