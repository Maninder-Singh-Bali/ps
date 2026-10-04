"""Explicitly linked manual plans use the active Store as their atomic authority.
Unlinked correction drafts stay isolated. No implicit activation or generation.
"""
import copy
import plan_drafts
from store import editing_busy


def linked_plan(store,key):
    matches=[a for a in store.db['assets'].values() if a.get('manual_draft_id')==key]
    if len(matches)>1:raise ValueError('This editable plan is linked to multiple assets; resolve the link before editing.')
    return matches[0] if matches else None


def get(store,key):
    plan=linked_plan(store,key)
    if not plan:return plan_drafts.get(key)
    return copy.deepcopy(plan['manual_document'])


def listing(store):
    rows=plan_drafts.listing()
    for plan in store.db['assets'].values():
        if not plan.get('manual_draft_id'):continue
        d=plan['manual_document'];rows=[r for r in rows if r['id']!=d['id']]
        rows.insert(0,{k:d.get(k) for k in ('id','name','revision','updated') }|{'count':len(d['features']),'active_project_id':plan['project_id']})
    return rows


def save(store,key,data):
    with store.lock:
        plan=linked_plan(store,key)
        if not plan:return plan_drafts.save(key,data)
        p=store.project(plan['project_id']);base=plan['manual_document']
        if editing_busy(store,p['id']):raise ValueError('Wait for this project’s current job before editing its shared scene.')
        if data.get('revision')!=base['revision']:raise ValueError('This plan changed in another window. Reopen before saving.')
        d=plan_drafts.validate(data,base)
        if not d.get('calibration'):raise ValueError('The active apartment must retain a verified drawing scale.')
        old=copy.deepcopy(store.db)
        try:
            d.update(revision=base['revision']+1,updated=plan_drafts.stamp(),active_project_id=p['id'])
            drawing=plan['drawing'];before=copy.deepcopy(drawing)
            drawing.update(features=copy.deepcopy(d['features']),surface_design=copy.deepcopy(d.get('surface_design',{})))
            drawing['site']['model'].update(metres_per_pixel=d['calibration']['metres_per_pixel'])
            drawing['site']['model']['wall_heights'][plan['manual_floor']]=d['wall_height_m']
            plan['surface_reference_files']=plan_drafts.reference_files(d,plan.get('surface_reference_files',{}))
            plan['manual_document']=d
            if before!=drawing:
                for r in p['rooms']:
                    if r.get('plan_id')==plan['id']:store.invalidate(p['id'],r)
                p['map_revision']+=1
                plan['manual_edit_review']='Saved geometry/design changed; review updated guide before any further generation.'
            store.save()
        except Exception:store.db=old;raise
        return copy.deepcopy(d)


def preview(store,data):
    plan=linked_plan(store,data.get('id'))
    if not plan:return plan_drafts.preview(data)
    snap=store.review_snapshot();plan=linked_plan(snap,data['id']);d=plan_drafts.validate(data,plan['manual_document'])
    plan['surface_reference_files']=plan_drafts.reference_files(d,plan.get('surface_reference_files',{}))
    plan['drawing'].update(features=d['features'],surface_design=d.get('surface_design',{}))
    plan['drawing']['site']['model'].update(metres_per_pixel=d['calibration']['metres_per_pixel'])
    plan['drawing']['site']['model']['wall_heights'][plan['manual_floor']]=d['wall_height_m']
    from shared_floor import build
    p=snap.project(plan['project_id']);room=next(r for r in p['rooms'] if r['id']==p['manual_preview_room_id'])
    return build(snap,room)


def activate(store,key,data):
    """Add a reviewed manual floor to an explicitly chosen/new project in one DB write.
    Earlier floors, rooms, outputs and phases are retained, never replaced.
    """
    from store import uid,now
    from pathlib import Path
    import shutil
    with store.lock,plan_drafts.LOCK:
        if linked_plan(store,key):raise ValueError('This plan is already linked. Open its project instead.')
        base=plan_drafts.get(key)
        if data.get('revision')!=base['revision']:raise ValueError('Plan changed. Save and review its latest revision before using it.')
        d=plan_drafts.validate(base,base)
        if not d.get('calibration') or d.get('background_alignment_unverified'):raise ValueError('Set and check the drawing scale and alignment first.')
        if not data.get('reviewed'):raise ValueError('Review extent, scale and unresolved geometry before linking.')
        fs=d['features'];walls=[f for f in fs if f['kind']=='wall']
        if not walls:raise ValueError('Trace at least one wall first.')
        refs=plan_drafts.reference_files(d)
        pts=[p for f in walls for p in f['points']];xs=[p[0] for p in pts];ys=[p[1] for p in pts]
        extent=[min(xs)/d['width'],min(ys)/d['height'],(max(xs)-min(xs))/d['width'],(max(ys)-min(ys))/d['height']]
        if min(extent[2:])<=0:raise ValueError('Trace a two-dimensional floor extent first.')
        before=copy.deepcopy(store.db);pid=data.get('project_id');new=not pid
        if pid:
            p=store.project(pid)
            if editing_busy(store,pid):raise ValueError('Wait for this project’s job before linking another floor.')
        else:
            pid=uid();p={'id':pid,'name':str(data.get('name') or d['name'])[:100],'created':now(),'updated':now(),'floor_plans':[],'rooms':[],'map_confirmed':False,'map_revision':0,'seed':2909202661,'style':'','music_id':None,
                'generation_phase':{'status':'paused','reason':'New manual plan requires review and separate generation authorization','allowances':{k:{'limit':0,'used':0} for k in ('image','video','reference')}}}
        aid=uid();rid=uid();floor=str(data.get('floor') or 'Ground floor')[:50]
        destination=store.root/'manual-plans'/aid;destination.mkdir(parents=True,exist_ok=False)
        try:
            files={}
            for file in plan_drafts.folder(key).iterdir():
                if file.is_file() and (file.name.startswith('page-') or file.name.startswith('original.')):
                    shutil.copy2(file,destination/file.name);files[file.name]=str(destination/file.name)
            page=Path(d['source_url']).name
            if page not in files:raise ValueError('The original drawing preview is missing; restore it before linking.')
            stored_refs={}
            for sha,path in refs.items():
                dest=destination/Path(path).name;shutil.copy2(path,dest);stored_refs[sha]=str(dest)
            d.update(active_project_id=pid,draft_only=False,revision=d['revision']+1,updated=plan_drafts.stamp())
            a={'id':aid,'project_id':pid,'kind':'plan','name':d['name'],'display_name':d['name'],'path':files[page],'width':d['width'],'height':d['height'],'created':now(),
               'manual_draft_id':key,'manual_document':d,'manual_floor':floor,'manual_source_files':files,'surface_reference_files':stored_refs,
               'drawing':{'features':copy.deepcopy(fs),'surface_design':copy.deepcopy(d.get('surface_design',{})),'surface_design_floor':floor,
                    'site':{'model':{'metres_per_pixel':d['calibration']['metres_per_pixel'],'scale_source':'Manual drawing calibration; not surveyed','wall_heights':{floor:d['wall_height_m']}}}}}
            r={'id':rid,'name':str(data.get('section_name') or 'Floor workspace · rooms need review')[:100],'floor':floor,'kind':'room','plan_id':aid,'bbox':extent,'notes':'Floor extent only. Review room boundaries before confirming the map.','references':[],'anchor_id':None,'images':[],'videos':[],'approved_image_id':None,'approved_video_id':None,'revision':1,'confidence':'manual','detection_note':'Explicitly linked floor workspace; room boundaries not inferred.'}
            store.db['projects'][pid]=p;store.db['assets'][aid]=a;p['manual_draft_id']=key;p['floor_plans'].append(aid);p['rooms'].append(r);p['manual_preview_room_id']=rid;p['map_confirmed']=False;p['map_revision']+=1;p['updated']=now()
            store.save()
        except Exception:
            store.db=before;shutil.rmtree(destination);raise
        return {'project_id':pid,'plan_id':aid,'room_id':rid,'document':copy.deepcopy(d),'created_project':new}


def source_file(store,key,name):
    plan=linked_plan(store,key)
    if plan and name in plan.get('manual_source_files',{}):return plan['manual_source_files'][name]
    return plan_drafts.folder(key)/name
