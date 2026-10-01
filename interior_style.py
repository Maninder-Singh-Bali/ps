"""Product/finish assignments on existing rooms; no second geometry model."""
import copy
from urllib.parse import urlsplit


def clean_assignment(data):
    out={k:str(data.get(k,'')).strip()[:2000 if k=='notes' else 240] for k in ('name','variant','notes','dimensions')}
    url=str(data.get('product_url','')).strip()
    if url:
        p=urlsplit(url)
        if p.scheme not in ('http','https') or not p.hostname or p.username or p.password or len(url)>4096 or any(c.isspace() for c in url):
            raise ValueError('Use a complete product link without embedded credentials.')
    out['product_url']=url
    out['dimension_status']=data.get('dimension_status','missing')
    if out['dimension_status'] not in ('missing','estimated','extracted','reviewed'):raise ValueError('Choose a dimension review status.')
    return out


def save_surfaces(store,pid,room,data):
    if data.get('revision')!=room['revision']:raise ValueError('The room changed. Reopen Surfaces before saving.')
    if any(j.get('project_id')==pid and j['status'] in ('queued','running','waiting') for j in store.db['jobs'].values()):
        raise ValueError('Finish or cancel active processing before changing finishes.')
    result={}
    for target,value in data.get('surfaces',{}).items():
        if target not in ('floor','walls','ceiling'):raise ValueError('Choose floor, walls or ceiling.')
        row=clean_assignment(value)
        ids=value.get('image_ids',[])
        if not isinstance(ids,list) or len(ids)>8 or any(a not in room['references'] for a in ids):raise ValueError('Choose up to eight images belonging to this room.')
        row['image_ids']=list(dict.fromkeys(ids))
        row['asset_id']=value.get('asset_id') or (ids[0] if ids else None)
        if row['asset_id'] and row['asset_id'] not in ids:raise ValueError('Choose the primary image from this surface’s images.')
        if any(v.get('asset_id') in ids for v in room.get('block_layout',{}).get('items',[])):raise ValueError('This image is assigned to an object. Upload a separate finish reference.')
        row['origin']='proposed_design'
        result[target]=row
    if result!=room.get('surfaces',{}):
        room['surfaces']=result;store.invalidate(pid,room);store.save()
    return copy.deepcopy(result)


def surface_references(store,room):
    rows=[]
    for target,v in room.get('surfaces',{}).items():
        if not v.get('asset_id'):continue
        a=store.asset(v['asset_id'])
        if not a.get('enabled',True):continue
        rows.append({**a,'surface_target':target,'category':v.get('name') or target+' finish',
                     'placement':f"Apply only to {target}. Variant: {v.get('variant') or 'unspecified'}. {v.get('notes','')}"})
    return rows


def view_context(room,view_id=None):
    if not view_id:return room
    if view_id not in room.get('camera_views',{}):raise ValueError('Choose a saved camera view belonging to this room.')
    return {**room,'_view_id':view_id}


def camera_for(plan,room):
    if room.get('_view_id'):
        return room['camera_views'][room['_view_id']]['camera']
    return plan.get('floor_cameras',{}).get(room['id'])


def selection_review_key(store, project, plan):
    import construction_scope as scope
    selection=scope.current(plan)
    if not selection:return None
    rooms=[r for r in project['rooms'] if r.get('plan_id')==plan['id'] and r.get('floor')==selection['floor'] and r.get('bbox') and scope.coverage(scope.room_polygon(r) or scope.box_polygon(r['bbox']),selection)>1e-7]
    return scope.digest([plan.get('sha256'),selection,plan.get('drawing'),plan.get('raster_revision'),plan.get('source_review'),plan.get('plan_reading'),[(r['id'],r.get('name'),r.get('floor'),r.get('bbox'),r.get('area_polygon')) for r in rooms]])


def selected_map_ready(store, project, room):
    import construction_scope as scope
    if not room.get('plan_id'):return False
    plan=store.asset(room['plan_id']);selection=scope.current(plan)
    if not selection or room.get('floor')!=selection['floor'] or not room.get('bbox'):return False
    if scope.coverage(scope.room_polygon(room) or scope.box_polygon(room['bbox']),selection)<.995:return False
    return bool(plan.get('selected_map_review') and plan['selected_map_review']['key']==selection_review_key(store,project,plan))


def map_ready(store,project,room):
    import construction_scope as scope
    if store and room.get('plan_id') and scope.required(store.asset(room['plan_id'])):
        return selected_map_ready(store,project,room)
    return bool(project.get('map_confirmed'))


def confirm_selected_map(store,project,plan_id):
    import construction_scope as scope
    from store import now
    if plan_id not in project['floor_plans']:raise ValueError('Choose a plan in this project.')
    plan=store.asset(plan_id);selection=scope.current(plan)
    if not selection:raise ValueError('Confirm the construction selection first.')
    rooms=[]
    for r in project['rooms']:
        if r.get('plan_id')!=plan_id or r.get('floor')!=selection['floor'] or not r.get('bbox'):continue
        covered=scope.coverage(scope.room_polygon(r) or scope.box_polygon(r['bbox']),selection)
        if covered<=1e-7:continue
        if covered<.995:raise ValueError('The selection cuts through '+r['name']+'. Adjust or review that room boundary first.')
        if not r.get('name','').strip() or r.get('floor')!=selection['floor']:raise ValueError('Assign a name and the selected floor to every included room.')
        rooms.append(r)
    if not rooms:raise ValueError('Mark at least one room inside the selection.')
    for f in plan.get('plan_reading',{}).get('features',[]):
        if f.get('review_status')=='rejected' or f.get('floor') not in ('',None,selection['floor']):continue
        poly=f.get('polygon') or (scope.box_polygon(f['bbox']) if f.get('bbox') else None)
        if not poly or scope.coverage(poly,selection)>1e-7:
            if f.get('review_status')!='confirmed' or f.get('kind')=='unknown':raise ValueError('Resolve uncertain architectural observations inside the selection first.')
    # Shared-floor readiness still validates supported walls, curves and raster
    # completeness before generation. This approval does not approve other rooms.
    plan['selected_map_review']={'key':selection_review_key(store,project,plan),'room_ids':[r['id'] for r in rooms],'updated':now()}
    store.save();return plan['selected_map_review']
