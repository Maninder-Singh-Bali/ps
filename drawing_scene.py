"""Resolve classified drawing geometry for previews and generation without editing the plan.

Only explicitly classified architecture is lifted. Curves retain their source
path and use bounded-tolerance tessellation. Unknown paths stay unresolved;
bounding boxes and section boundaries are never substituted for walls.
"""
import copy
import math
import re
from xml.etree import ElementTree as ET

NUM=r'[-+]?(?:\d*\.\d+|\d+\.?\d*)(?:[eE][-+]?\d+)?'
IDENTITY=(1.,0.,0.,1.,0.,0.)

def mul(a,b):
    return (a[0]*b[0]+a[2]*b[1],a[1]*b[0]+a[3]*b[1],a[0]*b[2]+a[2]*b[3],a[1]*b[2]+a[3]*b[3],a[0]*b[4]+a[2]*b[5]+a[4],a[1]*b[4]+a[3]*b[5]+a[5])

def point(m,p):return [m[0]*p[0]+m[2]*p[1]+m[4],m[1]*p[0]+m[3]*p[1]+m[5]]

def matrix(text):
    out=IDENTITY
    for match in re.finditer(r'([a-zA-Z]+)\s*\(([^)]*)\)',text or ''):
        name=match[1];v=list(map(float,re.findall(NUM,match[2])))
        if name=='translate' and len(v) in (1,2):m=(1,0,0,1,v[0],v[1] if len(v)>1 else 0)
        elif name=='scale' and len(v) in (1,2):m=(v[0],0,0,v[-1],0,0)
        elif name=='rotate' and len(v) in (1,3):
            t=math.radians(v[0]);c,s=math.cos(t),math.sin(t);m=(c,s,-s,c,0,0)
            if len(v)==3:m=mul(mul((1,0,0,1,v[1],v[2]),m),(1,0,0,1,-v[1],-v[2]))
        elif name=='matrix' and len(v)==6:m=tuple(v)
        else:raise ValueError('Unsupported SVG transform')
        out=mul(out,m)
    if re.sub(r'[a-zA-Z]+\s*\([^)]*\)','',text or '').strip(' ,\t\r\n'):raise ValueError('Invalid transform')
    return out

def segments(d):
    """Straight SVG subpaths; curves are intentionally not approximated as walls."""
    if re.search(r'[a-df-gi-kno-uw-yA-DF-GI-KNO-UW-Y]',re.sub(NUM,'',d)):raise ValueError('Curved or unsupported path')
    tokens=re.findall(r'[MLHVZmlhvz]|'+NUM,d);out=[];p=[0.,0.];start=p[:];i=0;cmd=None
    while i<len(tokens):
        if tokens[i].isalpha():cmd=tokens[i];i+=1
        if not cmd:raise ValueError('Invalid path')
        rel=cmd.islower();op=cmd.upper()
        if op=='Z':
            if p!=start:out.append((p[:],start[:]))
            p=start[:];cmd=None;continue
        n=2 if op in ('M','L') else 1
        values=list(map(float,tokens[i:i+n]));i+=n
        if len(values)!=n:raise ValueError('Invalid path')
        q=[values[0]+(p[0] if rel else 0),values[1]+(p[1] if rel else 0)] if n==2 else ([values[0]+(p[0] if rel else 0),p[1]] if op=='H' else [p[0],values[0]+(p[1] if rel else 0)])
        if op=='M':start=q[:];cmd='l' if rel else 'L'
        elif p!=q:out.append((p[:],q[:]))
        p=q
    return out

def straight_nodes(node,parent=IDENTITY):
    m=mul(parent,matrix(node.get('transform')));tag=node.tag.split('}')[-1]
    if tag=='g':
        return [v for child in node for v in straight_nodes(child,m)]
    val=lambda key,default=0:float(node.get(key,default))
    if tag=='rect':
        x,y,w,h=val('x'),val('y'),val('width'),val('height')
        if min(w,h)<=0:raise ValueError('Empty rectangle')
        if w>=h:raw=[([x,y+h/2],[x+w,y+h/2],h)]
        else:raw=[([x+w/2,y],[x+w/2,y+h],w)]
    elif tag=='line':raw=[([val('x1'),val('y1')],[val('x2'),val('y2')],1.5)]
    elif tag=='path':
        from curve_geometry import segments as curve_segments
        scale_bound=max(math.hypot(m[0],m[1])+math.hypot(m[2],m[3]),1)
        raw=[(a,b,float(node.get('stroke-width',1.5))) for a,b in curve_segments(node.get('d',''),.25/scale_bound)]
    elif tag in ('polyline','polygon'):
        vs=list(map(float,re.findall(NUM,node.get('points',''))));ps=list(zip(vs[::2],vs[1::2]));raw=[(a,b,1.5) for a,b in zip(ps,ps[1:]+(ps[:1] if tag=='polygon' else []))]
    else:raise ValueError('Unsupported architectural symbol')
    out=[]
    for a,b,t in raw:
        length=math.dist(a,b)
        if length<1e-8:continue
        p,q=point(m,a),point(m,b);scale=math.dist(p,q)/length
        # Normal thickness under the affine transformation, independent of orientation.
        thickness=t*abs(m[0]*m[3]-m[1]*m[2])/max(scale,1e-9)
        out.append({'points':[p,q],'thickness':thickness})
    return out

def door(node,edit):
    """Read the hinge/leaf and closed endpoint from a quarter-circle door symbol."""
    leaves=[];arcs=[]
    def walk(n,parent):
        m=mul(parent,matrix(n.get('transform')))
        if n.tag.split('}')[-1]=='path':
            d=n.get('d','')
            if re.search('[Aa]',d):
                match=re.fullmatch(r'\s*M\s*('+NUM+r')[ ,]+('+NUM+r')\s*A\s*('+NUM+r')[ ,]+('+NUM+r')[ ,]+('+NUM+r')[ ,]+([01])[ ,]+([01])[ ,]+('+NUM+r')[ ,]+('+NUM+r')\s*',d)
                if not match:raise ValueError('Unrecognized door arc')
                x,y,rx,ry,rotation,large,sweep,ex,ey=map(float,match.groups())
                if large or abs(rx-ry)>.01 or rotation:raise ValueError('Unrecognized door arc')
                arcs.append([point(m,[x,y]),point(m,[ex,ey])])
            else:leaves.extend(straight_nodes(n,parent))
        else:
            for c in n:walk(c,m)
    walk(node,edit)
    if len(leaves)!=1 or len(arcs)!=1:raise ValueError('Unrecognized door symbol')
    a,b=leaves[0]['points'];u,v=arcs[0]
    if math.dist(b,v)<.01:hinge,closed,tip=a,u,b
    elif math.dist(b,u)<.01:hinge,closed,tip=a,v,b
    elif math.dist(a,v)<.01:hinge,closed,tip=b,u,a
    elif math.dist(a,u)<.01:hinge,closed,tip=b,v,a
    else:raise ValueError('Door arc does not meet leaf')
    dx,dy=closed[0]-hinge[0],closed[1]-hinge[1]
    return {'points':[hinge,closed],'leaf_points':[hinge,tip],'thickness':leaves[0]['thickness'],'flip':dx*(tip[1]-hinge[1])-dy*(tip[0]-hinge[0])<0}

def hosted_features(features):
    """Resolve attached openings from host coordinates without changing saved evidence."""
    rows=copy.deepcopy(features);walls={f['id']:f for f in rows if f['kind']=='wall'}
    for f in rows:
        if not f.get('host_wall_id'):continue
        wall=walls.get(f['host_wall_id'])
        if not wall:continue
        a,b=wall['points'];length=math.dist(a,b)
        if length<1e-8:continue
        u=[(b[i]-a[i])/length for i in range(2)];offset=f['offset'];width=f['width']
        normal=f.get('normal_offset',0);n=[-u[1],u[0]]
        f['points']=[[a[i]+u[i]*t+n[i]*normal for i in range(2)] for t in (offset,offset+width)]
        if f.get('hinge_end'):f['points'].reverse()
        f['thickness']=f.get('frame_thickness',wall.get('thickness',1.5))
        f['height_m']=wall.get('height_m') if wall.get('height_m') is not None else f.get('height_m')
        if f['height_m'] is None:f.pop('height_m')
    return rows

def resolve(doc):
    from drawing_editor import transform
    rows=[];unresolved=[]
    for e in doc.get('elements',[]):
        if e.get('absorbed_by') or doc.get('edits',{}).get(e['id'],{}).get('hidden'):continue
        if e['kind'] not in ('wall','window','door','opening','sliding_door'):continue
        try:
            root=ET.fromstring(e['svg']);m=matrix(transform(doc.get('edits',{}).get(e['id'],{})))
            kind='door' if e['kind']=='opening' else e['kind']
            found=[door(root,m)] if kind=='door' and e.get('origin')!='raster_candidate' else straight_nodes(root,m)
            if not found:raise ValueError('Empty architecture')
            rows.extend({**f,'id':e['id']+(f':{i}' if len(found)>1 else ''),'source_id':e['id'],'native_source_id':e.get('native_source_id'),'kind':kind,'source_geometry':e['svg'],'curve_tolerance_px':.25} for i,f in enumerate(found))
        except (ValueError,TypeError,IndexError,ImportError,ET.ParseError):unresolved.append(e['id'])
    rows.extend({**copy.deepcopy(f),'source_id':f.get('id',f'typed:{i}')} for i,f in enumerate(hosted_features(doc.get('features',[]))) if f['kind'] not in ('line','floor_opening'))
    # Window rectangles often also contain a center stroke. Keep one volume.
    unique=[];endpoints={}
    for row in rows:
        if len(row.get('points',[]))!=2 or any(not math.isfinite(v) for p in row['points'] for v in p):
            unique.append(row);continue # retain invalid evidence for validation
        # Index both endpoints so reversed spans retain the same tolerance and
        # first-source precedence without comparing every pair on every review.
        x,y=row['points'][0];gx,gy=math.floor(x/.01),math.floor(y/.01);near=set()
        for dx in (-1,0,1):
            for dy in (-1,0,1):near.update(endpoints.get((row['kind'],gx+dx,gy+dy),()))
        duplicate=next((unique[i] for i in sorted(near) if min(max(math.dist(a,b) for a,b in zip(unique[i]['points'],row['points'])),max(math.dist(a,b) for a,b in zip(unique[i]['points'],row['points'][::-1])))<.01),None)
        if duplicate:duplicate['thickness']=max(duplicate.get('thickness',1.5),row.get('thickness',1.5))
        else:
            index=len(unique);unique.append(row)
            for x,y in row['points']:endpoints.setdefault((row['kind'],math.floor(x/.01),math.floor(y/.01)),[]).append(index)
    return unique,unresolved

def cut_walls(rows):
    """Split only wall spans actually overlapped by a parallel mapped opening."""
    out=[];openings=[r for r in rows if r['kind'] in ('door','window','sliding_door')]
    for wall in rows:
        if wall['kind']!='wall':out.append(wall);continue
        a,b=wall['points'];length=math.dist(a,b)
        if length<1e-8:continue
        u=[(b[i]-a[i])/length for i in range(2)];cuts=[]
        for o in openings:
            if o.get('host_wall_id') and o['host_wall_id']!=wall.get('id'):continue
            p,q=o['points'];ol=math.dist(p,q)
            if ol<1e-8 or abs(u[0]*(q[1]-p[1])-u[1]*(q[0]-p[0]))/ol>.01:continue
            tolerance=(wall.get('thickness',1.5)+o.get('thickness',1.5))/2+.05
            if max(abs(u[0]*(v[1]-a[1])-u[1]*(v[0]-a[0])) for v in (p,q))>tolerance:continue
            lo,hi=sorted(sum((v[i]-a[i])*u[i] for i in range(2)) for v in (p,q));lo=max(0,lo);hi=min(length,hi)
            if hi-lo>1e-6:cuts.append((lo,hi))
        cursor=0
        for lo,hi in sorted(cuts)+[(length,length)]:
            if lo>cursor+1e-6:out.append({**wall,'points':[[a[i]+u[i]*t for i in range(2)] for t in (cursor,lo)]})
            cursor=max(cursor,hi)
    return out

def load(store,plan):
    from drawing_editor import get_document
    cache=getattr(store,'_review_cache',None);key=('architecture',plan['id'])
    if cache is not None and key in cache:return copy.deepcopy(cache[key])
    doc=get_document(store,plan['project_id'],plan['id'])
    result=resolve(doc)
    if cache is not None:cache[key]=copy.deepcopy(result)
    return result
