"""Explicitly synthetic geometry fixture, separate from the supplied raster plan."""
import json
from pathlib import Path
from engine import register_asset
from drawing_editor import rasterize
from store import uid


def seed_geometry(store, folder):
    name='Synthetic curve and void regression'
    if any(p['name']==name for p in store.db['projects'].values()):return
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    svg=folder/'synthetic-curves.svg';png=folder/'synthetic-curves.png'
    svg.write_text('''<svg xmlns="http://www.w3.org/2000/svg" width="600" height="500" viewBox="0 0 600 500">
<path id="nativeCurve" class="wall" d="M60 260 C60 60 420 60 420 260" stroke="#536354" stroke-width="8" fill="none"/>
<path id="nativeWall" class="wall" d="M60 260 L60 420 L270 420" stroke="#536354" stroke-width="8" fill="none"/>
<path id="nativeReturn" class="wall" d="M330 420 L420 420 L420 260" stroke="#536354" stroke-width="8" fill="none"/>
<line id="nativeWindow" class="window" x1="420" y1="300" x2="420" y2="360" stroke="#7fb2c1" stroke-width="10"/>
</svg>''',encoding='utf-8')
    rasterize(svg,png)
    from PIL import Image
    with Image.open(png) as image:image.resize((600,500)).save(png)
    project=store.create_project(name);plan=register_asset(store,project['id'],png,'plan',display_name=name)
    project['floor_plans'].append(plan['id']);vector={'id':uid(),'project_id':project['id'],'path':str(svg.resolve()),'width':600,'height':500,'kind':'plan_vector','name':svg.name};store.db['assets'][vector['id']]=vector
    plan['cad_redraw_id']=vector['id'];plan['drawing']={'revision':0,'features':[],'edits':{},'site':{'model':{'metres_per_pixel':.02,'scale_source':'Synthetic fixture definition'}}}
    room=store.add_room(project['id'],'Synthetic studio','Ground',plan['id'],[.05,.05,.85,.85])
    outline=[[.05,.05],[.9,.05],[.9,.65],[.7,.65],[.7,.9],[.05,.9]]
    hole=[[.35,.45],[.45,.45],[.4,.55]]
    project['measurements']=[{'id':uid(),'plan_id':plan['id'],'floor':'Ground','outline':outline,'exclusions':[hole],'scale':{'mode':'percent'}}]
    room['area_polygon']=outline;plan['plan_reading']={'revision':0,'features':[],'checks':{},'warnings':['Synthetic geometry; not inferred from the curved residence.']}
    plan['floor_cameras']={room['id']:{'position':[.4,.82],'target':[.4,.3],'height':1.56,'target_height':1.2,'horizontal_fov':70}}
    store.save()
    import shared_floor
    from model_export import glb
    scene=shared_floor.build(store,room)
    (folder/'synthetic-scene.json').write_text(json.dumps(scene,indent=2),encoding='utf-8')
    (folder/'synthetic-model.glb').write_bytes(glb(scene))
    shared_floor.create_guide(store,room,[],folder)

