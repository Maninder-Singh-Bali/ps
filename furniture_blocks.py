"""Editable furniture proxies. Guesses stay drafts; source plans are never changed."""
import copy, math, uuid
from store import editing_busy
from urllib.parse import urlsplit
from scene_control import digest
from plan_preflight import inside

KINDS={'sofa','chair','table','bed','storage','refrigerator','comforter','pillar','fixture','appliance','desk','plant','rug','stair','light','decor','unknown'}

def basis(store,room):
    p=store.asset(room['plan_id'])
    project=store.project(p['project_id'])
    return digest({'plan':p['id'],'drawing':p.get('drawing'), 'study':p.get('plan_reading'),
                   'scale':[m for m in project.get('measurements',[]) if m.get('plan_id')==p['id'] and m.get('floor')==room['floor']],
                   'bbox':room.get('bbox'),'polygon':room.get('area_polygon')})

def clean(items):
    if not isinstance(items,list) or len(items)>40:raise ValueError('Use up to 40 furniture blocks per section.')
    out=[];ids=set()
    for v in items:
        if not isinstance(v,dict):raise ValueError('Invalid furniture block.')
        key=str(v.get('id',''))
        if not key or len(key)>64 or key in ids:raise ValueError('Each block needs a unique ID.')
        ids.add(key);kind=v.get('kind','unknown')
        if kind not in KINDS:raise ValueError('Choose a furniture type.')
        row={'id':key,'kind':kind,'label':str(v.get('label') or kind.title())[:100]}
        for field in ('x','y','width','depth','angle'):
            n=v.get(field)
            if type(n) not in (int,float) or not math.isfinite(n):raise ValueError('Enter valid block sizes and positions.')
            row[field]=float(n)
        if not all(0<=row[k]<=1 for k in ('x','y')) or not all(.005<=row[k]<=1 for k in ('width','depth')):raise ValueError('Block positions and proportions must fit the plan.')
        row['angle']%=360
        for axis in ('flip_x','flip_y'):
            if type(v.get(axis,False)) is not bool:raise ValueError('Invalid mirror setting.')
            row[axis]=v.get(axis,False)
        seats=v.get('seat_count')
        if seats is not None and (type(seats)!=int or not 1<=seats<=12):raise ValueError('Seat count must be a whole number between 1 and 12, or unknown.')
        row['seat_count']=seats if kind=='sofa' else None
        row['asset_id']=str(v['asset_id']) if v.get('asset_id') else None
        row['prompt']=str(v.get('prompt',''))[:2000]
        product_url=v.get('product_url','')
        if not isinstance(product_url,str):raise ValueError('Enter a valid product URL.')
        product_url=product_url.strip()
        if product_url:
            try:
                parsed=urlsplit(product_url)
                valid=parsed.scheme in ('https','http') and parsed.hostname and not parsed.username and not parsed.password
            except ValueError:valid=False
            if not valid or len(product_url)>4096 or any(c.isspace() or ord(c)<32 for c in product_url):raise ValueError('Enter a complete product URL starting with https:// or http://.')
        row['product_url']=product_url
        row['source']=str(v.get('source','manual'))[:40]
        row['shape']=v.get('shape') if v.get('shape') in ('l','round') else 'box'
        row['return_side']='right' if v.get('return_side')=='right' else 'left'
        row['preset_id']=str(v.get('preset_id',''))[:60]
        module=v.get('sofa_modules')
        if module is not None and kind=='sofa' and row['shape']!='round':
            keys=('main_seats','return_seats','leg_width','leg_depth','pitch_width','pitch_depth')
            if not isinstance(module,dict) or any(type(module.get(k)) not in (int,float) or not math.isfinite(module[k]) for k in keys):raise ValueError('Invalid sofa seat modules.')
            m={k:module[k] for k in keys};is_l=row['shape']=='l'
            if type(m['main_seats'])!=int or type(m['return_seats'])!=int or m['main_seats']<(2 if is_l else 1) or m['return_seats']<(1 if is_l else 0) or (not is_l and m['return_seats']!=0) or m['main_seats']+m['return_seats']>12:raise ValueError('Use up to 12 sofa seats.')
            if any(not 0<m[k]<=1 for k in keys[2:]):raise ValueError('Invalid sofa module dimensions.')
            expected_w=(m['leg_width']+(m['main_seats']-1)*m['pitch_width']) if is_l else m['main_seats']*m['pitch_width']
            expected_d=m['leg_depth']+m['return_seats']*m['pitch_depth'] if is_l else m['leg_depth']
            if not math.isclose(row['width'],expected_w,abs_tol=1e-8) or not math.isclose(row['depth'],expected_d,abs_tol=1e-8):raise ValueError('Sofa dimensions must match its seat modules.')
            row['sofa_modules']=m;row['seat_count']=m['main_seats']+m['return_seats']
        chairs=v.get('chair_modules')
        if chairs is not None and kind=='chair':
            if not isinstance(chairs,dict) or any(type(chairs.get(k))!=int or chairs[k]<1 for k in ('columns','rows')) or chairs['columns']*chairs['rows']>40:raise ValueError('Use between 1 and 40 chairs per group.')
            if any(type(chairs.get(k)) not in (int,float) or not math.isfinite(chairs[k]) or not 0<chairs[k]<=1 for k in ('width','depth')):raise ValueError('Invalid individual chair size.')
            if any(not math.isclose(row[k],chairs[k]*(chairs[n]*1.15-.15),abs_tol=1e-8) for k,n in [('width','columns'),('depth','rows')]):raise ValueError('Chair group dimensions must match its rows and columns.')
            row['chair_modules']={k:chairs[k] for k in ('columns','rows','width','depth')}
        if 'height_m' in v:
            h=v['height_m']
            if type(h) not in (int,float) or not math.isfinite(h) or not .01<=h<=5:raise ValueError('Furniture height must be between 0.01 and 5 metres.')
            row['height_m']=float(h)
        if 'elevation_m' in v:
            h=v['elevation_m']
            if type(h) not in (int,float) or not math.isfinite(h) or not 0<=h<=5:raise ValueError('Mounting height must be between 0 and 5 metres.')
            row['elevation_m']=float(h)
        size=v.get('physical_size')
        if size:
            if not isinstance(size,dict) or any(type(size.get(k)) not in (int,float) or not math.isfinite(size[k]) or not 0<size[k]<100 for k in ('width','depth')):raise ValueError('Enter valid furniture width and depth in metres.')
            row['physical_size']={'width':size['width'],'depth':size['depth'],'unit':'m'}
        out.append(row)
    return out

def corners(item,plan):
    # Rotation happens in source-pixel coordinates, not distorted normalized space.
    w,h=plan['width'],plan['height'];a=math.radians(item['angle']);c,s=math.cos(a),math.sin(a)
    return [[item['x']+(x*c-y*s)/w,item['y']+(x*s+y*c)/h]
            for x,y in [(-item['width']*w/2,-item['depth']*h/2),(item['width']*w/2,-item['depth']*h/2),(item['width']*w/2,item['depth']*h/2),(-item['width']*w/2,item['depth']*h/2)]]

def parts(item,plan):
    m=item.get('chair_modules')
    if item['kind']=='chair' and m:
        a=math.radians(item['angle']);c,s=math.cos(a),math.sin(a);result=[]
        for row in range(m['rows']):
            for col in range(m['columns']):
                x=(-item['width']/2+m['width']/2+col*m['width']*1.15)*plan['width']
                y=(-item['depth']/2+m['depth']/2+row*m['depth']*1.15)*plan['height']
                unit={**item,'chair_modules':None,'width':m['width'],'depth':m['depth'],'x':item['x']+(x*c-y*s)/plan['width'],'y':item['y']+(x*s+y*c)/plan['height']}
                result.extend(parts(unit,plan))
        return result
    if item.get('shape')=='round':
        angle=math.radians(item['angle']);c,s=math.cos(angle),math.sin(angle)
        points=[]
        for i in range(32):
            t=i*2*math.pi/32;x=math.cos(t)*item['width']*plan['width']/2;y=math.sin(t)*item['depth']*plan['height']/2
            points.append([item['x']+(x*c-y*s)/plan['width'],item['y']+(x*s+y*c)/plan['height']])
        return [points]
    stair_l=item.get('preset_id')=='staircase-l'
    if item.get('shape')!='l' and not stair_l:return [corners(item,plan)]
    # Two joined cuboids are ONE logical product. The inner corner remains empty.
    W=item['width']*plan['width'];D=item['depth']*plan['height'];angle=math.radians(item['angle']);c,s=math.cos(angle),math.sin(angle)
    m=item.get('sofa_modules',{});lw=m.get('leg_width',item['width']*.4)*plan['width'];ld=m.get('leg_depth',item['depth']*.4)*plan['height']
    rectangles=[(-W/2,D/2-ld,W/2,D/2)]
    rectangles.append((W/2-lw,-D/2,W/2,D/2-ld) if item.get('return_side')=='right' else (-W/2,-D/2,-W/2+lw,D/2-ld))
    if stair_l:rectangles=[(-W/2,-D/2,W/2,-D/2+D*.28),(-W/2,-D/2+D*.28,-W/2+W*.48,D/2)]
    fx=-1 if item.get('flip_x') else 1;fy=-1 if item.get('flip_y') else 1
    return [[[item['x']+(x*fx*c-y*fy*s)/plan['width'],item['y']+(x*fx*s+y*fy*c)/plan['height']] for x,y in [(l,t),(r,t),(r,b),(l,b)]] for l,t,r,b in rectangles]

def overlap(a,b):
    for poly in (a,b):
        for p,q in zip(poly,poly[1:]+poly[:1]):
            axis=[q[1]-p[1],p[0]-q[0]]
            one=[v[0]*axis[0]+v[1]*axis[1] for v in a];two=[v[0]*axis[0]+v[1]*axis[1] for v in b]
            if min(max(one),max(two))-max(min(one),min(two))<=1e-10:return False
    return True

def checks(store,room,items,architecture=None):
    plan=store.asset(room['plan_id']);b=room['bbox'];poly=room.get('area_polygon') or [[b[0],b[1]],[b[0]+b[2],b[1]],[b[0]+b[2],b[1]+b[3]],[b[0],b[1]+b[3]]]
    from drawing_scene import load,cut_walls
    if architecture is None:architecture=cut_walls(load(store,plan)[0])
    expanded=[(v,part) for v in items for part in parts(v,plan)];issues=[]
    def add(item,msg):issues.append({'id':item['id'],'message':item['label']+': '+msg})
    for item,foot in expanded:
        # Sample edges as well as vertices for concave section boundaries.
        samples=[[(p[0]*(10-i)+q[0]*i)/10,(p[1]*(10-i)+q[1]*i)/10] for p,q in zip(foot,foot[1:]+foot[:1]) for i in range(11)]
        if any(not inside(p,poly) for p in samples):add(item,'extends outside the section boundary.')
        for line in architecture:
            if line['kind'] not in ('wall','door','window','sliding_door'):continue
            pts=[[v[0]/plan['width'],v[1]/plan['height']] for v in line['points']]
            # Exact convex segment clipping catches even short crossings.
            from plan_health import cut_interval
            a=math.radians(-item['angle']);c,s=math.cos(a),math.sin(a)
            local=[]
            for x,y in pts:
                x=(x-item['x'])*plan['width'];y=(y-item['y'])*plan['height'];local.append([x*c-y*s,x*s+y*c])
            local_foot=[]
            for x,y in foot:
                x=(x-item['x'])*plan['width'];y=(y-item['y'])*plan['height'];local_foot.append([x*c-y*s,x*s+y*c])
            box=[min(p[0] for p in local_foot),min(p[1] for p in local_foot),max(p[0] for p in local_foot),max(p[1] for p in local_foot)]
            if cut_interval(local,box):add(item,'crosses a mapped '+line['kind'].replace('_',' ')+'.')
        for feature in plan.get('plan_reading',{}).get('features',[]):
            if feature.get('review_status')!='confirmed' or feature.get('floor') not in (None,'',room['floor']):continue
            if feature.get('kind') not in ('door','sliding_door','window','stair','space'):continue
            if feature['kind']=='space' and not feature.get('connection_room_id'):continue
            x,y,w,h=feature['bbox'];zone=[[x,y],[x+w,y],[x+w,y+h],[x,y+h]]
            if overlap(foot,zone):add(item,'overlaps '+feature.get('label',feature['kind'])+'; check access and clearance.')
    for i,(item,a) in enumerate(expanded):
        for other,b in expanded[i+1:]:
            low=max(item.get('elevation_m',0),other.get('elevation_m',0))
            high=min(v.get('elevation_m',0)+v.get('height_m',.45 if v['kind']=='table' else .8) for v in (item,other))
            if high-low<=1e-6:continue
            if 'rug' in (item['kind'],other['kind']) or {item['kind'],other['kind']}=={'bed','comforter'}:continue
            if item['id']!=other['id'] and overlap(a,b):add(item,'overlaps '+other['label']+'.')
    return list({(v['id'],v['message']):v for v in issues}.values())

def proposals(store,room,include_unknown=True):
    plan=store.asset(room['plan_id']);b=room['bbox'];out=[]
    features=plan.get('plan_reading',{}).get('features',[])+plan.get('vision_report',{}).get('features',[])
    for f in features:
        if f.get('kind')!='furniture' or f.get('review_status')=='rejected' or f.get('location_unresolved') or f.get('floor') not in ('',None,room['floor']):continue
        x,y,w,h=f['bbox'];cx=x+w/2;cy=y+h/2
        if not (b[0]<=cx<=b[0]+b[2] and b[1]<=cy<=b[1]+b[3]) or w*h>.65*b[2]*b[3]:continue
        if any(abs(v['x']-cx)<w*.3 and abs(v['y']-cy)<h*.3 for v in out):continue
        kind=f.get('object_type','unknown');kind=kind if kind in KINDS else 'unknown'
        if kind=='unknown' and not include_unknown:continue
        out.append({'id':uuid.uuid4().hex[:16],'kind':kind,'label':f.get('label','Uncertain furniture'),'seat_count':f.get('seat_count') if kind=='sofa' else None,'x':cx,'y':cy,'width':w,'depth':h,'angle':0})
    if include_unknown:
        from block_scan import scan
        for item in scan(plan,room):
            if any(abs(v['x']-item['x'])<(v['width']+item['width'])*.4 and abs(v['y']-item['y'])<(v['depth']+item['depth'])*.4 for v in out):continue
            out.append(item)
    return clean(out[:40])

def suggest(store,room,items,key):
    selected=next((i for i,v in enumerate(items) if v['id']==key),None)
    if selected is None:raise ValueError('Select a furniture block first.')
    original=items[selected];others=items[:selected]+items[selected+1:];b=room['bbox']
    candidates=[]
    for angle in dict.fromkeys((original['angle'],0,90,180,270)):
        for iy in range(1,16):
            for ix in range(1,16):
                v={**original,'x':b[0]+ix*b[2]/16,'y':b[1]+iy*b[3]/16,'angle':angle}
                dist=((v['x']-original['x'])/b[2])**2+((v['y']-original['y'])/b[3])**2
                candidates.append((dist+(0 if angle==original['angle'] else .03),v))
    # Only test the selected object against others; existing conflicts remain visible.
    from drawing_scene import load,cut_walls
    architecture=cut_walls(load(store,store.asset(room['plan_id']))[0])
    base={v['message'] for v in checks(store,room,others,architecture)}
    for _,v in sorted(candidates,key=lambda row:row[0]):
        issues=checks(store,room,others+[v],architecture)
        if all(row['message'] in base for row in issues):
            out=copy.deepcopy(items);out[selected]=v;return out
    raise ValueError('No clear position found at this size. Refine the room boundary, known openings or block dimensions.')

def drawing_draft(store,pid,rid,data):
    """Validate a shared drawing without changing the live project."""
    import drawing_editor
    room=store.room(pid,rid);doc=drawing_editor.get_document(store,pid,room['plan_id'])
    if not isinstance(data,dict) or data.get('revision')!=doc['revision'] or data.get('map_revision')!=doc['map_revision']:
        raise ValueError('The drawing changed. Reopen the plan before saving.')
    edits,features=drawing_editor.clean_changes(doc,data)
    # Only model scale is editable here; preserve location and sunlight.
    from scene_scale import clean_model
    site=copy.deepcopy(doc['site'])
    if 'model' in data.get('site',{}):site['model']=clean_model(data['site']['model'])
    return {**doc,'edits':edits,'features':features,'site':site}

def with_drawing_draft(store,pid,rid,drawing):
    staged=copy.copy(store);staged.db=copy.deepcopy(store.db);staged.save=lambda:None
    aid=store.room(pid,rid)['plan_id']
    staged.asset(aid)['drawing']={**staged.asset(aid).get('drawing',{}),**{k:drawing[k] for k in ('revision','base_asset_id','edits','features','site')}}
    return staged

def save_plan(store,pid,rid,data):
    """Validate every section before committing a multi-section editing session."""
    active=store.room(pid,rid);drafts=data.get('drafts')
    if not isinstance(drafts,list) or not 1<=len(drafts)<=100:raise ValueError('Choose the sections to save.')
    if editing_busy(store,pid):raise ValueError('Wait for the current activity before changing placement.')
    validated=[];seen=set()
    for draft in drafts:
        if not isinstance(draft,dict):raise ValueError('Invalid section draft.')
        key=draft.get('room_id');r=store.room(pid,key)
        if key in seen or r.get('plan_id')!=active.get('plan_id'):raise ValueError('Save each section once on the same plan.')
        seen.add(key)
        _, draft_items = validate_items(store,pid,key,draft)
        # Validation must not rebuild every floor's meshes for every section.
        result={'items':draft_items,'issues':checks(store,r,draft_items)}
        reviewed=draft.get('reviewed') is True and 'drawing' not in data
        if reviewed and result['issues']:raise ValueError(r['name']+': resolve flagged block conflicts before confirming placement.')
        if reviewed and any(v['kind']=='unknown' for v in result['items']):raise ValueError(r['name']+': identify unknown objects before confirming placement.')
        validated.append((r,result['items'],reviewed))
    if rid not in seen:raise ValueError('Include the active section when saving.')
    if 'drawing' in data:
        import drawing_editor
        drawing=drawing_draft(store,pid,rid,data['drawing'])
        # Export and validate on an isolated database. A failed render or block
        # check must never persist only half of the combined plan edit.
        staged=copy.copy(store);staged.db=copy.deepcopy(store.db);staged.save=lambda:None
        drawing_editor.save_document(staged,pid,active['plan_id'],drawing)
        next_data={k:copy.deepcopy(v) for k,v in data.items() if k!='drawing'}
        for draft in next_data['drafts']:
            draft['revision']=staged.room(pid,draft['room_id'])['revision']
            draft['reviewed']=False
        result=save_plan(staged,pid,rid,next_data)
        result['drawing']=drawing_editor.get_document(staged,pid,active['plan_id'])
        previous=store.db
        try:store.db=staged.db;store.save()
        except Exception:
            store.db=previous
            raise
        return result
    floors={r.get('floor') for r,_,_ in validated}
    for r,items,reviewed in validated:r['block_layout']={'items':items,'reviewed':reviewed,'basis':basis(store,r)}
    for r in store.project(pid)['rooms']:
        if r.get('plan_id')==active['plan_id'] and r.get('floor') in floors:store.invalidate(pid,r)
    store.save()
    result=request(store,pid,rid,{'action':'check','revision':active['revision'],'items':active['block_layout']['items']})
    result['saved_sections']=len(validated)
    return result

def validate_items(store,pid,rid,data):
    """Shared validation for previews and atomic multi-section saves."""
    room=store.room(pid,rid)
    if not room.get('plan_id') or not room.get('bbox'):raise ValueError('Map this section on the original plan first.')
    if data.get('revision')!=room['revision']:raise ValueError('The section changed. Reopen Furniture blocks.')
    items=clean(data.get('items',[]));linked=set()
    for item in items:
        aid=item.get('asset_id')
        if not aid:continue
        if aid not in room.get('references',[]):raise ValueError('Choose a furniture reference uploaded to this section.')
        if aid in linked:raise ValueError('This image is already assigned to another block. Add another copy for another furniture instance.')
        linked.add(aid)
    return room,items


def request(store,pid,rid,data):
    if data.get('action')=='save-plan':return save_plan(store,pid,rid,data)
    if 'drawing' in data:
        if data.get('action') not in ('check','suggest','propose'):raise ValueError('Save walls and furniture together with Save plan.')
        drawing=drawing_draft(store,pid,rid,data['drawing'])
        staged=with_drawing_draft(store,pid,rid,drawing)
        return request(staged,pid,rid,{k:v for k,v in data.items() if k!='drawing'})
    room,items=validate_items(store,pid,rid,data)
    action=data.get('action','check')
    if action=='propose':items=proposals(store,room,include_unknown=data.get('automatic') is not True)
    elif action=='suggest':items=suggest(store,room,items,data.get('selected'))
    elif action not in ('check','save'):raise ValueError('Unknown furniture-block action.')
    issues=checks(store,room,items)
    if action=='save':
        if editing_busy(store,pid):raise ValueError('Wait for the current activity before changing placement.')
        reviewed=data.get('reviewed') is True
        if reviewed and issues:raise ValueError('Resolve flagged block conflicts before confirming placement.')
        if reviewed and any(v['kind']=='unknown' for v in items):raise ValueError('Identify unknown objects before confirming placement.')
        room['block_layout']={'items':items,'reviewed':reviewed,'basis':basis(store,room)}
        # Any shared-floor output can see changed furniture.
        for r in store.project(pid)['rooms']:
            if r.get('plan_id')==room['plan_id'] and r.get('floor')==room['floor']:store.invalidate(pid,r)
        store.save()
    from placement_map import room_dimensions
    from shared_floor import build as build_scene
    # The editing viewer composes every level; generation cameras remain floor-local.
    floors={}
    for candidate in store.project(pid)['rooms']:
        if candidate.get('plan_id')==room['plan_id'] and candidate.get('bbox'):
            floors.setdefault(candidate['floor'],candidate)
    floors[room['floor']]=room
    preview_floors=[{'room_id':r['id'],'scene':build_scene(store,r,preview_items=items if r['id']==rid else None)} for r in floors.values()]
    return {'items':items,'issues':issues,'revision':room['revision'],'basis':basis(store,room),'room_dimensions':room_dimensions(store,room) or __import__('scene_scale').dimensions(store,room),
            'architecture':architecture_status(store,room),
            'preview_scene':next(f['scene'] for f in preview_floors if f['scene']['floor']==room['floor']),
            'preview_floors':preview_floors,
            'note':'Suggested positions avoid known geometry only. Unmapped walls, door swings and circulation may still be missing. Review the source plan; blocks do not improve scan resolution.'}


def architecture_status(store,room):
    plan=store.asset(room['plan_id']);study=plan.get('plan_reading',{})
    from drawing_scene import load
    features,unresolved=load(store,plan)
    reasons=[]
    if unresolved:reasons.append(f'{len(unresolved)} architectural outlines need review for 3D: '+', '.join(unresolved))
    if not study.get('reviewed'):reasons.append('Review walls, endpoints, doors, windows and open connections in Plan study first.')
    if not any(f.get('kind')=='wall' for f in features):reasons.append('Trace actual walls and their endpoints in Refine drawing. Section borders are not walls.')
    if not room.get('area_polygon'):reasons.append('The usable floor boundary currently uses the section rectangle. Refine it if the room is irregular.')
    return {'study_reviewed':bool(study.get('reviewed')),'typed_wall_count':sum(f.get('kind')=='wall' for f in features),
        'typed_opening_count':sum(f.get('kind') in ('door','window','sliding_door') for f in features),'notes':reasons,
        'scope':'Counts describe saved plan geometry only; they do not certify detection completeness.'}

def readiness(store,room):
    layout=room.get('block_layout',{})
    if not layout.get('items'):return []
    if not layout.get('reviewed') or layout.get('basis')!=basis(store,room):return ['Review furniture blocks against the current plan before generating.']
    problems=[v['message'] for v in checks(store,room,layout['items'])]
    for item in layout['items']:
        if item['kind']=='pillar':continue
        aid=item.get('asset_id')
        if not aid or aid not in room.get('references',[]) or not store.asset(aid).get('enabled',True):problems.append(item['label']+': link an active furniture image before image generation.')
    return problems
