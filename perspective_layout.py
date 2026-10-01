"""Perspective conditioning from explicitly corrected straight plan lines.

This is a relative layout guide, not surveyed 3D. Never used for anchored edits or
uncorrected/curved/partly interpreted plans. No labels enter the render reference.
"""
import json, math
from pathlib import Path
import numpy as np
from PIL import Image
from placement_map import current_layout,room_dimensions

def eligible(store,room,refs):
    from shared_floor import applies,readiness
    if room.get('plan_id') and applies(store,room):return not readiness(store,room)
    if not room.get('plan_id') or not room.get('bbox'):return False
    a=store.asset(room['plan_id']);d=a.get('drawing',{})
    if not d.get('features') or any(not e.get('hidden') for e in d.get('edits',{}).values()):return False
    # Reconstruct only an entirely redrawn plan, never discard surviving source paths.
    from drawing_editor import get_document
    doc=get_document(store,a['project_id'],a['id'])
    if any(not d.get('edits',{}).get(e['id'],{}).get('hidden') for e in doc['elements']):return False
    items=current_layout(room).get('items',[])
    return len(refs)<=3 and all(any(t in a.get('category','').lower() for t in ('sofa','table','chair')) for a in refs) and {a['id'] for a in refs}.issubset({x['asset_id'] for x in items}) and any(f['kind']=='wall' for f in d['features'])

def create(store,room,refs,folder):
    from shared_floor import applies,create_guide
    if room.get('plan_id') and applies(store,room):return create_guide(store,room,refs,folder)
    if not eligible(store,room,refs):return None
    a=store.asset(room['plan_id']);layout=current_layout(room);b=room['bbox'];dims=room_dimensions(store,room)
    W=dims['width_m'] if dims else 6.;D=dims['depth_m'] if dims else W*b[3]*a['height']/(b[2]*a['width']);H=.50*W
    heading=math.radians(layout.get('camera_heading',0));forward=np.array([math.sin(heading),-math.cos(heading),0.]);right=np.array([math.cos(heading),math.sin(heading),0.])
    center=np.array([W/2,D/2,0.]);camera=center-forward*max(W,D)*1.0+np.array([0,0,.32*W]);target=center+forward*max(W,D)*.12+np.array([0,0,.12*W])
    f=target-camera;f/=np.linalg.norm(f);r=np.cross([0,0,1],f);r/=np.linalg.norm(r);up=np.cross(f,r);matrix=np.array([r,up,f]);faces=[]
    def face(points,color):faces.append((np.array(points,dtype=float),color))
    def box(cx,cy,width,depth,z,height,color,angle=0):
        c,s=math.cos(angle),math.sin(angle)
        pts=[(cx+x*c-y*s,cy+x*s+y*c,zz) for zz in (z,z+height) for x,y in [(-width/2,-depth/2),(width/2,-depth/2),(width/2,depth/2),(-width/2,depth/2)]]
        for n,ix in enumerate(([0,1,5,4],[1,2,6,5],[2,3,7,6],[3,0,4,7],[4,5,6,7])):
            face([pts[i] for i in ix],tuple(int(min(255,c*(.88+n*.027))) for c in color))
    def xy(p):return ((p[0]/a['width']-b[0])/b[2]*W,(p[1]/a['height']-b[1])/b[3]*D)
    face([[-W,-D,0],[2*W,-D,0],[2*W,2*D,0],[-W,2*D,0]],(211,202,187))
    for ft in a['drawing']['features']:
        (x,y),(xx,yy)=map(xy,ft['points'])
        # Do not include lines from other sections or the cutaway wall behind the camera.
        if not all(-.02*W<=p[0]<=W*1.02 and -.02*D<=p[1]<=D*1.02 for p in ((x,y),(xx,yy))):continue
        viewing_span=abs(forward[0])*W+abs(forward[1])*D
        if np.dot(np.array([(x+xx)/2,(y+yy)/2,0])-center,forward)<-viewing_span*.42:continue
        kind=ft['kind']
        # Inset opening details toward the room to avoid coplanar depth ties.
        mid=np.array([(x+xx)/2,(y+yy)/2]);inside=center[:2]-mid
        normal=np.array([-(yy-y),xx-x],dtype=float);normal/=max(np.linalg.norm(normal),1e-8)
        if np.dot(normal,inside)<0:normal=-normal
        def opening_panel(t0,t1,z0,z1,color):
            start=np.array([x,y])+(np.array([xx,yy])-np.array([x,y]))*t0+normal*.003*W
            end=np.array([x,y])+(np.array([xx,yy])-np.array([x,y]))*t1+normal*.003*W
            face([[*start,z0],[*end,z0],[*end,z1],[*start,z1]],color)
        def opening_frame(z0,z1):
            fw=min(.07,.014*W/max(math.hypot(xx-x,yy-y),.001));fh=.014*W
            opening_panel(0,fw,z0,z1,(105,99,86));opening_panel(1-fw,1,z0,z1,(105,99,86))
            opening_panel(0,1,z0,z0+fh,(105,99,86));opening_panel(0,1,z1-fh,z1,(105,99,86))
        if kind=='wall':face([[x,y,0],[xx,yy,0],[xx,yy,H],[x,y,H]],(236,231,222))
        if kind=='window':
            lo,hi=.13*W,.39*W
            for z0,z1 in ((0,lo),(hi,H)):face([[x,y,z0],[xx,yy,z0],[xx,yy,z1],[x,y,z1]],(236,231,222))
            face([[x,y,lo],[xx,yy,lo],[xx,yy,hi],[x,y,hi]],(207,218,213))
            opening_frame(lo,hi)
        if kind=='door':
            face([[x,y,H*.82],[xx,yy,H*.82],[xx,yy,H],[x,y,H]],(236,231,222))
            # Closed leaf communicates a doorway without inventing a room beyond it.
            face([[x,y,0],[xx,yy,0],[xx,yy,H*.82],[x,y,H*.82]],(148,114,80))
            opening_frame(0,H*.82)
    # Rug footprint is just a material placeholder beneath the specified products.
    if refs:face([[W*.07,D*.13,.005],[W*.78,D*.13,.005],[W*.78,D*.83,.005],[W*.07,D*.83,.005]],(192,180,157))
    index={x['asset_id']:x for x in layout.get('items',[])};objects=[]
    for i,ref in enumerate(refs):
        item=index.get(ref['id'])
        if not item:continue
        name=ref.get('category','').lower();cx=item['x']*W;cy=item['y']*D;t=math.radians(item['angle'])
        sofa='sofa' in name;table='table' in name;w=W*(.50 if sofa else .23 if table else .20);depth=W*(.17 if sofa else .23 if table else .19)
        if dims and item.get('size'):
            size=item['size'];unit=1 if size['unit']=='m' else .3048;w=size['width']*unit;depth=size['depth']*unit
        wood=(99,68,43);fabric=(222,214,193) if sofa else (142,151,111)
        if item.get('block_id'):
            w=item['proportion'][0]*W;depth=item['proportion'][1]*D
            box(cx,cy,w,depth,0,W*(.065 if table else .12),(180,184,187),t)
            objects.append({'reference_id':ref['id'],'block_id':item['block_id'],'image_index':i+2,'plan_center':[item['x'],item['y']],'facing':item['angle'],'section_footprint':item['proportion']})
            continue
        if table:
            box(cx,cy,w*.8,depth*.8,0,.06*W,wood,t);box(cx,cy,w,depth,.06*W,.012*W,(235,230,219),t)
        else:
            box(cx,cy,w,depth,0,.04*W,wood,t);box(cx,cy,w*.95,depth*.88,.04*W,.038*W,fabric,t)
            bx=cx-math.sin(t)*depth*.39;by=cy+math.cos(t)*depth*.39
            box(bx,by,w,depth*.18,.07*W,.083*W,fabric,t)
            for sign in (-1,1):box(cx+sign*math.cos(t)*w*.47,cy+sign*math.sin(t)*w*.47,w*.07,depth,.05*W,.055*W,wood,t)
        objects.append({'reference_id':ref['id'],'image_index':i+2,'plan_center':[item['x'],item['y']],'facing':item['angle'],'footprint_m':[w,depth] if dims and item.get('size') else None})
    path=render_faces(faces,camera,target,Path(folder)/'perspective_layout_reference.png')
    info={'version':2,'method':'perspective from manually corrected line features and saved furniture map','dimensions':dims,'objects':objects,'camera_heading':layout.get('camera_heading',0),'assumptions':['Wall height, window sill/head heights, furniture heights and lens are illustrative defaults unless supplied; not inferred measurements.','Window frame finish and closed door leaves are visualization defaults; the plan specifies their opening locations only.','Geometry guides image conditioning, not a hard constraint on the generative output.'],'labels_in_image':False,'output_size':[1920,1088]}
    (Path(folder)/'perspective-layout.json').write_text(json.dumps(info,indent=2),encoding='utf8');return path,info


def render_faces(faces,camera,target,path,owners=None,return_buffers=False,horizontal_fov=None):
    camera=np.array(camera,dtype=float);target=np.array(target,dtype=float)
    f=target-camera;f/=np.linalg.norm(f);r=np.cross([0,0,1],f);r/=np.linalg.norm(r);up=np.cross(f,r);matrix=np.array([r,up,f])
    if horizontal_fov is not None and (not math.isfinite(horizontal_fov) or not 30<=horizontal_fov<=100):
        raise ValueError('Use a horizontal field of view between 30 and 100 degrees.')
    focal=1450. if horizontal_fov is None else 960/math.tan(math.radians(horizontal_fov)/2)
    def clip(points):
        out=[]
        for j,p in enumerate(points):
            q=points[j-1];pin=p[2]>.05;qin=q[2]>.05
            if pin!=qin:out.append(q+(p-q)*((.05-q[2])/(p[2]-q[2])))
            if pin:out.append(p)
        return np.array(out)
    pixels=np.full((1088,1920,3),(240,237,229),dtype=np.uint8);zbuffer=np.full((1088,1920),np.inf,dtype=np.float32)
    ownerbuffer=np.zeros((1088,1920),dtype=np.int32)
    if owners is not None and len(owners)!=len(faces):raise ValueError('Each surface must have one object identity.')
    transformed=[((matrix@(p-camera).T).T,c) for p,c in faces]
    for face_index,(points,color) in enumerate(transformed):
        points=clip(points)
        for i in range(1,len(points)-1):
            tri=points[[0,i,i+1]];screen=np.array([(960+focal*v[0]/v[2],544-focal*v[1]/v[2]) for v in tri])
            lo=np.maximum([0,0],np.floor(screen.min(axis=0))).astype(int);hi=np.minimum([1919,1087],np.ceil(screen.max(axis=0))).astype(int)
            if np.any(hi<lo):continue
            x,y=np.meshgrid(np.arange(lo[0],hi[0]+1)+.5,np.arange(lo[1],hi[1]+1)+.5)
            (ax,ay),(bx,by),(cx,cy)=screen;den=(by-cy)*(ax-cx)+(cx-bx)*(ay-cy)
            if abs(den)<1e-8:continue
            u=((by-cy)*(x-cx)+(cx-bx)*(y-cy))/den;v=((cy-ay)*(x-cx)+(ax-cx)*(y-cy))/den;w=1-u-v
            inv=u/tri[0,2]+v/tri[1,2]+w/tri[2,2];depth=1/np.maximum(inv,1e-12)
            region=zbuffer[lo[1]:hi[1]+1,lo[0]:hi[0]+1];mask=(u>=0)&(v>=0)&(w>=0)&(depth<region)
            region[mask]=depth[mask];pixels[lo[1]:hi[1]+1,lo[0]:hi[0]+1][mask]=color
            ownerbuffer[lo[1]:hi[1]+1,lo[0]:hi[0]+1][mask]=owners[face_index] if owners is not None else 0
    image=Image.fromarray(pixels)
    if path is None:return (image,ownerbuffer,zbuffer) if return_buffers else image
    path=Path(path);image.save(path)
    return (path,ownerbuffer,zbuffer) if return_buffers else path
