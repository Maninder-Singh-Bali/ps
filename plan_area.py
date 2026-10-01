"""Drawing-ratio measurements. Coordinates refer to the ORIGINAL plan image.

Areas use polygon integration, not enlarged preview pixels. Scanline slabs are
split at vertices and edge crossings so unions and overlaps are counted once.
"""
import math
from store import editing_busy, uid, now

EPS = 1e-10

def cross(a,b,c):
    return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])

def edges(p): return list(zip(p,p[1:]+p[:1]))
def area(p): return abs(sum(a[0]*b[1]-b[0]*a[1] for a,b in edges(p)))/2
def box_polygon(b):
    x,y,w,h=b
    return [[x,y],[x+w,y],[x+w,y+h],[x,y+h]]
def bounds(p):
    xs,ys=zip(*p);return [min(xs),min(ys),max(xs)-min(xs),max(ys)-min(ys)]

def crossing(a,b,c,d):
    den=(b[0]-a[0])*(d[1]-c[1])-(b[1]-a[1])*(d[0]-c[0])
    if abs(den)<EPS:return None
    t=((c[0]-a[0])*(d[1]-c[1])-(c[1]-a[1])*(d[0]-c[0]))/den
    u=((c[0]-a[0])*(b[1]-a[1])-(c[1]-a[1])*(b[0]-a[0]))/den
    if -EPS<=t<=1+EPS and -EPS<=u<=1+EPS:return [a[0]+t*(b[0]-a[0]),a[1]+t*(b[1]-a[1])]

def on_segment(a,b,p):
    return abs(cross(a,b,p))<EPS and min(a[0],b[0])-EPS<=p[0]<=max(a[0],b[0])+EPS and min(a[1],b[1])-EPS<=p[1]<=max(a[1],b[1])+EPS

def polygon(value):
    if not isinstance(value,list) or not 3<=len(value)<=64:raise ValueError('Outline each area with 3 to 64 corners.')
    p=[]
    for v in value:
        if not isinstance(v,list) or len(v)!=2 or not all(type(n) in (int,float) and math.isfinite(n) and 0<=n<=1 for n in v):raise ValueError('Keep all outline corners inside the drawing.')
        p.append([float(n) for n in v])
    es=edges(p)
    for i,(a,b) in enumerate(es):
        if math.dist(a,b)<1e-7:raise ValueError('Remove repeated outline corners.')
        for j,(c,d) in enumerate(es[i+1:],i+1):
            if j==i+1 or (i==0 and j==len(es)-1):continue
            if crossing(a,b,c,d) is not None or on_segment(a,b,c) or on_segment(a,b,d):raise ValueError('Outline lines must not cross or touch themselves.')
    if area(p)<1e-7:raise ValueError('Choose an area with a visible width and depth.')
    return p

def intervals(p,x):
    ys=sorted(a[1]+(x-a[0])*(b[1]-a[1])/(b[0]-a[0]) for a,b in edges(p) if min(a[0],b[0])<x<max(a[0],b[0]))
    return list(zip(ys[::2],ys[1::2]))
def merge(iv):
    out=[]
    for a,b in sorted(iv):
        if out and a<=out[-1][1]+EPS:out[-1][1]=max(out[-1][1],b)
        else:out.append([a,b])
    return out
def clip(iv,mask):return [(max(a,c),min(b,d)) for a,b in iv for c,d in mask if min(b,d)>max(a,c)]
def length(iv):return sum(b-a for a,b in iv)
def subtract(iv,holes):
    for c,d in merge(holes):
        out=[]
        for a,b in iv:
            if d<=a or c>=b:out.append([a,b]);continue
            if a<c:out.append([a,c])
            if d<b:out.append([d,b])
        iv=out
    return iv

def proportions(outline,sections,holes=None):
    holes=holes or [];allp=[outline]+sections+holes;es=[e for p in allp for e in edges(p)]
    cuts={p[0] for poly in allp for p in poly}
    for i,(a,b) in enumerate(es):
        for c,d in es[i+1:]:
            q=crossing(a,b,c,d)
            if q is not None:cuts.add(q[0])
    cuts=sorted(cuts);values=[0.]*len(sections);covered=0.;total=0.
    for x1,x2 in zip(cuts,cuts[1:]):
        if x2-x1<EPS:continue
        x=(x1+x2)/2;mask=subtract(intervals(outline,x),[iv for hole in holes for iv in intervals(hole,x)]);combined=[];total+=length(mask)*(x2-x1)
        for i,p in enumerate(sections):
            iv=clip(intervals(p,x),mask);values[i]+=length(iv)*(x2-x1);combined+=iv
        covered+=length(merge(combined))*(x2-x1)
    if total<1e-7:raise ValueError('The exclusions leave no measurable floor area.')
    return {'total':total,'sections':values,'covered':covered,'remaining':max(0,total-covered),'overlap':max(0,sum(values)-covered),'outside':sum(max(0,area(p)-v) for p,v in zip(sections,values))}

def calibration(data,outline,width,height,net_area=None):
    if not isinstance(data,dict):raise ValueError('Choose a measurement method.')
    mode=data.get('mode','percent');unit=data.get('unit','m')
    if unit not in ('m','ft'):raise ValueError('Choose metres or feet.')
    c={'mode':mode,'unit':unit};factor=1 if unit=='m' else .3048
    def number(k):
        v=data.get(k)
        if type(v) not in (int,float) or not math.isfinite(v) or not 0<v<1e9:raise ValueError('Enter a positive, finite measurement.')
        c[k]=float(v);return v
    if mode=='percent':return c,None
    if mode=='dimensions':
        w=number('width');h=number('height');b=bounds(outline)
        # Bounding span dimensions scale each drawing axis. L-shaped voids stay excluded.
        return c,w*h*factor**2/(b[2]*b[3])
    if mode=='area':return c,number('value')*factor**2/(net_area if net_area is not None else area(outline))
    if mode=='line':
        value=number('value');line=data.get('points')
        if not isinstance(line,list) or len(line)!=2:raise ValueError('Mark both ends of a known length on the drawing.')
        for p in line:
            if not isinstance(p,list) or len(p)!=2 or not all(type(n) in (int,float) and math.isfinite(n) and 0<=n<=1 for n in p):raise ValueError('Mark the line inside the drawing.')
        dist=math.hypot((line[1][0]-line[0][0])*width,(line[1][1]-line[0][1])*height)
        if dist<2:raise ValueError('Mark a longer calibration line for a reliable ratio.')
        c['points']=line
        return c,(value*factor/dist)**2*width*height
    raise ValueError('Unknown measurement method.')

def summarize(outline,sections,scale,width,height,holes=None):
    result=proportions(outline,sections,holes);clean,multiplier=calibration(scale,outline,width,height,result['total'])
    result['percentages']=[v/result['total']*100 for v in result['sections']]
    result['remaining_percent']=result['remaining']/result['total']*100
    result['area_m2']=None if multiplier is None else {k:[v*multiplier for v in a] if isinstance(a,list) else a*multiplier for k,a in result.items() if k in ('total','sections','covered','remaining','overlap','outside')}
    result['calibration']=clean
    return result

def exclusions(data):
    values=data.get('exclusions',[])
    if not isinstance(values,list) or len(values)>20:raise ValueError('Use up to 20 excluded areas.')
    return [polygon(v) for v in values]

def save_measurement(st,pid,plan_id,data):
    p=st.project(pid)
    if plan_id not in p['floor_plans']:raise ValueError('Choose a floor plan from this project.')
    if editing_busy(st,pid):raise ValueError('Finish the active generation before changing measured boundaries.')
    if data.get('map_revision')!=p['map_revision'] or data.get('area_revision',0)!=p.get('area_revision',0):raise ValueError('The plan changed while this editor was open. Reopen it before saving.')
    floor=str(data.get('floor','')).strip()[:50]
    if not floor:raise ValueError('Name this floor.')
    outline=polygon(data.get('outline'));holes=exclusions(data);rows=data.get('sections')
    if not isinstance(rows,list) or len(rows)>60:raise ValueError('Use up to 60 sections per floor.')
    seen=set();clean=[];new=[]
    for row in rows:
        if not isinstance(row,dict):raise ValueError('Invalid section.')
        room_id=row.get('room_id');name=str(row.get('name','')).strip()[:100]
        if room_id:
            r=st.room(pid,room_id)
            if r['plan_id']!=plan_id or r['floor']!=floor or room_id in seen:raise ValueError('Each section must belong to this plan and floor.')
            seen.add(room_id);name=r['name']
        elif not name:raise ValueError('Name each new section.')
        poly=polygon(row.get('polygon'));b=bounds(poly)
        if b[2]<.005 or b[3]<.005:raise ValueError('The section is too narrow to map reliably.')
        clean.append({'room_id':room_id,'name':name,'polygon':poly,'bbox':b,'kind':row.get('kind','room') if row.get('kind') in ('room','circulation','outdoor') else 'room'})
    if sum(len(r['polygon']) for r in clean)>1200:raise ValueError('Simplify outlines to fewer corners.')
    a=st.asset(plan_id);result=summarize(outline,[r['polygon'] for r in clean],data.get('scale',{}),a['width'],a['height'],holes)
    map_changed=False
    for row in clean:
        if row['room_id']:
            r=st.room(pid,row['room_id']);previous=r.get('area_polygon') if r.get('area_bbox')==r.get('bbox') else None
            previous=previous or (box_polygon(r['bbox']) if r.get('bbox') else None)
            changed=previous!=row['polygon']
            if changed:
                r['bbox']=row['bbox'];st.invalidate(pid,r);map_changed=True
        else:
            r={'id':uid(),'name':row['name'],'floor':floor,'kind':row['kind'],'plan_id':plan_id,'bbox':row['bbox'],'notes':'','references':[],'anchor_id':None,'images':[],'videos':[],'approved_image_id':None,'approved_video_id':None,'revision':1,'confidence':'manual','detection_note':'Section boundary drawn in the area editor.'}
            p['rooms'].append(r);row['room_id']=r['id'];map_changed=True
        r['area_polygon']=row['polygon'];r['area_bbox']=r['bbox'][:]
    record={'plan_id':plan_id,'floor':floor,'outline':outline,'exclusions':holes,'scale':result['calibration'],'sections':[{'room_id':r['room_id'],'polygon':r['polygon']} for r in clean],'updated':now()}
    p['measurements']=[v for v in p.get('measurements',[]) if not (v['plan_id']==plan_id and v['floor']==floor)]+[record]
    p['area_revision']=p.get('area_revision',0)+1;p['updated']=now()
    if map_changed:p['map_revision']+=1;p['map_confirmed']=False
    st.save();return {'measurement':record,'summary':result,'map_changed':map_changed}
