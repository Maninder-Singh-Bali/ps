"""Shared scene identity and explicit spatial edit boundaries for local models."""
from pathlib import Path
import copy
import hashlib
import json
import math
from PIL import Image, ImageDraw, ImageFilter


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def file_identity(store, aid):
    if not aid:
        return None
    a = store.asset(aid)
    actual = hashlib.sha256(Path(a['path']).read_bytes()).hexdigest()
    if a.get('sha256') and actual != a['sha256']:
        raise ValueError('A source file changed on disk. Upload that version again before generation or approval.')
    return {'id': aid, 'sha256': actual}


def clean_control(store, project, room, data):
    mode = data.get('mode', 'reference')
    if mode not in ('reference', 'structure', 'region'):
        raise ValueError('Choose reference guidance, preserve structure, or a selected area.')
    if mode == 'reference':
        return {'mode': mode}
    source = data.get('source_id') or room.get('anchor_id')
    a = store.asset(source)
    if a.get('project_id') != project['id'] or a.get('room_id') != room['id']:
        raise ValueError('Choose a master image belonging to this room.')
    if source != room.get('anchor_id') and (source not in room['images'] or a.get('kind') != 'image'):
        raise ValueError('Choose the room reference or a generated image from this room to refine.')
    with Image.open(a['path']) as im:
        if im.size != (1920, 1080):
            raise ValueError('Protected edits need a 1920 × 1080 master. This mode never enlarges a smaller source.')
    out = {'mode': mode, 'source_id': source, 'instruction': str(data.get('instruction', '')).strip()[:2500]}
    reference_id = data.get('reference_id')
    if reference_id:
        if reference_id not in room.get('references', []):
            raise ValueError('Choose an assigned product reference from this room.')
        reference = store.asset(reference_id)
        if reference.get('project_id') != project['id'] or reference.get('room_id') != room['id'] or not reference.get('enabled', True):
            raise ValueError('The edit reference must be an enabled reference belonging to this room.')
        out['reference_id'] = reference_id
    strength = float(data.get('denoise', .5 if mode == 'structure' else 1.0))
    if not math.isfinite(strength) or strength not in (.25, .5, .75, 1.0):
        raise ValueError('Choose a supported edit strength.')
    out['denoise'] = strength
    if mode == 'region':
        out['context_crop'] = data.get('context_crop') is True
        out['masked_context'] = data.get('masked_context') is True
        box = data.get('region')
        if not isinstance(box, list) or len(box) != 4 or not all(isinstance(v, (float, int)) and math.isfinite(v) for v in box):
            raise ValueError('Draw an edit area on the room image.')
        x, y, w, h = box
        if min(x, y) < 0 or min(w, h) < .01 or x+w > 1.000001 or y+h > 1.000001:
            raise ValueError('Keep the edit area inside the room image.')
        out['region'] = [float(v) for v in box]
        out['feather'] = 16
        points=data.get('mask_polygon')
        if points:
            if not isinstance(points,list) or not 3<=len(points)<=100 or any(not isinstance(p,list) or len(p)!=2 or any(not isinstance(v,(int,float)) or not math.isfinite(v) for v in p) or not (x<=p[0]<=x+w and y<=p[1]<=y+h) for p in points):
                raise ValueError('Draw an object outline inside the edit area, with at least three points.')
            area=abs(sum(p[0]*q[1]-q[0]*p[1] for p,q in zip(points,points[1:]+points[:1])))/2
            if area<.00001:raise ValueError('The object outline has no usable area.')
            out['mask_polygon']=copy.deepcopy(points)
        crop=data.get('reference_crop')
        if crop:
            if not reference_id or not isinstance(crop,list) or len(crop)!=4 or any(not isinstance(v,(int,float)) or not math.isfinite(v) for v in crop) or min(crop[:2])<0 or min(crop[2:])<=0 or crop[0]+crop[2]>1 or crop[1]+crop[3]>1:
                raise ValueError('Keep the product crop inside its selected reference.')
            out['reference_crop']=list(crop)
        if not out['instruction']:
            raise ValueError('Describe the change to make inside the selected area.')
    return out


def scene_snapshot(store, project, room):
    from interior_style import camera_for
    plan = store.asset(room['plan_id']) if room.get('plan_id') else {}
    drawing = plan.get('drawing', {})
    refs = [store.asset(aid) for aid in room['references'] if store.asset(aid).get('enabled', True)]
    control = room.get('scene_control', {'mode': 'reference'})
    content = {
        'project_id': project['id'], 'room_id': room['id'], 'room_revision': room['revision'],
        'seed': project['seed'], 'style': project['style'],
        'room': {k: copy.deepcopy(room.get(k)) for k in ('name', 'floor', 'kind', 'bbox', 'area_polygon', 'notes', 'furniture_layout', 'block_layout')},
        'anchor': file_identity(store, room.get('anchor_id')),
        'plan': file_identity(store, room.get('plan_id')),
        'drawing': {k: copy.deepcopy(drawing.get(k)) for k in ('edits', 'features', 'site')},
        'construction_selection': copy.deepcopy(plan.get('construction_selection')),
        'construction_selection_revision': plan.get('construction_selection_revision',0),
        'plan_reading': copy.deepcopy(plan.get('plan_reading', {})),
        'floor_camera': copy.deepcopy(camera_for(plan,room)),
        'floor_sections': [{k:copy.deepcopy(r.get(k)) for k in ('id','floor','bbox','area_polygon','furniture_layout','block_layout','references')} for r in project['rooms'] if r.get('plan_id')==room.get('plan_id') and r.get('floor')==room.get('floor')],
        'floor_products': [{**file_identity(store,aid),'enabled':store.asset(aid).get('enabled',True),'category':store.asset(aid).get('category')} for r in project['rooms'] if r.get('plan_id')==room.get('plan_id') and r.get('floor')==room.get('floor') for aid in r.get('references',[])],
        'measurements': [{k: copy.deepcopy(v) for k,v in m.items() if k!='updated'} for m in project.get('measurements',[]) if m.get('plan_id')==room.get('plan_id') and m.get('floor')==room.get('floor')],
        'products': [{**file_identity(store, a['id']), 'category': a.get('category'), 'placement': a.get('placement')} for a in refs],
    }
    from surface_inputs import identity
    design=identity(plan,room.get('floor'))
    if design:content['surface_design']=design
    if plan.get('raster_geometry'):
        content['raster_geometry']={k:copy.deepcopy(plan['raster_geometry'].get(k)) for k in ('source_sha256','pipeline_key','walls','uncertain_spans','openings','regions')}
        content['raster_corrections']=copy.deepcopy(plan.get('raster_corrections',{}))
    if room.get('surfaces'):content['surfaces']=copy.deepcopy(room['surfaces'])
    if room.get('_view_id'):content['view_id']=room['_view_id']
    return {'version': 2, 'fingerprint': digest(content), 'content': content}


def revision_matches(room, revision):
    return revision == room['revision'] or revision in room.get('edit_revision_equivalents',[])


def semantic_content(content):
    return {k:v for k,v in content.items() if k not in ('master','control','room_revision')}


def restore_edit_lineage(store):
    """Conservative legacy repair: every intervening revision must be a recorded
    control-only step, with identical scene evidence. Gaps/scene changes stop it.
    No output status, approval, scene record or historical manifest is changed.
    """
    from interior_style import view_context
    for project in store.db['projects'].values():
        for room in project['rooms']:
            records={}
            for job in store.db['jobs'].values():
                snap=job.get('scene_manifest',{})
                c=snap.get('content',{})
                if job.get('room_id')==room['id'] and job.get('kind')=='image' and snap.get('version')==1 and c.get('control'):
                    records.setdefault(c['room_revision'],[]).append(c)
            current=room['revision']; aliases=[];proof=[]
            # Do not bridge unrecorded revisions or multiple inconsistent snapshots.
            while current in records and current-1 in records:
                after,before=records[current],records[current-1]
                if len(after)!=1 or len(before)!=1:break
                a,b=after[0],before[0]
                if a['control']==b['control'] or semantic_content(a)!=semantic_content(b):break
                try:
                    live=scene_snapshot(store,project,view_context(room,a.get('view_id')))
                    if semantic_content(live['content'])!=semantic_content(a):break
                    for c in (a,b):
                        if c.get('master')!=file_identity(store,c['control'].get('source_id')):raise ValueError('Master changed')
                except (ValueError,OSError,KeyError):break
                aliases.append(current-1);proof.append({'from':current-1,'to':current,'scene':digest(semantic_content(a))});current-=1
            if aliases:
                room['edit_revision_equivalents']=aliases
                room['edit_revision_audit']={'method':'contiguous recorded control-only revisions','steps':proof}


def assert_edit(room, job):
    expected=job.get('edit_ticket')
    if expected is not None and expected!=room.get('scene_control',{'mode':'reference'}):
        raise ValueError('Edit settings changed during generation. The output cannot replace the requested edit.')


def assert_scene(store, project, room, expected):
    if expected and expected.get('content',{}).get('view_id'):
        from interior_style import view_context
        room=view_context(room,expected['content']['view_id'])
    current = scene_snapshot(store, project, room)
    if expected and (not revision_matches(room,expected['content']['room_revision']) or semantic_content(expected['content']) != semantic_content(current['content'])):
        raise ValueError('The master scene or references changed. Generate a new version from the current room before continuing.')
    return current


def save_manifest(job, folder, scene, **extra):
    record = {**copy.deepcopy(scene), **extra}
    job['scene_manifest'] = record
    (Path(folder) / 'scene-manifest.json').write_text(json.dumps(record, indent=2), encoding='utf-8')
    return record


def padded_image(graph, node_id, source):
    graph[node_id] = {'class_type': 'ImagePadForOutpaint', 'inputs': {
        'image': source, 'left': 0, 'right': 0, 'top': 4, 'bottom': 4, 'feathering': 0}}
    return [node_id, 0]


def region_pixels(control):
    x, y, w, h = control['region']
    left, top = int(x*1920), int(y*1080)
    right, bottom = min(1920, math.ceil((x+w)*1920)), min(1080, math.ceil((y+h)*1080))
    return left, top, right-left, bottom-top


def object_mask(control):
    """Full-resolution mask; blur remains strictly inside the selected bounds."""
    x,y,w,h=region_pixels(control)
    local=Image.new('L',(w,h))
    if control.get('mask_polygon'):
        ImageDraw.Draw(local).polygon([(round(px*1920)-x,round(py*1080)-y) for px,py in control['mask_polygon']],fill=255)
        local=local.filter(ImageFilter.GaussianBlur(3))
    else:
        # Feather inward so no pixel beyond the confirmed region can change.
        import numpy as np
        yy,xx=np.mgrid[:h,:w];edge=max(1,min(control.get('feather',16),w//4,h//4))
        local=Image.fromarray((255*np.clip(np.minimum.reduce([xx,yy,w-1-xx,h-1-yy])/edge,0,1)).astype('uint8'))
    result=Image.new('L',(1920,1088));result.paste(local,(x,y+4));return result


def mask_context_graph(graph,control,mask_name):
    """Same object mask feeds noise masking and compositing; references stay global.
    This is latent masking on the installed model, not a trained inpaint model.
    """
    meta=focus_surface_graph(graph,control);left,top,cw,ch=meta['context']
    graph['340']={'class_type':'LoadImage','inputs':{'image':mask_name}}
    graph['341']={'class_type':'ImageToMask','inputs':{'image':['340',0],'channel':'red'}}
    graph['342']={'class_type':'CropMask','inputs':{'mask':['341',0],'x':left,'y':top,'width':cw,'height':ch}}
    graph['343']={'class_type':'VAEEncode','inputs':{'pixels':['320',0],'vae':['3',0]}}
    graph['344']={'class_type':'SetLatentNoiseMask','inputs':{'samples':['343',0],'mask':['342',0]}}
    graph['345']={'class_type':'SplitSigmasDenoise','inputs':{'sigmas':['19',0],'denoise':control['denoise']}}
    graph['21']['inputs'].update(latent_image=['344',0],sigmas=['345',1])
    graph['330']['inputs']['mask']=['342',0]
    meta.update(method='native context with object-shaped latent noise mask and protected composite',sampler_mask=True,reference_spatial_binding=False)
    return meta


def protect_graph(graph, control):
    """Seed the output with native source latents; spatial edits also copy the untouched exterior."""
    source = padded_image(graph, '300', ['4', 0])
    graph['301'] = {'class_type': 'VAEEncode', 'inputs': {'pixels': source, 'vae': ['3', 0]}}
    graph['302'] = {'class_type': 'SplitSigmasDenoise', 'inputs': {'sigmas': ['19', 0], 'denoise': control['denoise']}}
    graph['21']['inputs'].update(latent_image=['301', 0], sigmas=['302', 1])
    graph['10']['inputs']['pixels'] = source
    if control['mode'] != 'region':
        return
    x, y, w, h = region_pixels(control)
    for key, width, height, value in [('303', 1920, 1088, 0.0), ('304', w, h, 1.0)]:
        graph[key] = {'class_type': 'SolidMask', 'inputs': {'width': width, 'height': height, 'value': value}}
    edge = min(control['feather'], w//4, h//4)
    graph['305'] = {'class_type': 'FeatherMask', 'inputs': {'mask': ['304', 0], 'left': edge, 'right': edge, 'top': edge, 'bottom': edge}}
    graph['306'] = {'class_type': 'MaskComposite', 'inputs': {'destination': ['303', 0], 'source': ['305', 0], 'x': x, 'y': y+4, 'operation': 'add'}}
    graph['307'] = {'class_type': 'SetLatentNoiseMask', 'inputs': {'samples': ['301', 0], 'mask': ['306', 0]}}
    graph['21']['inputs']['latent_image'] = ['307', 0]
    graph['308'] = {'class_type': 'ImageCompositeMasked', 'inputs': {'destination': source, 'source': ['22', 0], 'x': 0, 'y': 0, 'resize_source': False, 'mask': ['306', 0]}}
    graph['23']['inputs']['image'] = ['308', 0]
    graph['25']['inputs']['images'] = ['308', 0]


def focus_surface_graph(graph,control):
    """Resolve tiny surface edits in a native-pixel context tile, with no resizing."""
    x,y,w,h=region_pixels(control)
    cw=min(1920,max(512,math.ceil((w+128)/16)*16));ch=min(1088,max(512,math.ceil((h+128)/16)*16))
    left=max(0,min(1920-cw,math.floor((x-(cw-w)/2)/16)*16))
    top=max(0,min(1088-ch,math.floor((y+4-(ch-h)/2)/16)*16))
    graph['320']={'class_type':'ImageCrop','inputs':{'image':['300',0],'x':left,'y':top,'width':cw,'height':ch}}
    graph['321']={'class_type':'SolidMask','inputs':{'width':cw,'height':ch,'value':0.0}}
    graph['326']={'class_type':'MaskComposite','inputs':{'destination':['321',0],'source':['305',0],'x':x-left,'y':y+4-top,'operation':'add'}}
    graph['330']={'class_type':'ImageCompositeMasked','inputs':{'destination':['300',0],'source':['22',0],'x':left,'y':top,'resize_source':False,'mask':['326',0]}}
    graph['10']['inputs']['pixels']=['320',0]
    graph['19']['inputs'].update(width=cw,height=ch)
    graph['20']['inputs'].update(width=cw,height=ch)
    graph['21']['inputs'].update(latent_image=['20',0],sigmas=['19',0])
    graph['23']['inputs']['image']=['330',0];graph['25']['inputs']['images']=['330',0]
    for key in ('301','302','303','306','307','308'):graph.pop(key,None)
    return {'method':'native-pixel context crop and protected composite','context':[left,top,cw,ch],'selected_region':[x,y,w,h],'output':[1920,1080],'resized':False,'scope':'Only the selected patch is newly generated; the surrounding native1080 photograph is copied exactly.'}

def check_protected_output(source, result, control):
    """Pixel comparison of unchanged exterior; not an object recognition/placement claim."""
    import numpy as np
    a = np.array(Image.open(source).convert('RGB'), dtype=np.int16)
    b = np.array(Image.open(result).convert('RGB'), dtype=np.int16)
    if a.shape != b.shape:
        raise ValueError('Protected output dimensions changed.')
    x, y, w, h = region_pixels(control)
    outside = np.ones(a.shape[:2], dtype=bool)
    outside[y:y+h, x:x+w] = False
    if control.get('masked_context'):
        outside=np.array(object_mask(control))[4:1084,:]==0
    diff = np.abs(a-b)
    changed = int(np.count_nonzero(np.any(diff[outside] != 0, axis=1)))
    return {'outside_pixels': int(outside.sum()), 'changed_outside_pixels': changed,
            'max_outside_channel_difference': int(diff[outside].max()) if outside.any() else 0,
            'inside_mean_channel_change': round(float(diff[~outside].mean()), 4),
            'outside_exact_match': changed == 0,
            'scope': 'Unchanged image exterior only. Edited objects, placement and video motion still require review.'}
