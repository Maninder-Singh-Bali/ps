"""Derived joined wall footprints. Editable reference lines never move.

Exact endpoint/intersection topology only; no proximity gap closing. Offset-face
intersections form mitres at exposed sectors, with a bounded bevel for acute
angles. GEOS unions the envelope once, and height slices subtract real openings.
All consumers share this resolver. It is opt-in for correction drafts only.
"""
import copy,hashlib,json,math
from shapely import Polygon,LineString,Point,GeometryCollection,unary_union,constrained_delaunay_triangles,make_valid
from drawing_scene import hosted_features,cut_walls
EPS=1e-6
MITRE_LIMIT=3.0

def cross(a,b):return a[0]*b[1]-a[1]*b[0]
def polygons(g):
    if g.is_empty:return []
    if g.geom_type=='Polygon':return [g]
    return [p for c in getattr(g,'geoms',()) for p in polygons(c)]
def rings(g):return [{'outer':[list(p) for p in q.exterior.coords[:-1]],'holes':[[list(p) for p in r.coords[:-1]] for r in q.interiors]} for q in polygons(g)]
def offset(p,u,h,sign=1):return [p[0]-u[1]*h*sign,p[1]+u[0]*h*sign]

def envelope(walls):
    """Union flat-ended strips with the true offset envelope at shared nodes."""
    if not walls:return GeometryCollection(),[]
    bodies=[];nodes={};segments=[]
    def node(p):
        # Numerical equality, not a drafting snap tolerance. Original points stay exact.
        key=tuple(round(v,6) for v in p)
        if key not in nodes:nodes[key]={'point':list(p),'rays':[]}
        return nodes[key]
    for f in walls:
        a,b=f['points'];L=math.dist(a,b)
        if L<EPS:continue
        u=[(b[i]-a[i])/L for i in range(2)];h=f['thickness']/2
        bodies.append(Polygon([offset(a,u,h),offset(b,u,h),offset(b,u,h,-1),offset(a,u,h,-1)]))
        segments.append((a,b,u,L,h,f['id']))
        node(a);node(b)
    # T and crossing nodes are calculated at line intersections, without changing
    # or subdividing the stored wall references.
    for i,(a,b,*_) in enumerate(segments):
        for c,d,*_ in segments[i+1:]:
            hit=LineString([a,b]).intersection(LineString([c,d]))
            if hit.geom_type=='Point':node(hit.coords[0])
            elif hit.geom_type=='MultiPoint':
                for p in hit.geoms:node(p.coords[0])
    for n in nodes.values():
        p=n['point'];rays=[]
        for a,b,u,L,h,fid in segments:
            t=sum((p[i]-a[i])*u[i] for i in range(2));side=abs(cross(u,[p[i]-a[i] for i in range(2)]))
            if side>EPS or t<-EPS or t>L+EPS:continue
            if t>EPS:rays.append({'u':[-v for v in u],'h':h,'length':t,'id':fid})
            if t<L-EPS:rays.append({'u':u,'h':h,'length':L-t,'id':fid})
        # Coincident rays have one visible outer face, using the largest thickness.
        unique={}
        for r in rays:
            angle=math.atan2(r['u'][1],r['u'][0])%(2*math.pi);key=round(angle,9)
            if key not in unique or r['h']>unique[key]['h']:unique[key]={**r,'angle':angle}
        n['rays']=sorted(unique.values(),key=lambda r:r['angle'])
    joins=[];bodies=[]
    for n in nodes.values():
        rs=n['rays'];p=n['point'];corners=[]
        if len(rs)==1:
            r=rs[0];r['left']=offset(p,r['u'],r['h']);r['right']=offset(p,r['u'],r['h'],-1);continue
        for r,s in zip(rs,rs[1:]+rs[:1]):
            a=offset(p,r['u'],r['h']);b=offset(p,s['u'],s['h'],-1)
            den=cross(r['u'],s['u']);q=None
            if abs(den)>1e-10:
                t=cross([b[i]-a[i] for i in range(2)],s['u'])/den;q=[a[i]+t*r['u'][i] for i in range(2)]
            bound=min(MITRE_LIMIT*max(r['h'],s['h']),max(r['h'],min(r['length'],s['length'])*.45))
            bevel=q is None or math.dist(p,q)>bound
            if bevel:
                r['left']=a;s['right']=b;corners.extend([a,b])
            else:r['left']=q;s['right']=q;corners.append(q)
            gap=(s['angle']-r['angle'])%(2*math.pi)
            if gap>math.pi+1e-9:joins.append({'point':p,'walls':[r['id'],s['id']],'kind':'bevel' if bevel else 'mitre','limit_px':bound})
        # This cell is the shared offset junction itself. It is unioned with
        # incident wall bodies before drawing/extruding; never overpainted.
        if len(corners)>=3:
            cell=Polygon(corners)
            if not cell.is_valid:cell=make_valid(cell)
            bodies.extend(polygons(cell))
    def along(segment,p):
        a,b,u,L,h,fid=segment;t=sum((p[i]-a[i])*u[i] for i in range(2))
        return t if abs(cross(u,[p[i]-a[i] for i in range(2)]))<=EPS and -EPS<=t<=L+EPS else None
    def ray(n,u):return min(n['rays'],key=lambda r:math.dist(r['u'],u))
    for segment in segments:
        a,b,u,L,h,fid=segment
        ns=sorted([(t,n) for n in nodes.values() if (t:=along(segment,n['point'])) is not None],key=lambda item:item[0])
        for (ta,na),(tb,nb) in zip(ns,ns[1:]):
            if tb-ta<EPS:continue
            r=ray(na,u);s=ray(nb,[-v for v in u])
            # Each individual wall stops at the shared offset-face intersection,
            # rather than leaving its independent rectangular cap under a join.
            cell=Polygon([r['left'],s['right'],s['left'],r['right']])
            if not cell.is_valid:cell=make_valid(cell)
            bodies.extend(polygons(cell))
    return unary_union(bodies),joins

def at_height(features,height=None,default_height=2.5):
    rows=hosted_features(features);walls=[f for f in rows if f['kind']=='wall' and (height is None or height<f.get('height_m',default_height)-1e-9)]
    openings=[]
    for f in rows:
        if f['kind'] not in ('door','window','sliding_door'):continue
        lo=f.get('sill_m',.9) if f['kind']=='window' else f.get('base_m',0)
        hi=f.get('head_m',2.2 if f['kind']=='door' else 2.4)
        if height is None or lo<=height<hi:openings.append(f)
        elif not f.get('host_wall_id') and height<f.get('height_m',default_height)-1e-9:
            # Legacy traces store the window/door span separately from side walls.
            # Restore only their existing vertical solid bands; no host is inferred.
            walls.append({**f,'id':'band:'+f['id'],'kind':'wall'})
    pieces=[f for f in cut_walls(walls+openings) if f['kind']=='wall']
    return envelope(pieces)

def resolve(features,default_height=2.5):
    shape,joins=at_height(features,default_height=default_height)
    result={'version':1,'method':'joined offset polygon union; exact topology; bounded mitre/bevel','rings':rings(shape),'joins':joins,'area_px2':shape.area,'reference_lines_unchanged':True}
    result['hash']=hashlib.sha256(json.dumps(result,sort_keys=True).encode()).hexdigest();return result

def mesh(features,mpp,origin,default_height=2.5):
    rows=hosted_features(features);levels={0.,default_height}
    for f in rows:
        if f['kind']=='wall':levels.add(float(f.get('height_m',default_height)))
        elif f['kind'] in ('door','window','sliding_door'):
            levels.add(float(f.get('head_m',2.2 if f['kind']=='door' else 2.4)))
            levels.add(float(f.get('sill_m',.9) if f['kind']=='window' else f.get('base_m',0)))
    levels=sorted(z for z in levels if z>=0);slabs=[]
    for low,high in zip(levels,levels[1:]):
        g,_=at_height(rows,(low+high)/2,default_height);slabs.append((low,high,g))
    result=[]
    def xyz(p,z):return [(p[0]-origin[0])*mpp,(p[1]-origin[1])*mpp,z]
    def face(ps,col,mask):result.append({'points':ps,'color':col,'kind':'joined_wall','edge_mask':mask,'joined_wall':True})
    empty=GeometryCollection()
    for k,(low,high,g) in enumerate(slabs):
        if g.is_empty:continue
        below=slabs[k-1][2] if k else empty;above=slabs[k+1][2] if k+1<len(slabs) else empty
        bottom=g.difference(below);top=g.difference(above)
        for surface,z,top_side in [(bottom,low,False),(top,high,True)]:
            for poly in polygons(surface):
                boundary=poly.boundary
                for tri in constrained_delaunay_triangles(poly).geoms:
                    ps=list(tri.exterior.coords[:-1]);mask=[boundary.covers(LineString([a,b])) for a,b in zip(ps,ps[1:]+ps[:1])]
                    face([xyz(p,z) for p in ps],[238,236,231] if top_side else [204,202,197],mask)
        for poly in polygons(g):
            for ring in [poly.exterior,*poly.interiors]:
                ps=list(ring.coords[:-1]);N=len(ps)
                for i,a in enumerate(ps):
                    b=ps[(i+1)%N];prev=ps[(i-1)%N];after=ps[(i+2)%N];line=LineString([a,b]);u=[b[j]-a[j] for j in range(2)];L=math.hypot(*u)
                    turn_a=abs(cross([a[j]-prev[j] for j in range(2)],u))>EPS
                    turn_b=abs(cross(u,[after[j]-b[j] for j in range(2)]))>EPS
                    # Only real exterior edges; no triangulation diagonals or
                    # internal horizontal seams at sill/head slicing levels.
                    mask=[not bottom.is_empty and bottom.boundary.covers(line),turn_b,not top.is_empty and top.boundary.covers(line),turn_a]
                    shade=.85+.11*abs(u[0]/L) if L else 1
                    face([xyz(a,low),xyz(b,low),xyz(b,high),xyz(a,high)],[round(v*shade) for v in [232,229,222]],mask)
    return result
