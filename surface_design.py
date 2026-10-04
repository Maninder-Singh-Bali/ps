"""Draft-only surface design: explicit hosts, physical local units, no inference.

Uses the same shared scene face contract as wall_junctions. Source references are
preview images, not a claim of product geometry or supplied stone grain.
"""
import base64,copy,io,math,re
from PIL import Image,ImageOps
from shapely import Polygon,box,constrained_delaunay_triangles
from shapely.affinity import rotate,translate

KINDS={'painting','mirror','sconce','switchboard','socket','tv','shelf','panel','pendant','downlight','fan','grille','track','profile','bulkhead','rug','threshold','border'}
def num(v,lo,hi,name):
    if type(v) not in (int,float) or not math.isfinite(v) or not lo<=v<=hi:raise ValueError('Invalid '+name)
    return v

def image_data(value):
    if not value:return None
    if not isinstance(value,str) or len(value)>3_000_000 or not re.fullmatch(r'data:image/(png|jpeg|webp);base64,[A-Za-z0-9+/=]+',value):raise ValueError('Choose a PNG, JPEG or WebP reference up to 2 MB.')
    raw=base64.b64decode(value.split(',',1)[1],validate=True)
    with Image.open(io.BytesIO(raw)) as im:
        if im.width*im.height>16_000_000:raise ValueError('Reference preview exceeds 16 megapixels.')
        im.load();return im.convert('RGB')

def reference(r):
    if not isinstance(r,dict):raise ValueError('Invalid reference')
    for key in ('product_url',):
        u=r.get(key,'')
        if not isinstance(u,str) or len(u)>2048 or u and not re.match(r'^https?://[^\s]+$',u):raise ValueError('Use an http(s) product link.')
    a=r.get('asset')
    if a and (not isinstance(a,dict) or not re.fullmatch(r'[0-9a-f]{64}',a.get('sha256','')) or not re.fullmatch(a['sha256']+r'\.(png|jpg|webp)',a.get('file',''))):raise ValueError('Invalid original reference identity')
    image_data(r.get('image'))
    if r.get('dimension_status','assumed') not in ('assumed','extracted','verified'):raise ValueError('Invalid dimension status')

def finish(f):
    if not f:return
    if f.get('kind') not in ('paint','wallpaper','wood','stone','tile','marble'):raise ValueError('Invalid finish')
    for k,default in [('tile_width',.6),('tile_length',.6)]:num(f.get(k,default),.05,10,k)
    if f.get('grout',.003)>=min(f.get('tile_width',.6),f.get('tile_length',.6)):raise ValueError('Grout must be smaller than the tile.')
    num(f.get('grout',.003),0,.05,'grout');num(f.get('rotation',0),-360,360,'finish rotation')
    for k in ('offset_x','offset_y'):num(f.get(k,0),-100,100,k)
    for k in ('color','grout_color'):
        if not re.fullmatch(r'#[0-9a-fA-F]{6}',f.get(k,'#dddddd')):raise ValueError('Invalid finish colour')
    if f.get('layout','grid') not in ('grid','staggered'):raise ValueError('Invalid layout')
    reference(f.get('reference',{}))

def validate(raw):
    if raw is None:return None
    if not isinstance(raw,dict) or raw.get('version')!=1:raise ValueError('Unsupported surface design version')
    d=copy.deepcopy(raw);ss=d.get('surfaces',[]);items=d.get('items',[])
    if not isinstance(ss,list) or len(ss)>100 or not isinstance(items,list) or len(items)>300:raise ValueError('Use up to 100 surfaces and 300 design items.')
    ids=set()
    for s in ss:
        if not isinstance(s,dict) or not re.fullmatch(r'[\w:-]{1,100}',s.get('id','')) or s['id'] in ids:raise ValueError('Invalid surface identity')
        ids.add(s['id'])
        if s.get('kind') not in ('wall','floor','ceiling'):raise ValueError('Invalid surface kind')
        if s['kind']=='wall':
            if not isinstance(s.get('wall_id'),str) or s.get('side') not in (-1,1):raise ValueError('Select an explicit wall face')
        else:
            for ring in [s.get('boundary',[])]+s.get('holes',[]):
                if not isinstance(ring,list) or not 3<=len(ring)<=100:raise ValueError('Surface boundary needs 3–100 vertices')
                for p in ring:
                    if not isinstance(p,list) or len(p)!=2:raise ValueError('Invalid surface vertex')
                    for v in p:num(v,-100000,100000,'surface coordinate')
            p=Polygon(s['boundary'],s.get('holes',[]))
            if not p.is_valid or p.area<.01:raise ValueError('Boundary must be simple; voids must lie inside it without crossing.')
            num(s.get('elevation_m',0),0,20,'surface elevation')
        finish(s.get('finish'))
    itemids=set()
    for o in items:
        if not isinstance(o,dict) or not re.fullmatch(r'[\w:-]{1,100}',o.get('id','')) or o['id'] in itemids:raise ValueError('Invalid design item identity')
        itemids.add(o['id'])
        # Missing hosts are retained, visibly orphaned, never discarded on wall deletion.
        if o.get('kind') not in KINDS or not isinstance(o.get('surface_id'),str):raise ValueError('Invalid design item type/host')
        for k in ('x','y'):num(o.get(k),-100,100,k)
        for k in ('width','height','depth'):num(o.get(k),.001,30,k)
        num(o.get('rotation',0),-360,360,'item rotation');num(o.get('drop',0),0,20,'suspension')
        reference(o.get('reference',{}))
        if 'run' in o:
            if o['kind'] not in ('profile','track') or not 2<=len(o['run'])<=50:raise ValueError('Use 2–50 profile vertices')
            for p in o['run']:
                if len(p)!=2:raise ValueError('Invalid profile point')
                for v in p:num(v,-30,30,'profile point')
        if 'light' in o:
            num(o['light'].get('lumens',0),0,100000,'lumens');num(o['light'].get('kelvin',3000),1000,20000,'colour temperature')
        finish(o.get('finish'))
    return d

def polys(g):
    if g.is_empty:return []
    if g.geom_type=='Polygon':return [g]
    return [p for q in getattr(g,'geoms',[]) for p in polys(q)]
def rgb(c):return [int(c[i:i+2],16) for i in (1,3,5)]
def context(d,s):
    m=d['calibration']['metres_per_pixel']
    if s['kind']=='wall':
        w=next((w for w in d['features'] if w['id']==s['wall_id'] and w['kind']=='wall'),None)
        if not w:return None
        L=math.dist(*w['points'])*m;u=[(w['points'][1][i]-w['points'][0][i])*m/L for i in range(2)];n=[-u[1]*s['side'],u[0]*s['side']]
        region=box(0,0,L,w.get('height_m',d['wall_height_m']))
        for o in d['features']:
            if o.get('host_wall_id')==w['id']:
                base=o.get('sill_m',.9) if o['kind']=='window' else o.get('base_m',0)
                region=region.difference(box(o['offset']*m,base,(o['offset']+o['width'])*m,o.get('head_m',2.4 if o['kind']=='window' else 2.2)))
        def world(x,y,z=0):return [w['points'][0][i]*m+u[i]*x+n[i]*(w['thickness']*m/2+.004+z) for i in range(2)]+[y]
        return region,world
    ox=min(p[0] for p in s['boundary'])*m;oy=min(p[1] for p in s['boundary'])*m
    region=Polygon([[(p[0]*m-ox),(p[1]*m-oy)] for p in s['boundary']],[[[(p[0]*m-ox),(p[1]*m-oy)] for p in h] for h in s.get('holes',[])])
    def world(x,y,z=0):return [ox+x,oy+y,s.get('elevation_m',0)+( -z if s['kind']=='ceiling' else z+.006)]
    return region,world

def mesh(d,origin):
    design=d.get('surface_design') or {};out=[];m=d['calibration']['metres_per_pixel'];ss={s['id']:s for s in design.get('surfaces',[])};hidden=design.get('hidden_categories',[])
    def face(points,col,identifier,ceiling=False):
        if len(out)>=60000:raise ValueError('Preview exceeds 60000 faces. Reduce texture repeats or hide design categories.')
        out.append({'id':identifier,'object_key':('design:surface:' if identifier in ss else 'design:item:')+identifier,'surface_design':True,'kind':'surface_design','points':[[p[0]-origin[0]*m,p[1]-origin[1]*m,p[2]] for p in points],'color':col,'edge_mask':[False]*len(points),'ceiling':ceiling and not design.get('show_ceiling',False)})
    def flat(region,world,z,col,identifier,ceiling=False):
        for p in polys(region):
            for t in constrained_delaunay_triangles(p).geoms:face([world(x,y,z) for x,y in list(t.exterior.coords)[:-1]],col,identifier,ceiling)
    def prism(region,world,low,high,col,identifier):
        flat(region,world,high,col,identifier)
        for p in polys(region):
            for ring in [p.exterior]+list(p.interiors):
                for a,b in zip(list(ring.coords),list(ring.coords)[1:]):face([world(*a,low),world(*b,low),world(*b,high),world(*a,high)],[round(c*.8) for c in col],identifier)
    def textured(region,world,z,f,identifier,ceiling=False):
        if region.is_empty:return
        col=rgb(f.get('color','#d9d3c8'));image=image_data(f.get('reference',{}).get('image'))
        if f.get('kind')=='paint' or not f:flat(region,world,z,col,identifier,ceiling);return
        if image:image=image.resize((8,8),Image.Resampling.BOX)
        w=f.get('tile_width',.6);h=f.get('tile_length',.6);angle=f.get('rotation',0);ox=f.get('offset_x',0);oy=f.get('offset_y',0);grout=f.get('grout',.003)
        local=translate(rotate(region,-angle,origin=(0,0)),-ox,-oy);a,b,c,e=local.bounds
        count=(math.ceil((c-a)/w)+2)*(math.ceil((e-b)/h)+2)
        if count>2500:raise ValueError('Finish creates more than 2500 tiles; increase the tile size or use a smaller region.')
        flat(region,world,z-.0005,rgb(f.get('grout_color','#777777')),identifier,ceiling)
        for iy in range(math.floor(b/h)-1,math.ceil(e/h)+1):
            shift=w/2 if f.get('layout')=='staggered' and iy%2 else 0
            for ix in range(math.floor(a/w)-1,math.ceil(c/w)+1):
                x=ix*w+shift;y=iy*h;tile=box(x+grout/2,y+grout/2,x+w-grout/2,y+h-grout/2).intersection(local)
                if tile.is_empty:continue
                # CPU reference swatches keep the existing lightweight renderer;
                # intentionally approximate texture, never an exact product model.
                n=8 if image else 1
                for j in range(n):
                    for i in range(n):
                        cell=tile.intersection(box(x+i*w/n,y+j*h/n,x+(i+1)*w/n,y+(j+1)*h/n))
                        if cell.is_empty:continue
                        color=col
                        if image:
                            fx=(i+.5)/n;fy=(j+.5)/n
                            if f.get('bookmatch') and ix%2:fx=1-fx
                            color=list(image.getpixel((min(image.width-1,int(fx*image.width)),min(image.height-1,int(fy*image.height)))))
                        flat(rotate(translate(cell,ox,oy),angle,origin=(0,0)),world,z,color,identifier,ceiling)
    for s in ss.values():
        ctx=context(d,s)
        if not ctx or s['kind'] in hidden:continue
        region,world=ctx
        if s.get('finish'):textured(region,world,0,s['finish'],s['id'],s['kind']=='ceiling')
        elif s['kind']=='ceiling':flat(region,world,0,[241,239,232],s['id'],True)
        elif s['kind']=='floor':flat(region,world,0,[226,220,210],s['id'])
    palette={'painting':[180,123,85],'mirror':[157,191,203],'sconce':[206,162,71],'switchboard':[245,243,237],'socket':[234,231,222],'tv':[45,50,56],'shelf':[157,114,75],'panel':[179,155,129],'pendant':[213,173,87],'downlight':[245,219,147],'fan':[144,131,114],'grille':[164,180,185],'track':[63,70,74],'profile':[249,223,159],'bulkhead':[225,225,215],'rug':[163,135,110],'threshold':[153,142,126],'border':[100,104,108]}
    for o in design.get('items',[]):
        s=ss.get(o['surface_id']);ctx=context(d,s) if s else None
        if not ctx or o['kind'] in hidden or s['kind'] in hidden:continue
        region,world=ctx
        def transform(g):return translate(rotate(g,o.get('rotation',0),origin=(0,0)),o['x'],o['y'])
        rect=transform(box(-o['width']/2,-o['height']/2,o['width']/2,o['height']/2));low=o.get('drop',0) if s['kind']=='ceiling' else 0;high=low+o['depth']
        if o.get('run'):
            from shapely import LineString
            rect=transform(LineString(o['run']).buffer(o['height']/2,cap_style=2,join_style=2))
        prism(rect,world,low,high,palette[o['kind']],o['id'])
        if s['kind']=='ceiling' and low>0:
            prism(box(o['x']-.007,o['y']-.007,o['x']+.007,o['y']+.007),world,0,low,[80,80,80],o['id'])
        if o.get('finish'):textured(rect,world,high+.001,o['finish'],o['id'])
        im=image_data(o.get('reference',{}).get('image'))
        if im and o['kind'] in ('painting','panel','tv'):
            iw,ih=o['width'],o['height']
            if o.get('reference',{}).get('crop'):
                im=ImageOps.fit(im,(max(1,round(256*iw/max(iw,ih))),max(1,round(256*ih/max(iw,ih)))))
            else:
                scale=min(iw/im.width,ih/im.height);iw,ih=im.width*scale,im.height*scale
            im=im.resize((32,32),Image.Resampling.BOX)
            for y in range(32):
                for x in range(32):
                    cell=transform(box((x/32-.5)*iw,(y/32-.5)*ih,((x+1)/32-.5)*iw,((y+1)/32-.5)*ih))
                    flat(cell,world,high+.001,list(im.getpixel((min(im.width-1,int(((31-x if s['kind']=='wall' and s['side']==1 else x)+.5)/32*im.width)),min(im.height-1,int((31-y+.5)/32*im.height))))),o['id'])
    return out
