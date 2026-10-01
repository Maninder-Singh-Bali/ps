"""One full-floor geometric scene for all room views; never extrude room boxes."""
import math,copy,json,hashlib
from pathlib import Path
import numpy as np
from placement_map import current_layout,room_dimensions


def sections(store,room):
    p=store.project(store.asset(room['plan_id'])['project_id'])
    return [r for r in p.get('rooms',[room]) if r.get('plan_id')==room['plan_id'] and r.get('floor')==room['floor'] and r.get('bbox')]


def floor_bounds(store, room):
    """Include the reviewed floor envelope, not just rooms' interior faces."""
    rs = sections(store, room)
    points = [p for r in rs for p in (r['bbox'][:2],
              [r['bbox'][0]+r['bbox'][2], r['bbox'][1]+r['bbox'][3]])]
    project = store.project(store.asset(room['plan_id'])['project_id'])
    for measurement in project.get('measurements', []):
        if measurement['plan_id'] == room['plan_id'] and measurement['floor'] == room['floor']:
            points.extend(measurement.get('outline', []))
    return [min(p[0] for p in points), min(p[1] for p in points),
            max(p[0] for p in points), max(p[1] for p in points)]


def applies(store,room):
    if not room.get('plan_id'):return False
    plan=store.asset(room['plan_id'])
    return bool(plan.get('raster_geometry') or plan.get('cad_redraw_id') or plan.get('vector_preview_id') or len(sections(store,room))>1 or room.get('block_layout',{}).get('items'))


def unresolved_curves(plan,architecture,floor=None):
    from curve_review import unresolved
    return unresolved(plan,architecture,floor)


def readiness(store,room):
    plan=store.asset(room['plan_id']);issues=[]
    if plan.get('raster_geometry'):
        from raster_validation import status
        review=status(store,plan['project_id'],plan['id'])
        if not review['geometry_validated']:issues.append('Raster geometry review is '+review['state']+'. '+(review['issues'][0]['message'] if review['issues'] else 'Complete boundary review against the original before image generation.'))
    from drawing_scene import load
    architecture,unresolved=load(store,plan)
    if unresolved:issues.append(f'{len(unresolved)} architectural outlines need review before 3D generation: '+', '.join(unresolved)+'. Trace their actual geometry; they are not replaced by boxes.')
    rs=sections(store,room)
    b=floor_bounds(store,room)
    def on_floor(f):return all(b[0]-.003<=v[0]/plan['width']<=b[2]+.003 and b[1]-.003<=v[1]/plan['height']<=b[3]+.003 for v in f['points'])
    if not any(f['kind']=='wall' and on_floor(f) for f in architecture):issues.append('Trace the actual walls on this floor in Refine drawing. Section boxes and open-space connections will never be made into walls.')
    if not plan.get('floor_cameras',{}).get(room['id']):issues.append('Set this section’s camera and viewing direction on the full plan in Structure check.')
    missing=unresolved_curves(plan,architecture,room['floor'])
    if missing:issues.append('Curved architecture lacks matching reviewed curve geometry: '+', '.join(missing)+'. Review these particular paths; do not substitute straight walls.')
    return issues


def floor_rectangles(width,depth,openings):
    """Subtract explicit rectangular voids without filling them with triangles."""
    rectangles=[(0,0,width,depth)]
    for left,top,right,bottom in openings:
        remaining=[]
        for x,y,xx,yy in rectangles:
            l,t,r,b=max(x,left),max(y,top),min(xx,right),min(yy,bottom)
            if l>=r or t>=b:remaining.append((x,y,xx,yy));continue
            remaining.extend(q for q in [(x,y,xx,t),(x,b,xx,yy),(x,t,l,b),(r,t,xx,b)] if q[2]-q[0]>1e-8 and q[3]-q[1]>1e-8)
        rectangles=remaining
    return rectangles


def build(store,room,preview_items=None,camera_override=None):
    plan=store.asset(room['plan_id']);rs=sections(store,room);b=floor_bounds(store,room)
    span=[b[2]-b[0],b[3]-b[1]];synthetic={**room,'bbox':[b[0],b[1],*span]};dims=room_dimensions(store,synthetic)
    from scene_scale import settings,dimensions
    model=settings(plan,room['floor']); metric=dims or dimensions(store,synthetic)
    W=metric['width_m'];D=metric['depth_m'];H=model['wall_height_m']
    model.update(metres_per_pixel=W/(span[0]*plan['width']),scale_source=metric['method'],measured=bool(dims))
    def xy(v):return [(v[0]-b[0])/span[0]*W,(v[1]-b[1])/span[1]*D]
    surfaces=[];lines=[];architecture_id=None
    def face(points,color,kind,object_key=None):surfaces.append({'points':points,'color':color,'kind':kind,**({'object_key':object_key} if object_key else {}),**({'source_id':architecture_id} if architecture_id else {})})
    def prism(a,z,thickness,low,high,color,kind):
        dx,dy=z[0]-a[0],z[1]-a[1];length=math.hypot(dx,dy)
        if length<1e-8 or high<=low:return
        ox,oy=-dy/length*thickness/2,dx/length*thickness/2
        poly=[[a[0]+ox,a[1]+oy],[z[0]+ox,z[1]+oy],[z[0]-ox,z[1]-oy],[a[0]-ox,a[1]-oy]]
        face([[*p,low] for p in poly],color,kind);face([[*p,high] for p in poly],color,kind)
        for p,q in zip(poly,poly[1:]+poly[:1]):face([[*p,low],[*q,low],[*q,high],[*p,high]],color,kind)
    openings=[]
    for f in plan.get('drawing',{}).get('features',[]):
        if f['kind']!='floor_opening':continue
        pts=[[v[0]/plan['width'],v[1]/plan['height']] for v in f['points']]
        if not all(b[0]<=v[0]<=b[2] and b[1]<=v[1]<=b[3] for v in pts):continue
        p,q=map(xy,pts);openings.append([min(p[0],q[0]),min(p[1],q[1]),max(p[0],q[0]),max(p[1],q[1])])
    measurement=next((m for m in store.project(plan['project_id']).get('measurements',[]) if m['plan_id']==plan['id'] and m['floor']==room['floor']),None)
    if measurement:
        from curve_geometry import floor_faces
        holes=copy.deepcopy(measurement.get('exclusions',[]))
        for left,top,right,bottom in openings:
            holes.append([[b[0]+x/W*span[0],b[1]+y/D*span[1]] for x,y in [(left,top),(right,top),(right,bottom),(left,bottom)]])
        for polygon in floor_faces(measurement['outline'],holes):face([[*xy(v),0] for v in polygon],[214,207,192],'floor')
    else:
        for x,y,xx,yy in floor_rectangles(W,D,openings):
            face([[x,y,0],[xx,y,0],[xx,yy,0],[x,yy,0]],[214,207,192],'floor_estimate')
    from drawing_scene import load,cut_walls
    architecture,unresolved=load(store,plan)
    for f in cut_walls(architecture):
        architecture_id=f.get('source_id',f.get('id'))
        if f['kind']=='line':continue
        pts=[[v[0]/plan['width'],v[1]/plan['height']] for v in f['points']]
        # Entire source segments must belong to this floor; never reinterpret another floor.
        if not all(b[0]-.003<=v[0]<=b[2]+.003 and b[1]-.003<=v[1]<=b[3]+.003 for v in pts):continue
        a,z=map(xy,pts);kind=f['kind'];lines.append({'id':f.get('id'),'source_id':f.get('source_id',f.get('id')),'kind':kind,'points':pts,'thickness':f.get('thickness',1.5)})
        bands=[(0,H,[232,227,217])]
        if kind=='window':bands=[(0,.9,[232,227,217]),(.9,2.4,[182,212,218]),(2.4,H,[232,227,217])]
        elif kind=='sliding_door':bands=[(0,2.4,[171,207,216]),(2.4,H,[232,227,217])]
        elif kind=='door':bands=[(2.2,H,[232,227,217])]
        # Drawing thickness is in source pixels. Use an explicit illustrative
        # default only for older features without a recorded thickness.
        thickness=float(f.get('thickness',0) or 0)*W/(span[0]*plan['width']) or .12
        for low,high,col in bands:prism(a,z,thickness,max(0,min(H,low)),max(0,min(H,high)),col,kind)
        if kind=='door':
            dx,dy=z[0]-a[0],z[1]-a[1];length=math.hypot(dx,dy)
            if length>0:
                unit=[dx/length,dy/length];jamb=min(.07,length*.08)
                prism(a,[a[0]+unit[0]*jamb,a[1]+unit[1]*jamb],thickness,0,min(2.2,H),[172,135,93],'door_frame')
                prism([z[0]-unit[0]*jamb,z[1]-unit[1]*jamb],z,thickness,0,min(2.2,H),[172,135,93],'door_frame')
                sign=-1 if f.get('flip') else 1
                leaf=[xy([v[0]/plan['width'],v[1]/plan['height']]) for v in f['leaf_points']] if f.get('leaf_points') else [a,[a[0]-sign*dy,a[1]+sign*dx]]
                prism(*leaf,min(.045,thickness),0,min(2.15,H),[190,160,121],'door_leaf')
    architecture_id=None
    products=[]
    for r in rs:
        rb=r['bbox'];rw=rb[2]/span[0]*W
        from furniture_blocks import readiness as block_readiness
        from furniture_meshes import mesh
        for item in (preview_items if preview_items is not None and r['id']==room['id'] else r.get('block_layout',{}).get('items',[])):
            object_key=r['id']+':'+item['id']
            for part in mesh(item,plan):
                face([[*xy(v[:2]),v[2]] for v in part['points']],part['color'],'block',object_key)
            products.append({'object_key':object_key,'asset_id':item.get('asset_id'),'block_id':item['id'],'room_id':r['id'],'label':item['label'],'centre':[item['x'],item['y']],'facing':item['angle'],'size_confirmed':False,'reviewed':not block_readiness(store,r)})
        for item in current_layout(r).get('items',[]):
            if item.get('block_id'):continue
            ref=store.asset(item['asset_id'])
            if not ref.get('enabled',True):continue
            q=[rb[0]+item['x']*rb[2],rb[1]+item['y']*rb[3]];cx,cy=xy(q);cat=ref.get('category','Furniture').lower();wide=.5 if 'sofa' in cat else .23;deep=.17 if 'sofa' in cat else .23
            w,d=rw*wide,rw*deep
            if dims and item.get('size'):
                size=item['size'];factor=1 if size['unit']=='m' else .3048;w=size['width']*factor;d=size['depth']*factor
            h=.45 if 'table' in cat else .8;t=math.radians(item['angle']);c,s=math.cos(t),math.sin(t)
            corners=[[cx+x*c-y*s,cy+x*s+y*c] for x,y in [(-w/2,-d/2),(w/2,-d/2),(w/2,d/2),(-w/2,d/2)]]
            color=[178,156,123] if 'table' in cat else [184,186,153]
            for a,z in zip(corners,corners[1:]+corners[:1]):face([[*a,0],[*z,0],[*z,h],[*a,h]],color,'furniture')
            face([[*q,h] for q in corners],color,'furniture')
            products.append({'asset_id':item['asset_id'],'room_id':r['id'],'centre':q,'facing':item['angle'],'size_confirmed':bool(dims and item.get('size'))})
    camera=camera_override or plan.get('floor_cameras',{}).get(room['id']);world_camera=None
    if camera:
        world_camera={'position':[*xy(camera['position']),camera['height']], 'target':[*xy(camera['target']),camera.get('target_height',camera['height'])], 'horizontal_fov':camera.get('horizontal_fov',math.degrees(2*math.atan(960/1450)))}
    content={'plan_id':plan['id'],'floor':room['floor'],'bounds':b,'width':W,'depth':D,'height':H,'calibrated':bool(dims),'floor_boundary_status':'saved polygon' if measurement else 'unknown; reference plane only','model_scale':model,'surfaces':surfaces,'lines':lines,'products':products,
             'unresolved_architecture':unresolved,'architecture_counts':{k:sum(f['kind']==k for f in lines) for k in ('wall','window','door','sliding_door')},
             'camera':world_camera,'saved_camera':camera,'room_id':room['id'],'room_name':room['name'],
             'limits':['3D uses visible classified source architecture and typed drawing segments, including saved edits; room/section rectangles are not walls.',f'Wall height {H:g} m; opening heights and door leaf poses are defaults unless measured. Wall thickness follows the drawing.','Low-poly furniture shows saved placement, size and seat counts. Models are library proxies; exact product appearance depends on reference conditioning.']+([] if dims else ['Scale is estimated from furniture or manually entered; calibrate a known plan dimension for measured accuracy.'])}
    from scene_document import from_plan
    content['scene_document']=from_plan(plan,rs,architecture)
    content['geometry_hash']=hashlib.sha256(json.dumps({k:content[k] for k in ('bounds','surfaces','products')},sort_keys=True).encode()).hexdigest()
    return content


def create_guide(store,room,refs,folder):
    issues=readiness(store,room)
    from furniture_blocks import readiness as block_readiness
    for section in sections(store,room):issues.extend(block_readiness(store,section))
    if issues:raise ValueError('Shared floor: '+' '.join(issues))
    scene=build(store,room);camera=scene['camera']
    from perspective_layout import render_faces
    faces=[(np.array(f['points']),tuple(f['color'])) for f in scene['surfaces']]
    products=[p for p in scene['products'] if p.get('object_key')]
    owner_ids={p['object_key']:i+1 for i,p in enumerate(products)}
    path,face_ids,depth=render_faces(faces,camera['position'],camera['target'],Path(folder)/'shared_floor_reference.png',
        owners=list(range(1,len(faces)+1)),return_buffers=True,horizontal_fov=camera['horizontal_fov'])
    owners=np.array([0]+[owner_ids.get(f.get('object_key'),0) for f in scene['surfaces']],dtype=np.int32)[face_ids]
    projected=save_projection(products,owners,depth,folder)
    invisible=[p['label'] for p in projected if p['room_id']==room['id'] and not p['visible_pixels']]
    if invisible:raise ValueError('The selected camera cannot see these furniture blocks: '+', '.join(invisible)+'. Adjust the camera or placement before generating.')
    from geometry_guidance import save as save_guidance
    guidance=save_guidance(scene,face_ids,depth,folder)
    info={'version':3,'method':'Shared full-floor geometry; all section views use the same wall/opening and furniture coordinates','geometry_hash':scene['geometry_hash'],
          'plan_id':scene['plan_id'],'floor':scene['floor'],'camera':camera,'objects':scene['products'],'output_size':[1920,1088],
          'labels_in_image':False,'assumptions':scene['limits'],'shared_floor':True,'projected_objects':projected,
          'geometry_guidance':guidance,'scene_revision':scene['scene_document']['scene_revision'],
          'placement_enforcement':'Projected coordinates and reference conditioning; masks are QA targets, not a model-enforced constraint.'}
    (Path(folder)/'shared-floor-scene.json').write_text(json.dumps(scene,indent=2),encoding='utf-8')
    return path,info


def save_projection(products,owners,depth,folder):
    """The same z-buffer used for the guide supplies per-product visible QA targets."""
    from PIL import Image
    folder=Path(folder);result=[]
    for index,product in enumerate(products,1):
        mask=owners==index;ys,xs=np.where(mask);visible=len(xs)
        bbox=[int(xs.min()),int(ys.min()),int(xs.max()+1),int(ys.max()+1)] if visible else None
        name=f'placement-object-{index:02d}.png'
        Image.fromarray((mask*255).astype(np.uint8)).save(folder/name)
        # Final output removes four rows at both ends; keep coordinates explicit.
        final_mask=mask[4:1084];fy,fx=np.where(final_mask)
        final_bbox=[int(fx.min()),int(fy.min()),int(fx.max()+1),int(fy.max()+1)] if len(fx) else None
        result.append({**product,'mask_file':name,'visible_pixels':visible,'guide_bbox_xyxy':bbox,
            'guide_size':[1920,1088],'output_bbox_xyxy':final_bbox,'output_size':[1920,1080],
            'median_camera_depth':float(np.median(depth[mask])) if visible else None,
            'scope':'Visible placeholder envelope; product silhouette may occupy less area. Not an output accuracy measurement.'})
    (folder/'placement-projection.json').write_text(json.dumps(result,indent=2),encoding='utf8')
    return result


def clean_camera(store,pid,aid,data):
    from plan_preflight import inside
    from scene_control import digest
    p=store.project(pid);plan=store.asset(aid)
    if aid not in p['floor_plans']:raise ValueError('Choose a plan from this project.')
    r=store.room(pid,data.get('room_id'))
    if r.get('plan_id')!=aid:raise ValueError('Choose a section on this plan.')
    if data.get('revision')!=r['revision']:raise ValueError('This section changed. Reopen Structure check.')
    camera={}
    for key in ('position','target'):
        v=data.get(key)
        if not isinstance(v,list) or len(v)!=2 or any(type(n) not in (int,float) or not math.isfinite(n) or not 0<=n<=1 for n in v):raise ValueError('Choose camera and target points on the full plan.')
        camera[key]=v
    b=r['bbox'];poly=r.get('area_polygon') or [[b[0],b[1]],[b[0]+b[2],b[1]],[b[0]+b[2],b[1]+b[3]],[b[0],b[1]+b[3]]]
    if not inside(camera['position'],poly):raise ValueError('Place the camera inside the selected section.')
    if math.dist(camera['position'],camera['target'])<.01:raise ValueError('Choose a viewing target farther from the camera.')
    from scene_scale import settings
    h=data.get('height',settings(plan,r['floor'])['eye_height_m'])
    if type(h) not in (int,float) or not math.isfinite(h) or not .3<=h<=2.8:raise ValueError('Use a view height between 0.3 and 2.8.')
    camera['height']=h;camera['illustrative_height']=True
    for key,default,low,high in [('target_height',h,0,3),('horizontal_fov',math.degrees(2*math.atan(960/1450)),30,100)]:
        value=data.get(key,default)
        if type(value) not in (int,float) or not math.isfinite(value) or not low<=value<=high:raise ValueError(f'{key.replace("_"," ").capitalize()} must be between {low} and {high}.')
        camera[key]=value
    return r,plan,camera


def preview_camera(store,pid,aid,data):
    import base64
    from perspective_layout import render_faces
    from PIL import Image
    import io
    r,plan,camera=clean_camera(store,pid,aid,data)
    scene=build(store,r,camera_override=camera);view=scene['camera']
    products=[p for p in scene['products'] if p.get('object_key')]
    identities={p['object_key']:i+1 for i,p in enumerate(products)}
    im,owners,_=render_faces([(np.array(f['points']),tuple(f['color'])) for f in scene['surfaces']],view['position'],view['target'],None,horizontal_fov=view['horizontal_fov'],owners=[identities.get(f.get('object_key'),0) for f in scene['surfaces']],return_buffers=True)
    palette=[(83,132,162),(194,143,69),(134,153,93),(161,110,143),(87,157,149),(163,116,89)]
    objects=[];pixels=np.array(im)
    for i,p in enumerate(products):
        mask=owners==i+1;visible=mask[4:1084];ys,xs=np.where(visible);color=palette[i%len(palette)]
        clipped=bool(len(xs) and (xs.min()==0 or xs.max()==1919 or ys.min()==0 or ys.max()==1079))
        objects.append({'label':p['label'],'object_key':p['object_key'],'color':'#%02x%02x%02x'%color,'visible_pixels':len(xs),'status':'Outside view or hidden' if not len(xs) else 'Partly outside frame' if clipped else 'In view'})
        if data.get('identify_objects'):
            pixels[mask]=color
            # Boundary pixels separate adjoining objects even with a similar palette.
            interior=mask.copy();interior[1:] &= mask[:-1];interior[:-1] &= mask[1:];interior[:,1:] &= mask[:,:-1];interior[:,:-1] &= mask[:,1:]
            pixels[mask & ~interior]=tuple(int(c*.7) for c in color)
    if data.get('identify_objects'):im=Image.fromarray(pixels)
    im=im.crop((0,4,1920,1084));im.thumbnail((960,540));buffer=io.BytesIO();im.save(buffer,format='PNG')
    return {'image':'data:image/png;base64,'+base64.b64encode(buffer.getvalue()).decode(),'camera':camera,'calibrated':scene['calibrated'],'typed_segments':len(scene['lines']),'objects':objects}


def save_camera(store,pid,aid,data):
    if any(j['project_id']==pid and j['status'] in ('queued','running','waiting') for j in store.db['jobs'].values()):raise ValueError('Finish the active generation before changing shared views.')
    r,plan,camera=clean_camera(store,pid,aid,data)
    if plan.setdefault('floor_cameras',{}).get(r['id'])!=camera:
        plan['floor_cameras'][r['id']]=camera;store.invalidate(pid,r);store.save()
    return {'ok':True,'room_id':r['id'],'revision':r['revision'],'camera':camera}
