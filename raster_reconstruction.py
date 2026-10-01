"""Dashboard jobs and reversible corrections for original-pixel reconstruction."""
import copy,hashlib,json,math,os,subprocess,sys,time
from pathlib import Path
from store import now
from raster_identity import correction_for, identified, indexed, reconcile


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
    return [plan.get('sha256'),plan.get('drawing',{}).get('revision',0),plan.get('raster_revision',0),plan.get('source_review')]


def run(engine,job):
    import project_storage
    st=engine.store;pid=job['project_id'];aid=job['plan_id']
    import source_scope
    contract=source_scope.prepare(st,job)
    if contract is None:return
    with st.lock:
        plan=copy.deepcopy(st.asset(aid));before=fingerprint(plan)
        if aid not in st.project(pid)['floor_plans']:raise ValueError('Plan is no longer in this project.')
    if plan.get('plan_source',{}).get('vector'):
        st.update_job(job['id'],status='completed',stage='Native geometry retained; raster tracing skipped',finished=now(),progress=100);return
    st.update_job(job['id'],status='running',stage='Extracting wall strokes from original pixels',progress=None,started=now())
    python=runtime(engine.app_root);worker=Path(engine.app_root)/'raster_geometry.py'
    scope=plan['source_review']['panels']
    panels,masked=source_scope.materialize(plan,contract,project_storage.project_root(st,pid)/'Supporting_Files'/'Source_Panels')
    key=hashlib.sha256(masked.read_bytes()+worker.read_bytes()+contract['key'].encode()).hexdigest()[:24]
    folder=project_storage.project_root(st,pid)/'Supporting_Files'/'Raster_Geometry'/key;folder.mkdir(parents=True,exist_ok=True)
    target=folder/'raster-geometry.json';cached=target.exists()
    if not cached:
        scope_path=folder/'panels.json';scope_path.write_text(json.dumps(scope),encoding='utf-8')
        args=[str(python),str(worker),str(masked),str(folder),'--panels',str(scope_path)]
        process=subprocess.Popen(args,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env={**os.environ,'OMP_NUM_THREADS':'2','OPENBLAS_NUM_THREADS':'2','MKL_NUM_THREADS':'2'},creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        started=time.monotonic()
        while process.poll() is None:
            if engine.stop.is_set() or st.db['jobs'][job['id']]['status']=='cancelled' or time.monotonic()-started>90:
                process.terminate();process.communicate(timeout=5)
                if time.monotonic()-started>90:raise ValueError('Boundary tracing reached its 90-second limit. Retry with a smaller page or inspect Setup.')
                st.update_job(job['id'],status='cancelled',stage='Boundary tracing stopped; saved corrections retained',finished=now());return
            time.sleep(.15)
        stdout,stderr=process.communicate()
        if process.returncode:raise ValueError('Boundary tracing failed: '+stderr.decode('utf-8',errors='replace')[-500:])
    result=json.loads(target.read_text(encoding='utf-8'));result['cached']=cached
    result['source_sha256']=contract['source_sha256'];result['source_contract']=contract
    sx=plan['width']/result['analysis_size'][0];sy=plan['height']/result['analysis_size'][1]
    for group in ('walls','uncertain_spans','openings','regions'):
        for item in result.get(group,[]):
            points=item.get('geometry',{}).get('points') or item.get('points') or item.get('polygon') or []
            matches=[p for p in contract['panels'] if points and all(p['pixel_box'][0]<=q[0]*sx<=p['pixel_box'][2] and p['pixel_box'][1]<=q[1]*sy<=p['pixel_box'][3] for q in points)]
            if len(matches)==1:item.update(panel_id=matches[0]['id'],floor=matches[0].get('floor',''))
    with st.lock:
        current=st.asset(aid)
        if fingerprint(current)!=before or not source_scope.current(current,contract) or job.get('status')=='cancelled':
            st.update_job(job['id'],status='cancelled',stage='Inputs changed; obsolete boundaries discarded',finished=now());return
        from engine import register_asset
        previous=current.get('raster_geometry',{})
        if previous and any(previous.get(k)!=result.get(k) for k in ('walls','uncertain_spans','openings','regions')):
            project=st.project(pid);project['map_confirmed']=False
            for room in project['rooms']:
                if room.get('plan_id')==aid:st.invalidate(pid,room)
        overlay=register_asset(st,pid,folder/'boundary-overlay.png','analysis_overlay',source_asset_id=aid)
        result['overlay_asset_id']=overlay['id'];result['pipeline_key']=key
        apply_report(current,result)
        st.save();st.update_job(job['id'],status='completed',stage=f"{len(result['walls'])} wall paths proposed; partial draft ready for review",progress=100,finished=now())


def apply_report(plan,result):
    result=identified(result)
    previous=plan.get('raster_geometry') or {}
    corrections,orphaned=reconcile(plan,result)
    evidence=('source_sha256','analysis_size','source_contract','source_scope','walls','uncertain_spans','openings','regions')
    if any(previous.get(k)!=result.get(k) for k in evidence):
        old_index,new_index=indexed(previous),indexed(result)
        by_identity={token:key for key,(_,token) in new_index.items()}
        drawing=plan.setdefault('drawing',{})
        # Transform/hidden edits are evidence-bound too. Keep unmatched edits
        # in the local archive and block completion until reviewed.
        edits=drawing.get('edits',{});remapped={}
        for key,value in edits.items():
            if key not in old_index:remapped[key]=value;continue
            target=by_identity.get(old_index[key][1])
            if target:remapped[target]=value
            else:orphaned.append({'id':key,'correction':copy.deepcopy(value),'reason':'Transformed source path changed; drawing edit was archived.'})
        drawing['edits']=remapped;drawing['revision']=drawing.get('revision',0)+1
        plan.setdefault('raster_review_archive',[]).append({
            'source_sha256':previous.get('source_sha256'),'corrections':copy.deepcopy(plan.get('raster_corrections',{})),
            'undo':copy.deepcopy(plan.get('raster_undo',[])),'redo':copy.deepcopy(plan.get('raster_redo',[]))})
        plan['raster_undo']=[];plan['raster_redo']=[]
        plan['raster_revision']=plan.get('raster_revision',0)+1
        plan.pop('raster_validation',None)
    plan['raster_geometry']=result;plan['raster_corrections']=corrections
    plan['raster_orphaned_corrections']=orphaned


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
        value=copy.deepcopy(item);correction=correction_for(plan,item['id'])
        if correction.get('action')=='reject':continue
        if correction.get('points'):
            value['geometry']={'type':'polyline','points':correction['points'],'note':'User correction; original pixel trace retained separately.'}
        value['review_state']=correction.get('action','pending');result.append(value)
    return result


def elements(plan):
    report=plan.get('raster_geometry')
    if not report:return []
    if plan.get('source_review'):
        from source_panels import valid,digest
        from source_scope import current
        if not valid(plan) or report.get('source_scope')!=digest(plan['source_review']['panels']):return []
        if report.get('source_contract') and not current(plan,report['source_contract']):return []
        if not report.get('source_contract') and plan['source_review'].get('revision',0)>0:return []
    sx=plan['width']/report['analysis_size'][0];sy=plan['height']/report['analysis_size'][1];result=[]
    for wall in paths(plan,True):
        correction=correction_for(plan,wall['id'])
        if correction.get('action')=='defer':continue
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
        ids=data.get('ids',[data.get('id')])
        if not isinstance(ids,list) or not 1<=len(ids)<=200 or any(not isinstance(k,str) or k not in known for k in ids) or len(set(ids))!=len(ids) or action not in ('accept','reject','edit','defer'):raise ValueError('Choose boundaries and a valid correction.')
        if len(ids)>1 and (action=='edit' or data.get('points') is not None or any(known[k].get('candidate_opening') or not known[k].get('width_px') for k in ids)):
            raise ValueError('Review wall paths together. Classify openings and uncertain exterior stretches individually.')
        points=data.get('points');width,height=plan['raster_geometry']['analysis_size']
        if points is not None and (not isinstance(points,list) or not 2<=len(points)<=500 or any(not isinstance(p,list) or len(p)!=2 or any(type(v) not in (int,float) or not math.isfinite(v) for v in p) or not 0<=p[0]<=width or not 0<=p[1]<=height for p in points)):
            raise ValueError('Keep boundary points inside the source image.')
        kind=data.get('kind')
        allowed=(None,'door','window','sliding_door','open_transition') if known[ids[0]].get('candidate_opening') else (None,'wall','window')
        if kind not in allowed:raise ValueError('Choose a supported classification for this boundary or opening.')
        plan.setdefault('raster_undo',[]).append(copy.deepcopy(plan.get('raster_corrections',{})));plan['raster_undo']=plan['raster_undo'][-40:];plan['raster_redo']=[]
        identities=indexed(plan['raster_geometry'])
        for key in ids:
            plan.setdefault('raster_corrections',{})[key]={**correction_for(plan,key),'source_identity':identities[key][1],'action':action,'updated':now(),**({'points':points} if points is not None else {}),**({'kind':kind} if kind else {})}
    project=st.project(pid);old_project=copy.deepcopy(project)
    try:
        plan['raster_revision']=plan.get('raster_revision',0)+1
        plan.pop('raster_validation',None)
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
