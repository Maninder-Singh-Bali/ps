"""Low-poly library proxies shared by camera guides and the interactive viewer.

Recipes use unit-box coordinates. Horizontal coordinates are transformed in
source pixels (so rotating a non-square plan does not distort a model), then
returned normalized. Heights remain metres/illustrative scene units.
"""
import json, math
from pathlib import Path
from functools import lru_cache

@lru_cache(maxsize=1)
def catalog():
    return json.loads((Path(__file__).parent/'static/furniture-meshes.json').read_text(encoding='utf8'))

def component(x,y,z,w,d,h,material='fabric',role='body',type='box'):
    return dict(bounds=[x,y,z,w,d,h],material=material,role=role,type=type)

def sofa(item):
    """One cushion per saved seat; backs face outward on both L-shaped runs."""
    is_l=item.get('shape')=='l';m=item.get('sofa_modules') or {}
    total=max(1,min(12,int(item.get('seat_count') or 3)))
    main=int(m.get('main_seats',max(2,total-1) if is_l else total))
    ret=int(m.get('return_seats',max(1,total-main) if is_l else 0))
    lw=min(1,m.get('leg_width',item['width']*.4)/item['width'])
    ld=min(1,m.get('leg_depth',item['depth']*.4)/item['depth']) if is_l else 1
    px=(1-lw)/(main-1) if is_l else 1/main
    py=(1-ld)/max(1,ret)
    p=[]
    def add(x,y,z,w,d,h,material='fabric',role='body',type='box'):
        if w>0 and d>0 and h>0:p.append(component(x,y,z,w,d,h,material,role,type))
    def base(x,y,w,d):
        add(x,y,.15,w,d,.3)
        for a in (x+w*.1,x+w*.84):
            for b in (y+d*.1,y+d*.84):add(a,b,0,w*.06,d*.06,.15,'wood','leg')
    def seat(x,y,w,d):add(x,y,.45,w,d,.2,'cushion','seat','bevel')
    if is_l:
        base(0,1-ld,1,ld);base(0,0,lw,1-ld)
        bx=lw*.13;by=ld*.13
        add(0,0,.4,bx,1,.6,'fabric','back');add(bx,1-by,.4,1-bx,by,.6,'fabric','back')
        add(0,0,.45,lw,by,.32,'fabric','arm');add(1-bx,1-ld,.45,bx,ld,.32,'fabric','arm')
        seat(bx+.02*lw,1-ld+.03*ld,lw-bx-.04*lw,ld-by-.06*ld)
        for i in range(main-1):
            x=lw+i*px;seat(x+.035*px,1-ld+.03*ld,px*.93-(bx if i==main-2 else 0),ld-by-.06*ld)
        for i in range(ret):
            y=i*py;seat(bx+.02*lw,y+.035*py+(by if i==0 else 0),lw-bx-.04*lw,py*.93-(by if i==0 else 0))
        if item.get('return_side')=='right':
            for q in p:q['bounds'][0]=1-q['bounds'][0]-q['bounds'][3]
    else:
        base(0,0,1,1);arm=min(.09,.18/main)
        add(0,0,.4,1,.15,.6,'fabric','back');add(0,.15,.4,arm,.85,.38,'fabric','arm');add(1-arm,.15,.4,arm,.85,.38,'fabric','arm')
        pitch=(1-2*arm)/main
        for i in range(main):seat(arm+i*pitch+pitch*.035,.18,pitch*.93,.78)
    # 450 mm seat at the library's 850 mm back height.
    def seat_z(z):return z*(.45/.85)/.65 if z<=.65 else .45/.85+(z-.65)*(1-.45/.85)/.35
    for q in p:
        z,h=q['bounds'][2],q['bounds'][5];q['bounds'][2]=seat_z(z);q['bounds'][5]=seat_z(z+h)-seat_z(z)
    return p

def components(item):
    data=catalog();kind=item.get('kind','unknown');preset=item.get('preset_id','')
    if kind=='sofa':return sofa(item)
    if preset=='staircase-spiral':
        n=max(8,math.ceil((item.get('height_m') or 3)/.18));turn=math.pi*11/6
        parts=[component(.46,.46,0,.08,.08,1,'metal','column','cylinder')]
        for i in range(n):
            a=i*turn/n;b=(i+1)*turn/n
            parts.append({**component(0,0,max(0,(i+1)/n-.025),1,1,.025,'wood','step','sector'),'start':a,'end':b})
            parts.append(component(.5+.46*math.cos(b)-.012,.5+.46*math.sin(b)-.012,(i+1)/n,.024,.024,.25,'metal','railing','cylinder'))
        return parts
    if item.get('preset_id')=='staircase-l':
        n=max(4,math.ceil((item.get('height_m') or 3)/.18));first=math.ceil(n*.65);last=n-first;w=.48;d=.28
        return ([component(0,d+i*(1-d)/first,0,w,(1-d)/first,(first-i)/n,'stone','step') for i in range(first)]
                +[component(0,0,0,w,d,first/n,'stone','landing')]
                +[component(w+i*(1-w)/last,0,0,(1-w)/last,d,(first+i+1)/n,'stone','step') for i in range(last)])
    if kind=='stair':
        n=max(2,math.ceil((item.get('height_m') or 3)/.18))
        return [component(0,i/n,0,1,1/n,(n-i)/n,'stone','step') for i in range(n)]
    key=preset if preset in data['recipes'] else data['defaults'].get(kind,'unknown')
    if item.get('shape')=='round' and kind in ('table','pillar'):key='table-round' if kind=='table' else 'pillar-round'
    return data['recipes'][key]

def instances(item,plan):
    m=item.get('chair_modules')
    if item.get('kind')!='chair' or not m:return [item]
    a=math.radians(item.get('angle',0));c,s=math.cos(a),math.sin(a);out=[]
    for row in range(m['rows']):
        for col in range(m['columns']):
            x=(-item['width']/2+m['width']/2+col*m['width']*1.15)*plan['width']
            y=(-item['depth']/2+m['depth']/2+row*m['depth']*1.15)*plan['height']
            out.append({**item,'chair_modules':None,'width':m['width'],'depth':m['depth'],'x':item['x']+(x*c-y*s)/plan['width'],'y':item['y']+(x*s+y*c)/plan['height']})
    return out

def primitive(p):
    x,y,z,w,d,h=p['bounds'];axis=p.get('axis','z');kind=p['type']
    if axis=='y':y,z,d,h=z,y,h,d
    if kind=='sector':
        angles=[p['start']+(p['end']-p['start'])*i/3 for i in range(4)]
        poly=[[.5+.46*math.cos(a),.5+.46*math.sin(a)] for a in angles]+[[.5+.055*math.cos(a),.5+.055*math.sin(a)] for a in reversed(angles)]
    elif kind=='cylinder':poly=[[(math.cos(i*math.pi/6)+1)/2,(math.sin(i*math.pi/6)+1)/2] for i in range(12)]
    elif kind=='bevel':poly=[[.1,0],[.9,0],[1,.1],[1,.9],[.9,1],[.1,1],[0,.9],[0,.1]]
    else:poly=[[0,0],[1,0],[1,1],[0,1]]
    scale=p.get('top_scale',1)
    bottom=[[x+a*w,y+b*d,z] for a,b in poly]
    top=[[x+(.5+(a-.5)*scale)*w,y+(.5+(b-.5)*scale)*d,z+h] for a,b in poly]
    faces=[(bottom,.65),(top,1.)]+[([bottom[i],bottom[(i+1)%len(poly)],top[(i+1)%len(poly)],top[i]],.76+.12*(i%3)/2) for i in range(len(poly))]
    if axis=='y':faces=[([[a,c,b] for a,b,c in points],shade) for points,shade in faces]
    return faces

def mesh(item,plan):
    out=[];materials=catalog()['materials']
    for unit in instances(item,plan):
        a=math.radians(unit.get('angle',0));c,s=math.cos(a),math.sin(a)
        W=unit['width']*plan['width'];D=unit['depth']*plan['height'];H=unit.get('height_m',.45 if unit.get('kind')=='table' else .8)
        for part in components(unit):
            color=materials[part['material']]
            for points,shade in primitive(part):
                vertices=[]
                for x,y,z in points:
                    if unit.get('flip_x'):x=1-x
                    if unit.get('flip_y'):y=1-y
                    x=(x-.5)*W;y=(y-.5)*D
                    vertices.append([unit['x']+(x*c-y*s)/plan['width'],unit['y']+(x*s+y*c)/plan['height'],z*H+unit.get('elevation_m',0)])
                out.append({'points':vertices,'color':[math.floor(v*shade+.5) for v in color],'part':part['role']})
    return out
