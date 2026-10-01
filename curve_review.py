"""Curves require provenance and correspondence, never just a shared bounding box."""
import hashlib,json,math,re

def token(value):return hashlib.sha256(json.dumps(value,sort_keys=True).encode()).hexdigest()

def curves(plan,architecture):
    from raster_identity import correction_for
    candidates={w['id']:w for key in ('walls','uncertain_spans') for w in plan.get('raster_geometry',{}).get(key,[])}
    groups={}
    for row in architecture:
        if row['kind']=='wall':groups.setdefault(row['source_id'],[]).append(row)
    out={}
    for key,rows in groups.items():
        item=candidates.get(key)
        if item:
            correction=correction_for(plan,key)
            if correction.get('action')!='accept' or correction.get('points'):continue
            provenance=item.get('geometry',{}).get('type') in ('arc','spline')
        else:
            # A source SVG arc/Bezier is evidence of a curve; an L/polyline is not.
            from xml.etree import ElementTree as ET
            try:provenance=any(re.search('[AaCcQqSsTt]',n.get('d','')) for r in rows for n in ET.fromstring(r.get('source_geometry') or '<g/>').iter())
            except ET.ParseError:provenance=False
        if not provenance:continue
        points=[rows[0]['points'][0]]
        for row in rows:
            if math.dist(points[-1],row['points'][0])>.5:break
            points.append(row['points'][1])
        else:
            if len(points)<5:continue
            turns=[]
            for a,b,c in zip(points,points[1:],points[2:]):
                u=[b[i]-a[i] for i in (0,1)];v=[c[i]-b[i] for i in (0,1)]
                turns.append(math.atan2(u[0]*v[1]-u[1]*v[0],sum(u[i]*v[i] for i in (0,1))))
            if not turns or max(map(abs,turns))>math.radians(40) or sum(map(abs,turns))<.1:continue
            out[key]={'points':points,'fingerprint':token([[r['points'],r.get('source_geometry')] for r in rows])}
    return out

def observation_token(f):return token({k:f.get(k) for k in ('id','kind','bbox','floor','polygon')})

def corresponds(plan,feature,curve):
    x,y,w,h=feature['bbox'];W,H=plan['width'],plan['height'];pad=max(W,H)*.01
    ps=curve['points'];inside=sum(x*W-pad<=p[0]<=(x+w)*W+pad and y*H-pad<=p[1]<=(y+h)*H+pad for p in ps)/len(ps)
    # Explicit identity binding supplies correspondence. This bounds check only
    # rejects grossly misplaced bindings; it never supplies identity by itself.
    return inside>=.95 and math.dist(ps[0],ps[-1])>max(w*W,h*H)*.25

def unresolved(plan,architecture,floor=None):
    available=curves(plan,architecture);missing=[]
    for f in plan.get('plan_reading',{}).get('features',[]):
        if f.get('kind')!='curved_wall' or f.get('review_status')=='rejected' or floor is not None and f.get('floor')!=floor:continue
        binding=plan.get('curve_bindings',{}).get(f['id'],{});curve=available.get(binding.get('source_id'))
        if f.get('review_status')!='confirmed' or not curve or binding.get('curve_fingerprint')!=curve['fingerprint'] or binding.get('observation_fingerprint')!=observation_token(f) or not corresponds(plan,f,curve):missing.append(f['id'])
    return missing

def bind(plan,architecture,feature_id,source_id):
    f=next((f for f in plan.get('plan_reading',{}).get('features',[]) if f['id']==feature_id and f.get('kind')=='curved_wall'),None)
    curve=curves(plan,architecture).get(source_id)
    if not f or not curve or not corresponds(plan,f,curve):raise ValueError('Choose a supported, reviewed curve at this observation. Straight runs and unrelated curves cannot be linked.')
    plan.setdefault('curve_bindings',{})[feature_id]={'source_id':source_id,'curve_fingerprint':curve['fingerprint'],'observation_fingerprint':observation_token(f)}


def save(st,pid,aid,data):
    import copy
    from drawing_editor import get_document
    from drawing_scene import resolve
    from raster_validation import signature
    from store import editing_busy
    plan=st.asset(aid);project=st.project(pid)
    if aid not in project['floor_plans']:raise ValueError('Choose this project’s plan.')
    if editing_busy(st,pid):raise ValueError('Finish generation before linking curve evidence.')
    if data.get('fingerprint')!=signature(plan,project):raise ValueError('Geometry changed. Refresh before linking a curve.')
    before=copy.deepcopy(plan)
    try:
        if data.get('action')=='undo':
            if not plan.get('curve_binding_undo'):raise ValueError('No curve link to undo.')
            plan['curve_bindings']=plan['curve_binding_undo'].pop()
        else:
            architecture,_=resolve(get_document(st,pid,aid))
            bind(plan,architecture,data.get('feature_id'),data.get('source_id'))
            plan.setdefault('curve_binding_undo',[]).append(before.get('curve_bindings',{}))
        plan.pop('raster_validation',None);st.save()
    except Exception:plan.clear();plan.update(before);raise
    return {'saved':True}
