"""Dashboard jobs and reversible corrections for original-pixel reconstruction."""
import copy,hashlib,json,math,subprocess,sys,time
from pathlib import Path
from store import now


def runtime(root):
    from standalone import config
    candidates=[Path(sys.executable),Path(config(root).get('geometry_python') or config(root).get('comfy_python') or sys.executable)]
    for python in dict.fromkeys(candidates):
        if not python.is_file():continue
        probe=subprocess.run([str(python),'-c','import scipy, numpy, PIL'],capture_output=True,timeout=15,
                             creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        if probe.returncode==0:return python
    raise ValueError('Wall reconstruction needs the local SciPy image-processing component. Open Setup to connect an installed runtime. No cloud reader was used.')


def fingerprint(plan):
    return [plan.get('sha256'),plan.get('drawing',{}).get('revision',0),plan.get('raster_revision',0)]


def run(engine,job):
    import project_storage
    st=engine.store;pid=job['project_id'];aid=job['plan_id']
    with st.lock:
        plan=copy.deepcopy(st.asset(aid));before=fingerprint(plan)
        if aid not in st.project(pid)['floor_plans']:raise ValueError('Plan is no longer in this project.')
    if plan.get('plan_source',{}).get('vector'):
        st.update_job(job['id'],status='completed',stage='Native geometry retained; raster tracing skipped',finished=now(),progress=100);return
    st.update_job(job['id'],status='running',stage='Extracting wall strokes from original pixels',progress=None,started=now())
    python=runtime(engine.app_root);worker=Path(engine.app_root)/'raster_geometry.py'
    enhanced=st.db['assets'].get(plan.get('enhanced_reading_id'))
    key=hashlib.sha256(Path(plan['path']).read_bytes()+worker.read_bytes()+(Path(enhanced['path']).read_bytes() if enhanced else b'')).hexdigest()[:24]
    folder=project_storage.project_root(st,pid)/'Supporting_Files'/'Raster_Geometry'/key;folder.mkdir(parents=True,exist_ok=True)
    target=folder/'raster-geometry.json';cached=target.exists()
    if not cached:
        args=[str(python),str(worker),plan['path'],str(folder)]
        if enhanced:args.extend(['--enhanced',enhanced['path']])
        process=subprocess.Popen(args,stdout=subprocess.PIPE,stderr=subprocess.PIPE,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        started=time.monotonic()
        while process.poll() is None:
            if engine.stop.is_set() or job['status']=='cancelled' or time.monotonic()-started>90:
                process.terminate();process.communicate(timeout=5)
                if time.monotonic()-started>90:raise ValueError('Boundary tracing reached its 90-second limit. Retry with a smaller page or inspect Setup.')
                st.update_job(job['id'],status='cancelled',stage='Boundary tracing stopped; saved corrections retained',finished=now());return
            time.sleep(.15)
        stdout,stderr=process.communicate()
        if process.returncode:raise ValueError('Boundary tracing failed: '+stderr.decode('utf-8',errors='replace')[-500:])
    result=json.loads(target.read_text(encoding='utf-8'));result['cached']=cached
    with st.lock:
        current=st.asset(aid)
        if fingerprint(current)!=before:
            current['raster_suggestion']=result
            st.update_job(job['id'],status='completed',stage='New boundaries saved separately; your edits were preserved',progress=100,finished=now());return
        from engine import register_asset
        previous=current.get('raster_geometry',{})
        if previous and any(previous.get(k)!=result.get(k) for k in ('walls','uncertain_spans','openings','regions')):
            project=st.project(pid);project['map_confirmed']=False
            for room in project['rooms']:
                if room.get('plan_id')==aid:st.invalidate(pid,room)
        overlay=register_asset(st,pid,folder/'boundary-overlay.png','analysis_overlay',source_asset_id=aid)
        result['overlay_asset_id']=overlay['id'];result['pipeline_key']=key;current['raster_geometry']=result
        current.setdefault('raster_corrections',{});current.setdefault('raster_revision',0)
        st.save();st.update_job(job['id'],status='completed',stage=f"{len(result['walls'])} wall paths proposed; partial draft ready for review",progress=100,finished=now())


def candidates(plan):
    report=plan.get('raster_geometry') or {}
    walls=report.get('walls',[])
    result=walls+report.get('uncertain_spans',[])
    by_id={wall['id']:wall for wall in walls}
    for opening in report.get('openings',[]):
        widths=[by_id[key]['width_px'] for key in opening.get('wall_ids',[]) if key in by_id]
        result.append({**opening,'candidate_opening':True,'width_px':sum(widths)/len(widths) if widths else 8,
                       'geometry':{'type':'polyline','points':opening['points']}})
    return result


def paths(plan,include_uncertain=False):
    items=candidates(plan) if include_uncertain else (plan.get('raster_geometry') or {}).get('walls',[])
    result=[]
    for item in items:
        value=copy.deepcopy(item);correction=plan.get('raster_corrections',{}).get(item['id'],{})
        if correction.get('action')=='reject':continue
        if correction.get('points'):
            value['geometry']={'type':'polyline','points':correction['points'],'note':'User correction; original pixel trace retained separately.'}
        value['review_state']=correction.get('action','pending');result.append(value)
    return result


def elements(plan):
    report=plan.get('raster_geometry')
    if not report:return []
    sx=plan['width']/report['analysis_size'][0];sy=plan['height']/report['analysis_size'][1];result=[]
    for wall in paths(plan,True):
        correction=plan.get('raster_corrections',{}).get(wall['id'],{})
        if wall.get('candidate_opening') and correction.get('kind') not in ('door','window','sliding_door'):continue
        if not wall.get('width_px') and correction.get('kind') not in ('wall','window'):continue
        points=wall['geometry']['points'];d='M'+' L'.join(f'{x*sx:.4f},{y*sy:.4f}' for x,y in points)
        width=wall.get('width_px',8);kind=correction.get('kind','wall')
        result.append({'id':wall['id'],'kind':kind,'origin':'raster_candidate','svg':f'<path d="{d}" stroke-width="{width*sx:.4f}" fill="none"/>',
                       'native_source_id':wall['id'],'review_state':wall['review_state']})
    return result


def correct(st,pid,aid,data):
    plan=st.asset(aid)
    if aid not in st.project(pid)['floor_plans']:raise ValueError('Choose this project’s plan.')
    if data.get('revision')!=plan.get('raster_revision',0):raise ValueError('Boundaries changed. Refresh before saving.')
    if data.get('source_sha256')!=plan.get('raster_geometry',{}).get('source_sha256'):raise ValueError('Source changed. Reopen boundary review.')
    action=data.get('action');before=copy.deepcopy(plan)
    if action in ('undo','redo'):
        src='raster_undo' if action=='undo' else 'raster_redo';dest='raster_redo' if action=='undo' else 'raster_undo'
        if not plan.get(src):raise ValueError('No boundary edit to '+action+'.')
        plan.setdefault(dest,[]).append(copy.deepcopy(plan.get('raster_corrections',{})))
        plan['raster_corrections']=plan[src].pop()
    else:
        known={v['id']:v for v in candidates(plan)}
        if data.get('id') not in known or action not in ('accept','reject','edit','defer'):raise ValueError('Choose a boundary and a valid correction.')
        points=data.get('points');width,height=plan['raster_geometry']['analysis_size']
        if points is not None and (not isinstance(points,list) or not 2<=len(points)<=500 or any(not isinstance(p,list) or len(p)!=2 or any(type(v) not in (int,float) or not math.isfinite(v) for v in p) or not 0<=p[0]<=width or not 0<=p[1]<=height for p in points)):
            raise ValueError('Keep boundary points inside the source image.')
        kind=data.get('kind')
        allowed=(None,'door','window','sliding_door','open_transition') if known[data['id']].get('candidate_opening') else (None,'wall','window')
        if kind not in allowed:raise ValueError('Choose a supported classification for this boundary or opening.')
        plan.setdefault('raster_undo',[]).append(copy.deepcopy(plan.get('raster_corrections',{})));plan['raster_undo']=plan['raster_undo'][-40:];plan['raster_redo']=[]
        plan.setdefault('raster_corrections',{})[data['id']]={**plan.get('raster_corrections',{}).get(data['id'],{}),'action':action,'updated':now(),**({'points':points} if points is not None else {}),**({'kind':kind} if kind else {})}
    project=st.project(pid);old_project=copy.deepcopy(project)
    try:
        plan['raster_revision']=plan.get('raster_revision',0)+1
        plan.setdefault('drawing',{})['revision']=plan.get('drawing',{}).get('revision',0)+1
        project['map_confirmed']=False
        for room in project['rooms']:
            if room.get('plan_id')==aid:st.invalidate(pid,room)
        st.save()
    except Exception:
        plan.clear();plan.update(before);project.clear();project.update(old_project);raise
    return {'revision':plan['raster_revision'],'saved':True,'geometry_validated':False}


def draft(st,pid,aid):
    from drawing_editor import get_document
    from drawing_scene import resolve,cut_walls
    from scene_scale import estimate,settings
    from scene_document import from_plan
    plan=st.asset(aid)
    if aid not in st.project(pid)['floor_plans']:raise ValueError('Plan does not belong to project.')
    native=bool(plan.get('plan_source',{}).get('vector') or plan.get('cad_redraw_id'))
    rows,unresolved=resolve(get_document(st,pid,aid));scale,scale_source=estimate(st,plan)
    height=settings(plan,'Unassigned')['wall_height_m'];surfaces=[]
    for wall in cut_walls(rows):
        if wall['kind'] not in ('wall','window','door','sliding_door'):continue
        a,b=[np for np in wall['points']];dx,dy=b[0]-a[0],b[1]-a[1];length=math.hypot(dx,dy)
        if length<.01:continue
        offset=[-dy/length*wall['thickness']/2,dx/length*wall['thickness']/2]
        corners=[[((p[0]+sign*offset[0])*scale),((p[1]+sign*offset[1])*scale)] for p,sign in [(a,1),(b,1),(b,-1),(a,-1)]]
        kind=wall['kind'];bands=[(0,height,[160,182,168])]
        if kind=='window':bands=[(0,.9,[160,182,168]),(.9,2.4,[173,207,218]),(2.4,height,[160,182,168])]
        elif kind=='door':bands=[(2.2,height,[160,182,168])]
        elif kind=='sliding_door':bands=[(0,2.4,[173,207,218]),(2.4,height,[160,182,168])]
        for low,high,color in bands:
            low=max(0,min(height,low));high=max(0,min(height,high))
            if high<=low:continue
            faces=[[[*p,high] for p in corners]]+[[[*p,low],[*q,low],[*q,high],[*p,high]] for p,q in zip(corners,corners[1:]+corners[:1])]
            for points in faces:surfaces.append({'points':points,'color':color,'kind':'wall_candidate' if kind=='wall' else kind,'source_id':wall['source_id']})
    scene={'plan_id':aid,'floor':'Unassigned — partial native draft' if native else 'Unassigned — partial raster draft','bounds':[0,0,1,1],'width':plan['width']*scale,'depth':plan['height']*scale,'height':height,
           'calibrated':False,'surfaces':surfaces,'lines':rows,'products':[],'camera':None,'saved_camera':None,
           'unresolved_architecture':unresolved+[s['id'] for s in plan.get('raster_geometry',{}).get('uncertain_spans',[])],
           'issues':['Partial, unverified draft. Thin boundaries, openings, floor assignments and rooms still need review.'],
           'limits':[('Native paths with provisional classification; no room-box walls invented.' if native else 'Pixel-supported wall candidates only; no floor slab or room-box walls invented.'),scale_source,'Wall height is the editable project default.'],
           'partial':True,'geometry_validated':False,'scene_document':from_plan(plan,st.project(pid)['rooms'],rows)}
    scene['geometry_hash']=hashlib.sha256(json.dumps(surfaces,sort_keys=True).encode()).hexdigest();return scene
