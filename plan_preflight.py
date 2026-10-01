"""Local, deterministic input checks. These do not certify generated image fidelity."""
import math
from placement_map import current_layout,room_dimensions

def inside(point,poly):
    x,y=point;hit=False
    for a,b in zip(poly,poly[1:]+poly[:1]):
        dx,dy=b[0]-a[0],b[1]-a[1]
        if abs(dx*(y-a[1])-dy*(x-a[0]))<1e-8 and min(a[0],b[0])-1e-8<=x<=max(a[0],b[0])+1e-8 and min(a[1],b[1])-1e-8<=y<=max(a[1],b[1])+1e-8:return True
        if (a[1]>y)!=(b[1]>y) and x<(b[0]-a[0])*(y-a[1])/(b[1]-a[1])+a[0]:hit=not hit
    return hit

def crossing_opening(wall,opening):
    a,b=wall['points'];c,d=opening['points'];dx,dy=b[0]-a[0],b[1]-a[1];length=math.hypot(dx,dy)
    if length<1e-8:return False
    if any(abs(dx*(p[1]-a[1])-dy*(p[0]-a[0]))/length>.2 for p in (c,d)):return False
    positions=[((p[0]-a[0])*dx+(p[1]-a[1])*dy)/length for p in (c,d)]
    return min(length,max(positions))-max(0,min(positions))>.5

def line_in_box(points,bounds):
    """Length of the segment strictly inside a marked feature's pixel bounds."""
    a,b=points;lo,hi=0.,1.;dx,dy=b[0]-a[0],b[1]-a[1]
    # Ignore endpoint-only/border contact with the opening's selection rectangle.
    x0,y0,x1,y1=bounds;x0+=1e-5;y0+=1e-5;x1-=1e-5;y1-=1e-5
    for p,q in ((-dx,a[0]-x0),(dx,x1-a[0]),(-dy,a[1]-y0),(dy,y1-a[1])):
        if abs(p)<1e-12:
            if q<0:return 0.
        elif p<0:lo=max(lo,q/p)
        else:hi=min(hi,q/p)
    return max(0.,hi-lo)*math.hypot(dx,dy)

def report(store,project,room):
    rows=[]
    def add(key,level,text):rows.append({'id':key,'level':level,'message':text})
    anchor=room.get('anchor_id') or (room.get('scene_control',{}).get('source_id') if room.get('scene_control',{}).get('mode') in ('region','structure') else None)
    if room.get('block_layout',{}).get('items') and room.get('scene_control',{}).get('mode','reference')=='reference':anchor=None
    from interior_style import map_ready,selected_map_ready
    if not map_ready(store,project,room):add('map','blocked','Review and confirm this project’s room map first.')
    else:add('map','pass','Room map is confirmed for the current inputs.')
    if not room.get('plan_id') or not room.get('bbox'):
        add('plan','warning' if anchor else 'blocked','No floor-plan section is available. A room photo can guide appearance, but plan correspondence cannot be checked.')
        return finish(rows,room)
    plan=store.asset(room['plan_id']);b=room['bbox'];study=plan.get('plan_reading',{})
    import furniture_blocks
    for n,message in enumerate(furniture_blocks.readiness(store,room)):add('block-'+str(n),'blocked',message)
    if not study.get('reviewed') and not selected_map_ready(store,project,room):add('study','warning' if anchor else 'blocked','Review the architectural plan study before generating from this drawing.')
    else:add('study','pass','The saved architectural study has been reviewed.')
    relevant=[]
    from plan_reading import overlap
    for f in study.get('features',[]):
        if f.get('review_status')=='rejected' or f.get('floor') not in ('',None,room['floor']):continue
        if room['id'] in (f.get('room_id'),f.get('connection_room_id')) or not f.get('room_id') and overlap(f['bbox'],b)>.05:relevant.append(f)
    if any(f.get('review_status')=='pending' or f.get('kind')=='unknown' for f in relevant):add('unresolved','warning' if anchor else 'blocked','This section contains unresolved plan symbols. Classify them in Plan study.')
    if any(f.get('kind')=='stair' and not f.get('connection_room_id') for f in relevant):add('landing','warning' if anchor else 'blocked','The staircase arrival is unresolved. Confirm its connection before generating the adjoining space.')
    if min(plan['width']*b[2],plan['height']*b[3])<256:add('source','warning',f"Small source section ({round(plan['width']*b[2])} × {round(plan['height']*b[3])} pixels). Enlarging it cannot recover missing details.")
    # Connections reference one feature on the full plan, not separate per-room copies.
    sections={r['id']:r for r in project.get('rooms',[])}
    sections.setdefault(room['id'],room)
    def touches(a,b):
        eps=1e-6
        return a[0]<=b[0]+b[2]+eps and b[0]<=a[0]+a[2]+eps and a[1]<=b[1]+b[3]+eps and b[1]<=a[1]+a[3]+eps
    for feature in relevant:
        target=feature.get('connection_room_id')
        if not target:continue
        owner=sections.get(feature.get('room_id'));other=sections.get(target)
        if not owner or not other or owner['id']==other['id']:
            add('connection-'+feature['id'],'blocked','A shared feature needs two different existing sections.');continue
        if feature['kind']=='stair':continue
        if owner.get('plan_id')!=other.get('plan_id') or owner.get('floor')!=other.get('floor'):
            add('connection-'+feature['id'],'blocked','Adjoining sections must use the same full floor plan and floor; independent crops do not establish a shared position.');continue
        if any(not v.get('bbox') or not touches(feature['bbox'],v['bbox']) for v in (owner,other)):
            add('connection-'+feature['id'],'blocked',f"Shared feature {feature['label']} does not touch both {owner['name']} and {other['name']} on the plan.");continue
        if feature.get('review_status')=='confirmed':
            add('connection-'+feature['id'],'pass',f"{owner['name']} ↔ {other['name']}: {feature['label']} uses one shared position and type. Output correspondence still needs review.")
    # Validate the same opening-cut geometry that the shared scene renders.
    # A raw host-wall span is not a blockage when its mapped opening cuts it.
    from shared_floor import applies
    features=plan.get('drawing',{}).get('features',[])
    if applies(store,room):
        from drawing_scene import load,cut_walls
        features=cut_walls(load(store,plan)[0])
    # A reviewed opening must never be contradicted by a remaining solid wall.
    for feature in relevant:
        if feature.get('review_status')!='confirmed' or feature.get('kind') not in ('door','window','sliding_door'):continue
        box=feature['bbox'];bounds=[box[0]*plan['width'],box[1]*plan['height'],(box[0]+box[2])*plan['width'],(box[1]+box[3])*plan['height']]
        if any(line_in_box(w['points'],bounds)>.5 for w in features if w['kind']=='wall'):
            add('meaning-'+feature.get('id','opening'),'blocked',f"{feature.get('label','Opening')} is identified as {feature['kind'].replace('_',' ')}, but the drawing puts a solid wall through it. Correct the shared drawing before rendering.")
    from placement_map import active_references
    layout=current_layout(room);refs=active_references(store,room)
    items={v['asset_id']:v for v in layout.get('items',[])}
    if refs and not anchor and any(a['id'] not in items for a in refs):add('placements','blocked','Place every active furniture reference on the map before generating a plan-based room.')
    poly=room.get('area_polygon') or [[b[0],b[1]],[b[0]+b[2],b[1]],[b[0]+b[2],b[1]+b[3]],[b[0],b[1]+b[3]]]
    dims=room_dimensions(store,room)
    for ref in refs:
        v=items.get(ref['id'])
        if not v:continue
        name=ref.get('category','Furniture');point=[b[0]+v['x']*b[2],b[1]+v['y']*b[3]]
        if not inside(point,poly):add('outside-'+ref['id'],'blocked',name+' is placed outside the room boundary.')
        if dims and v.get('size'):
            size=v['size'];factor=1 if size['unit']=='m' else .3048;w=size['width']*factor;d=size['depth']*factor;t=math.radians(v['angle'])
            corners=[[b[0]+(v['x']+(x*math.cos(t)-y*math.sin(t))/dims['width_m'])*b[2],b[1]+(v['y']+(x*math.sin(t)+y*math.cos(t))/dims['depth_m'])*b[3]] for x,y in [(-w/2,-d/2),(w/2,-d/2),(w/2,d/2),(-w/2,d/2)]]
            if any(not inside(p,poly) for p in corners):add('footprint-'+ref['id'],'blocked',name+' extends beyond the room boundary at the entered dimensions.')
    if not dims:add('scale','warning','Only proportions are known. Enter measured dimensions to check furniture size and clearance.')
    elif any(a['id'] in items and not items[a['id']].get('size') for a in refs):add('sizes','warning','Enter furniture width and depth to check its full footprint; markers only describe centres.')
    def in_section(f):
        x=sum(p[0] for p in f['points'])/(2*plan['width']);y=sum(p[1] for p in f['points'])/(2*plan['height'])
        return b[0]-1e-6<=x<=b[0]+b[2]+1e-6 and b[1]-1e-6<=y<=b[1]+b[3]+1e-6
    walls=[f for f in features if f['kind']=='wall'];openings=[f for f in features if f['kind'] in ('door','window','sliding_door') and in_section(f)]
    if any(crossing_opening(w,o) for w in walls for o in openings):add('blocked-opening','blocked','A drawn wall overlaps a door or window opening. Split the wall around the opening in Refine drawing.')
    if not anchor:
        from shared_floor import applies,readiness
        if applies(store,room):
            for i,issue in enumerate(readiness(store,room)):add('shared-floor-'+str(i),'blocked',issue)
            if not readiness(store,room):add('shared-floor','pass','This camera uses the full floor’s shared geometry, including adjoining sections. Visual output still needs review.')
            return finish(rows,room)
        from perspective_layout import eligible
        can_guide=eligible(store,room,refs)
        if any(f.get('kind')=='curved_wall' for f in relevant):add('curves','blocked','This section has curved walls. A reviewed perspective layout preserving those curves is needed; the straight-wall guide cannot represent them.')
        elif not can_guide:add('guide','warning','This section has no checked perspective guide. The drawing can guide FLUX, but spatial accuracy remains unverified.')
        else:
            heading=layout.get('camera_heading',0);front=[]
            for f in features:
                if f['kind'] not in ('wall','window','door'):continue
                pts=[((p[0]/plan['width']-b[0])/b[2],(p[1]/plan['height']-b[1])/b[3]) for p in f['points']]
                axis,boundary=(1,0) if heading==0 else (0,1) if heading==90 else (1,1) if heading==180 else (0,0)
                if all(abs(p[axis]-boundary)<.08 for p in pts):front.append(sorted([p[1-axis] for p in pts]))
            end=0;coverage=0
            for lo,hi in sorted(front):lo=max(0,lo,end);hi=min(1,hi);coverage+=max(0,hi-lo);end=max(end,hi)
            if coverage<.7:add('open-view','blocked','The camera faces an open or incomplete edge of this section. Include the adjoining room geometry or choose a view into the mapped room.')
            else:add('guide','pass','Camera-facing boundary has mapped wall and opening geometry.')
    else:add('master','pass','This edit uses a saved room image as its visual reference. Plan accuracy still requires review.')
    return finish(rows,room)

def finish(rows,room):
    blocked=any(r['level']=='blocked' for r in rows)
    return {'version':1,'room_id':room['id'],'room_name':room['name'],'can_generate':not blocked,'status':'needs_input' if blocked else 'inputs_checked','checks':rows,'scope':'Checks saved inputs only. Object identity, output geometry and motion require image/video review. Runs locally without Codex.'}

def assert_ready(store,project,room):
    result=report(store,project,room)
    if not result['can_generate']:raise ValueError('Plan check: '+' '.join(r['message'] for r in result['checks'] if r['level']=='blocked'))
    return result
