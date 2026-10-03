"""Surface-design bridge shared by draft previews and image input preparation.

No Store writes, network access, job submission or model loading. Editor visibility
is presentation state, never permission to omit physical objects from generation.
"""
import base64, copy, hashlib, json
from pathlib import Path
import surface_design


def design_for(plan, floor=None):
    drawing=plan.get('drawing',{})
    raw=drawing.get('surface_design')
    if not raw:return None
    bound=drawing.get('surface_design_floor')
    if floor is not None and bound != floor:
        if bound is None:raise ValueError('Surface design needs an explicit floor assignment before generation.')
        return None
    d=surface_design.validate(raw)
    d.pop('hidden_categories',None);d.pop('show_ceiling',None)
    return d


def identity(plan, floor=None):
    d=design_for(plan,floor)
    return compact(d) if d else None


def compact(value):
    if isinstance(value,list):return [compact(v) for v in value]
    if not isinstance(value,dict):return value
    out={k:compact(v) for k,v in value.items() if k!='image'}
    if value.get('image'):
        raw=base64.b64decode(value['image'].split(',',1)[1],validate=True)
        out['image_identity']={'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw),'preview_only':True}
    return out


def document(plan, floor, mpp, height):
    design=design_for(plan,floor)
    return {'features':plan.get('drawing',{}).get('features',[]),'calibration':{'metres_per_pixel':mpp},'wall_height_m':height,'surface_design':design}


def augment(scene, plan, room):
    d=document(plan,room['floor'],scene['model_scale']['metres_per_pixel'],scene['height'])
    if not d['surface_design']:return
    origin=[scene['bounds'][0]*plan['width'],scene['bounds'][1]*plan['height']]
    design=d['surface_design'];records=[]
    issues=[]
    for s in design['surfaces']:
        if surface_design.context(d,s) is None:issues.append('Surface '+s['id']+' has a missing wall host; attach it before preparing generation inputs.')
    by_id={s['id']:s for s in design['surfaces']}
    for item in design['items']:
        if item['surface_id'] not in by_id:
            issues.append('Design item '+item['id']+' has a missing surface host.');continue
        s=by_id[item['surface_id']];ctx=surface_design.context(d,s)
        if ctx is None:continue
        _,world=ctx
        pos=world(item['x'],item['y'],item.get('drop',0))
        records.append({**compact(item),'object_key':'design:item:'+item['id'],'surface_kind':s['kind'],
            'world_position_m':[pos[0]-origin[0]*d['calibration']['metres_per_pixel'],pos[1]-origin[1]*d['calibration']['metres_per_pixel'],pos[2]],
            'room_id':room['id'],'label':item.get('reference',{}).get('title') or item['kind'],'surface_design':True,
            'dimension_status':item.get('reference',{}).get('dimension_status','assumed'),
            'placement_basis':'surface-local metres; world position at mounting plane; depth/drop retained separately'})
    # Replace only the reference floor, never verified architecture. Explicit
    # voids remain absent; there is no infinite plane below the designed floor.
    if any(s['kind']=='floor' for s in design['surfaces']):scene['surfaces']=[f for f in scene['surfaces'] if not f['kind'].startswith('floor')]
    scene['surfaces']+=surface_design.mesh(d,origin)
    scene['products']+=records
    scene['surface_design']=identity(plan,room['floor'])
    scene['surface_design_issues']=issues
    scene['limits']+=['Surface design dimensions retain their recorded evidence status. Products are proxies and texture guides use saved preview images; exact appearance is not guaranteed. Editor hiding/cutaway does not omit generation objects.']


def prepare(plan, room, folder):
    """Materialize exact saved preview bytes and semantic input manifest."""
    design=design_for(plan,room['floor'])
    if not design:return None,[]
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True);refs=[]
    for kind,rows in [('surface',design['surfaces']),('item',design['items'])]:
        for row in rows:
            for role,r in [('product',row.get('reference',{})),('finish',row.get('finish',{}).get('reference',{}))]:
                if not r.get('image'):continue
                raw=base64.b64decode(r['image'].split(',',1)[1],validate=True);sha=hashlib.sha256(raw).hexdigest()
                ext={'png':'png','jpeg':'jpg','webp':'webp'}[r['image'].split(';')[0].split('/')[1]]
                path=folder/('surface-reference-'+sha+'.'+ext)
                path.write_bytes(raw)
                refs.append({'id':f'design:{kind}:{row["id"]}:{role}','path':str(path),'sha256':sha,
                    'category':row.get('kind','surface')+' '+role,'design_target':f'{kind}:{row["id"]}',
                    'placement':f'Only {role} for {kind} {row["id"]}; use its saved surface placement and dimensions.',
                    'reference':compact(r),'preview_only':True})
    info={'version':1,'floor':room['floor'],'design':identity(plan,room['floor']),
          'references':[{k:v for k,v in r.items() if k!='path'}|{'file':Path(r['path']).name} for r in refs],
          'units':'item placement and dimensions in metres; boundaries in original source pixels',
          'scope':'Saved design intent and preview references; not measured product fidelity. Links are metadata, not downloaded product images.',
          'visibility':'All physical items included, independent of editor visibility/cutaway.'}
    (folder/'surface-design-inputs.json').write_text(json.dumps(info,indent=2))
    return info,refs


def instruction(info):
    if not info:return ''
    return '\nSURFACE DESIGN: Use the following physical surface assignments, local metre dimensions, materials and item placements at the matching guide geometry. Preserve their evidence status; do not add a room from reference photos. '+json.dumps(info['design'],ensure_ascii=False)
