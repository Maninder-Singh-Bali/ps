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

def read_scoped(plan,scope,settings,sections,progress,folder,root,cancelled):
    import source_scope,plan_upscale,object_detection
    panels,_=source_scope.materialize(plan,scope,folder/'Source_Panels')
    panels=[p for p in panels if not sections or source_scope.local_sections(sections,p)]
    reports=[];features=[];observations=[];warnings=[];passes=[]
    for panel in panels:
        if cancelled():break
        panel_folder=folder/scope['key']/panel['id']
        try:
            enhanced,enhancement=plan_upscale.enhance(panel['path'],root,panel_folder,progress)
        except (OSError,ValueError,KeyError,subprocess.SubprocessError) as exc:
            enhanced=panel['path'];enhancement={'method':'native','warning':'Enhancement unavailable: '+str(exc)[:250]}
        local=source_scope.local_sections(sections,panel)
        if sections and not local:continue
        identity={**scope,'panel_id':panel['id']}
        report=object_detection.read(panel['path'],enhanced,settings,local,progress,panel_folder/'Detection_Cache',
                                     cancelled=cancelled,source_scope=identity)
        reports.append(report)
        def mapped(row):
            value=source_scope.map_row(row,panel,scope)
            token=lambda key:'observation'+hashlib.sha256((scope['key']+panel['id']+key).encode()).hexdigest()[:24]
            value['id']=token(row['id'])
            if row.get('original_matches'):value['original_matches']=[token(key) for key in row['original_matches']]
            return value
        features.extend(mapped(row) for row in report['features'])
        observations.extend(mapped(row) for row in report.get('original_observations',[]))
        passes.extend({**row,'panel_id':panel['id'],'floor':panel.get('floor','')} for row in report.get('passes',[]))
        warnings.extend(report.get('warnings',[]))
        if enhancement.get('warning'):warnings.append(enhancement['warning'])
    complete=bool(reports) and len(reports)==len([p for p in panels if not sections or source_scope.local_sections(sections,p)]) and all(r.get('coverage_complete') for r in reports)
    unfinished=len(panels)-len(reports)
    coverage={'pending_regions':sum(r.get('coverage',{}).get('pending_regions',0) for r in reports)+unfinished,
              'failed_regions':sum(r.get('coverage',{}).get('failed_regions',0) for r in reports),
              'saturated_regions':sum(r.get('coverage',{}).get('saturated_regions',0) for r in reports),
              'network_calls':sum(r.get('coverage',{}).get('network_calls',0) for r in reports),
              'resumable':bool(unfinished or any(r.get('coverage',{}).get('resumable') for r in reports))}
    from detection_review import reconcile
    return reconcile(dict(features=features,original_observations=observations,passes=passes,warnings=list(dict.fromkeys(warnings)),
        pipeline_key=hashlib.sha256(json.dumps([scope['key'],settings.get('vision_model') or MODEL,sections,[r.get('pipeline_key') for r in reports]],sort_keys=True).encode()).hexdigest(),
        reviewed=False,source_scope=scope,source_sha256=scope['source_sha256'],source_size=scope['source_size'],
        coverage=coverage,coverage_complete=complete,complete=complete,processing_finished=not cancelled(),cancelled=cancelled(),
        geometry_validated=False,accuracy_verified=False,scale_status='estimated',model=settings.get('vision_model') or MODEL,
        elapsed_seconds=round(sum(r.get('elapsed_seconds',0) for r in reports),2)))


def run(engine,job):
    from engine import memory_headroom,available_vram
    import project_storage,source_scope
    st=engine.store;pid=job['project_id'];aid=job['plan_id']
    scope=source_scope.prepare(st,job)
    if scope is None:return
    with st.lock:
        a=copy.deepcopy(st.asset(aid));p=copy.deepcopy(st.project(pid))
        if aid not in p['floor_plans']:raise ValueError('Plan no longer belongs to this project.')
        revisions=[p['map_revision'],a.get('plan_reading',{}).get('revision',0),a.get('drawing',{}).get('revision',0)]
        st.update_job(job['id'],input_revision=revisions[0],study_revision=revisions[1],drawing_revision=revisions[2])
    while True:
        if engine.stop.is_set() or job['status']=='cancelled':return
        try:q=engine.get('/queue')
        except requests.ConnectionError:q=None
        busy=q and (q['queue_running'] or q['queue_pending'])
        if not busy and q:engine.post('/free',{'unload_models':True,'free_memory':True})
        ram,commit=memory_headroom();vram=available_vram()
        if not busy and ram>=12 and commit>=20 and (vram is None or vram>=2):break
        st.update_job(job['id'],status='waiting',stage='Waiting for local renderer' if busy else 'Waiting for available RAM / GPU memory',progress=None)
        engine.stop.wait(3)
    st.update_job(job['id'],status='running',started=now(),stage='Reading approved plan panels',progress=None)
    settings=copy.deepcopy(st.db['settings']);url=settings.get('vision_url','http://127.0.0.1:11434').rstrip('/')
    tags=engine.services.reader_ready() if getattr(engine,'services',None) else ensure_service(engine.app_root,url);model=settings.get('vision_model') or MODEL
    if not any(v['name']==model for v in tags.get('models',[])):raise ValueError('Local vision model is not installed: '+model)
    sections=[copy.deepcopy(r) for r in p['rooms'] if r['id'] in job.get('section_ids',[])]
    folder=project_storage.project_root(st,pid)/'Supporting_Files'/'Enhanced_Plans'
    report=read_scoped(a,scope,settings,sections,lambda stage,value:st.update_job(job['id'],stage=stage,progress=value),
                       folder,engine.app_root,lambda: st.db['jobs'][job['id']]['status']=='cancelled' or engine.stop.is_set())
    with st.lock:
        current=st.asset(aid);project=st.project(pid)
        live=[project['map_revision'],current.get('plan_reading',{}).get('revision',0),current.get('drawing',{}).get('revision',0)]
        report.update(input_map_revision=revisions[0],input_study_revision=revisions[1],input_drawing_revision=revisions[2],
                      stale=not source_scope.current(current,scope) or live!=revisions)
        folder=project_storage.project_root(st,pid)/'Supporting_Files'/'Vision_Studies';folder.mkdir(parents=True,exist_ok=True)
        (folder/(job['id']+'.json')).write_text(json.dumps(report,indent=2),encoding='utf8')
        if report['stale']:
            st.update_job(job['id'],status='cancelled',stage='Inputs changed; obsolete analysis discarded',finished=now(),report=report);return
        previous=current.get('vision_report') or {}
        if previous.get('source_scope')==scope:
            report['review_decisions']=copy.deepcopy(previous.get('review_decisions',{}))
        elif previous:
            current.setdefault('vision_report_archive',[]).append(previous)
        current['vision_report']=report;st.save()
        if report.get('cancelled') or job.get('status')=='cancelled':
            st.update_job(job['id'],status='cancelled',stage='Analysis stopped; current-scope partial results retained',finished=now(),report=report);return
        resumable=report.get('coverage',{}).get('resumable')
        stage='Visual proposals ready  -  review required' if report.get('coverage_complete') else ('Partial analysis saved  -  resume remaining regions' if resumable else 'Detector exhausted  -  correct evidence or change detection approach')
        st.update_job(job['id'],status='completed' if report['features'] else 'failed',stage=stage,progress=100 if report.get('coverage_complete') else None,
                      error=None if report['features'] else 'No usable symbols; inspect original and detector limitations.',finished=now(),report=report)

def import_proposals(st,pid,aid,data):
    import plan_reading
    a=st.asset(aid);p=st.project(pid);doc=plan_reading.get_reading(st,pid,aid);report=a.get('vision_report')
    from detection_review import reconcile
    if report:report=reconcile(report)
    plan_reading._idle(st,pid)
    from source_scope import current
    if not report or not current(a,report.get('source_scope')) or report.get('stale') or report['input_map_revision']!=p['map_revision'] or report.get('input_study_revision',doc['revision'])!=doc['revision']:raise ValueError('Plan changed since this reading. Read it again before importing proposals.')
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
