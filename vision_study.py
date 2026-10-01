"""Local visual proposals with source provenance. Never changes verified geometry."""
import base64, copy, hashlib, io, json, math, os, socket, subprocess, time
from pathlib import Path
from urllib.parse import urlparse
import requests
from PIL import Image
from store import uid, now

MODEL='qwen3-vl:8b-instruct'
SCHEMA={'type':'object','properties':{'features':{'type':'array','items':{'type':'object','properties':{
    'kind':{'type':'string','enum':['wall','curved_wall','door','window','sliding_door','stair','furniture','space','unknown']},
    'label':{'type':'string'},'object_type':{'type':'string'},'seat_count':{'type':['integer','null']},
    'bbox':{'type':'array','items':{'type':'number'},'minItems':4,'maxItems':4},'floor':{'type':'string'},
    'confidence':{'type':'string','enum':['low','medium','high']},'evidence':{'type':'string'}},
    'required':['kind','label','object_type','seat_count','bbox','floor','confidence','evidence'],'additionalProperties':False}},
    'uncertainties':{'type':'array','items':{'type':'string'}}},'required':['features','uncertainties'],'additionalProperties':False}

def ensure_service(root,url):
    u=urlparse(url)
    if u.scheme!='http' or u.hostname not in ('127.0.0.1','localhost') or u.username or u.password or u.path not in ('','/') or u.query or u.fragment:
        raise ValueError('Use a local vision service address.')
    s=requests.Session();s.trust_env=False
    try:return s.get(url+'/api/tags',timeout=3).json()
    except requests.RequestException:pass
    with socket.socket() as sock:
        sock.settimeout(1)
        if sock.connect_ex((u.hostname,u.port or 80))==0:raise ValueError('Vision port is occupied. No duplicate service started.')
    root=Path(root)
    from standalone import config as local_config
    config=local_config(root);exe=Path(config.get('ollama_executable') or root/'runtime'/'ollama'/'ollama.exe')
    if not exe.exists():raise ValueError('Local vision runtime missing. Open Setup and connect installed local components.')
    models=Path(config['comfy_root'])/'models'/'vision'/'ollama'
    env=os.environ.copy();env.update(OLLAMA_HOST=u.netloc,OLLAMA_MODELS=str(models),OLLAMA_KEEP_ALIVE='0',OLLAMA_NUM_PARALLEL='1',OLLAMA_NO_CLOUD='1')
    logs=root/'logs';logs.mkdir(exist_ok=True)
    with (logs/'vision-service.log').open('ab') as log:
        proc=subprocess.Popen([str(exe),'serve'],cwd=root,env=env,stdout=log,stderr=log,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    (root/'vision-service.json').write_text(json.dumps({'pid':proc.pid,'started':now(),'model_path':str(models)}))
    for _ in range(20):
        time.sleep(.5)
        try:return s.get(url+'/api/tags',timeout=1).json()
        except requests.RequestException:pass
    raise ValueError('Local vision service did not become ready. Check logs/vision-service.log.')

def clean_result(raw):
    if not isinstance(raw,dict):raise ValueError('Vision returned an invalid report; no plan changes made.')
    rows=[]
    for item in raw.get('features',[]):
        if not isinstance(item,dict):continue
        kind=item.get('kind');box=item.get('bbox')
        if kind not in ('wall','curved_wall','door','window','sliding_door','stair','furniture','space','unknown'):kind='unknown'
        if not isinstance(box,list) or len(box)!=4 or any(type(v) not in (int,float) or not math.isfinite(v) for v in box):continue
        x,y,w,h=box
        if min(x,y)<0 or min(w,h)<.001 or x+w>1.00001 or y+h>1.00001:continue
        seats=item.get('seat_count');seats=seats if type(seats) is int and 1<=seats<=12 else None
        rows.append({'id':uid(),'kind':kind,'bbox':box,'label':str(item.get('label',kind))[:120],
                     'seat_count':seats,'object_type':str(item.get('object_type',''))[:70],
                     'floor':str(item.get('floor',''))[:80],'evidence':str(item.get('evidence','Uncertain visual proposal'))[:1000],
                     'confidence':item.get('confidence') if item.get('confidence') in ('low','medium','high') else 'low',
                     'review_status':'pending','source':'local_vision','notes':'','shape':'unspecified','room_id':None,'connection_room_id':None})
    warnings=[str(v)[:800] for v in raw.get('uncertainties',[])[:30]]
    return {'features':rows,'warnings':warnings,'reviewed':False}

def check_observations(result,sections):
    """Reject room-sized furniture locations; model confidence is not validation."""
    for f in result['features']:
        if f['kind']!='furniture':continue
        b=f['bbox']
        for r in sections:
            rb=r['bbox'];intersection=max(0,min(b[0]+b[2],rb[0]+rb[2])-max(b[0],rb[0]))*max(0,min(b[1]+b[3],rb[1]+rb[3])-max(b[1],rb[1]))
            if intersection>rb[2]*rb[3]*.65:
                f['location_unresolved']=True;f['confidence']='low'
                result['warnings'].append(f"{f['label']}: predicted bounds cover most of {r['name']}. This is not an object location; mark it before importing.")
    result['accuracy_verified']=False
    return result

def read(path,settings,sections,progress):
    from object_detection import read as read_objects
    return read_objects(path,path,settings,sections,progress)

def run(engine,job):
    from engine import memory_headroom,available_vram
    import project_storage
    st=engine.store;pid=job['project_id'];a=st.asset(job['plan_id']);p=st.project(pid)
    if job['plan_id'] not in p['floor_plans']:raise ValueError('Plan no longer belongs to this project.')
    while True:
        if engine.stop.is_set() or job['status']=='cancelled':return
        try:q=engine.get('/queue')
        except requests.ConnectionError:q=None  # A stopped renderer owns no GPU models.
        busy=q and (q['queue_running'] or q['queue_pending'])
        if not busy and q:engine.post('/free',{'unload_models':True,'free_memory':True})
        ram,commit=memory_headroom();vram=available_vram()
        if not busy and ram>=12 and commit>=20 and (vram is None or vram>=2):break
        st.update_job(job['id'],status='waiting',stage='Waiting for local renderer' if busy else 'Waiting for available RAM / GPU memory',progress=None)
        engine.stop.wait(3)
    st.update_job(job['id'],status='running',started=now(),stage='Preparing local plan reader',progress=None)
    if q:engine.post('/free',{'unload_models':True,'free_memory':True})
    settings=copy.deepcopy(st.db['settings']);url=settings.get('vision_url','http://127.0.0.1:11434').rstrip('/')
    tags=ensure_service(engine.app_root,url);model=settings.get('vision_model') or MODEL
    if not any(v['name']==model for v in tags.get('models',[])):raise ValueError('Local vision model is not installed: '+model)
    sections=[copy.deepcopy(r) for r in p['rooms'] if r['id'] in job.get('section_ids',[])]
    import plan_upscale, object_detection
    from engine import register_asset
    progress=lambda stage,value:st.update_job(job['id'],stage=stage,progress=value)
    folder=project_storage.project_root(st,pid)/'Supporting_Files'/'Enhanced_Plans'
    path=a['path'];enhancement=None
    input_drawing_revision=a.get('drawing',{}).get('revision',0)
    try:
        path,enhancement=plan_upscale.enhance(a['path'],engine.app_root,folder,progress)
        if enhancement['scale']>1:
            with st.lock:
                existing=next((v for v in st.db['assets'].values() if v.get('project_id')==pid and v.get('path')==str(path)),None)
                enhanced=existing or register_asset(st,pid,path,'plan_preview',source_asset_id=a['id'],enhancement=enhancement,output_upscaled=True)
                a['enhanced_reading_id']=enhanced['id'];st.save()
    except (OSError,ValueError,KeyError,subprocess.SubprocessError) as exc:
        path=a['path']
        enhancement={'method':'native','scale':1,'warning':'Enhancement unavailable: '+str(exc)[:250]}
    report=object_detection.read(a['path'],path,settings,sections,progress,folder/'Detection_Cache',
        cancelled=lambda: st.db['jobs'][job['id']]['status']=='cancelled' or engine.stop.is_set())
    report['enhancement']=enhancement
    if enhancement.get('warning'):report['warnings'].append(enhancement['warning'])
    with st.lock:
        a=st.asset(job['plan_id']);p=st.project(pid)
        report['input_map_revision']=job['input_revision'];report['stale']=p['map_revision']!=job['input_revision'] or a.get('plan_reading',{}).get('revision',0)!=job.get('study_revision',0) or a.get('drawing',{}).get('revision',0)!=input_drawing_revision
        report['input_study_revision']=job.get('study_revision',a.get('plan_reading',{}).get('revision',0))
        folder=project_storage.project_root(st,pid)/'Supporting_Files'/'Vision_Studies';folder.mkdir(parents=True,exist_ok=True)
        (folder/(job['id']+'.json')).write_text(json.dumps(report,indent=2),encoding='utf8')
        previous=a.get('vision_report') or {}
        report['review_decisions']=copy.deepcopy(previous.get('review_decisions',{}))
        a['vision_report']=report;st.save()
        if not a.get('plan_source',{}).get('vector') and enhancement.get('scale',1)>1:
            st.new_job(pid,'raster_reconstruction',plan_id=a['id'])
        if report.get('cancelled') or job.get('status')=='cancelled':
            st.update_job(job['id'],status='cancelled',stage='Analysis stopped; partial results retained',finished=now(),report=report);return
        stage=('Visual proposals ready — review required' if report.get('coverage_complete') else 'Partial analysis saved — resume to cover remaining regions') if report['features'] else 'No usable symbols — needs attention'
        st.update_job(job['id'],status='completed' if report['features'] else 'failed',stage=stage,progress=100 if report.get('coverage_complete') else None,error=None if report['features'] else 'No usable symbols were found. The plan has not been verified or changed.',finished=now(),report=report)

def import_proposals(st,pid,aid,data):
    import plan_reading
    a=st.asset(aid);p=st.project(pid);doc=plan_reading.get_reading(st,pid,aid);report=a.get('vision_report')
    from detection_review import reconcile
    if report:report=reconcile(report)
    plan_reading._idle(st,pid)
    if not report or report.get('stale') or report['input_map_revision']!=p['map_revision'] or report.get('input_study_revision',doc['revision'])!=doc['revision']:raise ValueError('Plan changed since this reading. Read it again before importing proposals.')
    if data.get('revision')!=doc['revision']:raise ValueError('Study changed. Reopen it first.')
    if report.get('imported'):raise ValueError('These proposals are already in the study.')
    added=[]
    for f in report['features']:
        if f.get('location_unresolved') or f.get('review_resolution')=='rejected' or f['kind']=='unknown':continue
        if any(plan_reading.overlap(f['bbox'],v['bbox'])>.65 and f['kind']==v['kind'] for v in doc['features']):continue
        item=copy.deepcopy(f)
        item['review_status']='pending';item['source']='local_vision'
        if item['seat_count']:item['notes']=f"Visual estimate: {item['seat_count']} seats; verify against original."
        added.append(item)
    if not added:raise ValueError('No new usable locations to import. Mark uncertain objects in Study structure; the plan was not changed.')
    result=plan_reading.save_reading(st,pid,aid,{**doc,'features':doc['features']+added,'reviewed':False})
    report['imported']=True;a['vision_report']=report;st.save();return {'added':len(added),'reading':result}
