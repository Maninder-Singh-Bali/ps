"""Non-destructive construction scope in original-sheet coordinates.

Selections filter supported geometry. They never generate boundary walls.
"""
import copy
import hashlib
import json
import math
from plan_area import polygon, edges, crossing, on_segment, intervals, merge, clip, subtract, area, bounds, box_polygon, EPS


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def current(plan):
    s = plan.get('construction_selection')
    return s if s and s.get('confirmed') and s.get('source_sha256') == plan.get('sha256') else None


def required(plan):
    return bool(plan.get('construction_selection_required') or plan.get('construction_selection'))


def inside(p, poly):
    if any(on_segment(a, b, p) for a, b in edges(poly)):
        return True
    x, y = p
    return sum((a[1] > y) != (b[1] > y) and x < (b[0]-a[0])*(y-a[1])/(b[1]-a[1])+a[0] for a, b in edges(poly)) % 2 == 1


def contains(p, s):
    return any(inside(p, r) for r in s['regions']) and not any(inside(p, h) for h in s.get('exclusions', []))


def line_parts(a, b, s, thickness=0, size=(1, 1)):
    """Clip length only; parallel host-wall faces retain their complete thickness."""
    dx, dy = b[0]-a[0], b[1]-a[1]
    norm = dx*dx+dy*dy
    if norm < 1e-16:
        return []
    def t(p): return ((p[0]-a[0])*dx+(p[1]-a[1])*dy)/norm
    cuts = {0., 1.}
    for poly in s['regions']+s.get('exclusions', []):
        for c, d in edges(poly):
            p = crossing(a, b, c, d)
            if p is not None: cuts.add(max(0., min(1., t(p))))
    ordered = sorted(cuts)
    spans = [[l, r] for l, r in zip(ordered, ordered[1:]) if contains([a[0]+dx*(l+r)/2, a[1]+dy*(l+r)/2], s)]
    # Interior-face selection may put the wall centre outside the region. Only
    # parallel, overlapping source segments qualify, never a nearby room box.
    px, py = dx*size[0], dy*size[1]
    length = math.hypot(px, py)
    if thickness > 0:
        for poly in s['regions']:
            for c, d in edges(poly):
                ex, ey = (d[0]-c[0])*size[0], (d[1]-c[1])*size[1]
                if abs(px*ey-py*ex) > 1e-6*length*max(1, math.hypot(ex, ey)): continue
                dist = abs(px*(c[1]-a[1])*size[1]-py*(c[0]-a[0])*size[0])/length
                if dist > thickness/2+.05: continue
                l, r = max(0., min(t(c), t(d))), min(1., max(t(c), t(d)))
                if r > l: spans.append([l, r])
    # Void edges do not permit construction inside a hole.
    spans = merge(spans)
    for h in s.get('exclusions', []):
        hs = {'regions': [h], 'exclusions': []}
        spans = subtract(spans, line_parts(a, b, hs))
    return spans


def architecture(rows, plan, s):
    out = []
    for f in rows:
        if f.get('floor') and f['floor'] != s['floor']: continue
        if f['kind'] not in ('wall', 'door', 'window', 'sliding_door'): continue
        a, b = [[p[0]/plan['width'], p[1]/plan['height']] for p in f['points']]
        parts = line_parts(a, b, s, f.get('thickness', 0), (plan['width'], plan['height']))
        # Openings are atomic; a cut opening stays excluded pending adjustment.
        if f['kind'] != 'wall' and (len(parts) != 1 or parts[0][0] > 1e-7 or parts[0][1] < 1-1e-7): continue
        for i, (l, r) in enumerate(parts):
            if r-l < 1e-8: continue
            v = copy.deepcopy(f)
            v['points'] = [[(a[0]+(b[0]-a[0])*t)*plan['width'], (a[1]+(b[1]-a[1])*t)*plan['height']] for t in (l, r)]
            v['selection_part'] = i
            out.append(v)
    return out


def faces(s, masks=(), holes=()):
    """Polygon union intersected with optional floor envelope, subtracting voids."""
    regions = s['regions']; holes = s.get('exclusions', [])+list(holes)
    polygons = regions+list(masks)+holes
    es = [e for p in polygons for e in edges(p)]
    cuts = {p[0] for poly in polygons for p in poly}
    for i, (a, b) in enumerate(es):
        for c, d in es[i+1:]:
            q = crossing(a, b, c, d)
            if q is not None: cuts.add(q[0])
    out = []; cuts = sorted(cuts)
    for l, r in zip(cuts, cuts[1:]):
        if r-l < EPS: continue
        mid = (l+r)/2
        iv = merge([v for p in regions for v in intervals(p, mid)])
        if masks: iv = clip(iv, merge([v for p in masks for v in intervals(p, mid)]))
        iv = subtract(iv, [v for p in holes for v in intervals(p, mid)])
        active = [(a, b) for a, b in es if min(a[0], b[0]) < mid < max(a[0], b[0])]
        def y(e, x):
            a, b = e; return a[1]+(x-a[0])*(b[1]-a[1])/(b[0]-a[0])
        for lo, hi in iv:
            low = min(active, key=lambda e: abs(y(e, mid)-lo)); high = min(active, key=lambda e: abs(y(e, mid)-hi))
            out.append([[l,y(low,l)],[r,y(low,r)],[r,y(high,r)],[l,y(high,l)]])
    return out


def coverage(poly, s):
    selected = sum(area(p) for p in faces(s, [poly]))
    return min(1., selected/max(area(poly), EPS))


def footprint(item, plan):
    # Library widths/depths use normalized sheet axes; rotation is in pixel space.
    x, y = item['x'], item['y']; w = item['width']; d = item['depth']
    t = math.radians(item.get('angle', 0)); c, sn = math.cos(t), math.sin(t)
    return [[x+(u*c-v*sn)/plan['width'], y+(u*sn+v*c)/plan['height']] for u,v in [(-w*plan['width']/2,-d*plan['height']/2),(w*plan['width']/2,-d*plan['height']/2),(w*plan['width']/2,d*plan['height']/2),(-w*plan['width']/2,d*plan['height']/2)]]


def room_polygon(room):
    return room.get('area_polygon') if room.get('area_bbox') == room.get('bbox') else None


def evidence(st, pid, aid):
    p = st.project(pid); a = st.asset(aid)
    return digest([a.get('sha256'), a.get('drawing'), a.get('raster_revision'), a.get('source_review'), a.get('plan_reading'), p.get('area_revision'), [(r['id'],r.get('bbox'),r.get('area_polygon'),r.get('block_layout'),r.get('furniture_layout')) for r in p['rooms'] if r.get('plan_id') == aid]])


def clean(data, plan):
    regions = data.get('regions', [])
    if not isinstance(regions,list) or not 1 <= len(regions) <= 20: raise ValueError('Draw or choose at least one area (up to 20).')
    holes = data.get('exclusions', [])
    if not isinstance(holes,list) or len(holes) > 20: raise ValueError('Use up to 20 open-to-sky voids.')
    floor = str(data.get('floor','')).strip()[:50]
    if not floor: raise ValueError('Name the selected floor.')
    s = {'regions':[polygon(p) for p in regions], 'exclusions':[polygon(p) for p in holes], 'floor':floor, 'name':str(data.get('name','Selected area')).strip()[:100] or 'Selected area', 'kind':data.get('kind') if data.get('kind') in ('manual','rooms','apartment') else 'manual', 'source_sha256':plan.get('sha256')}
    if sum(area(p) for p in faces(s)) < 1e-7: raise ValueError('The selection has no constructible area.')
    return s


def inspect(st, pid, aid, data=None):
    p = st.project(pid)
    if aid not in p['floor_plans']: raise ValueError('Choose a plan from this project.')
    a = st.asset(aid); saved = current(a); candidates = []
    for r in p['rooms']:
        poly = room_polygon(r)
        if r.get('plan_id') == aid and poly:
            candidates.append({'id':r['id'], 'name':r['name'], 'floor':r['floor'], 'kind':'rooms', 'regions':[poly]})
    # Only explicitly saved/reviewed apartment selections, not inferred groups.
    seen = set()
    for old in [saved]+list(reversed(a.get('construction_selection_history', []))):
        if old and old.get('confirmed') and old.get('kind') == 'apartment' and old.get('source_sha256') == a.get('sha256') and old['name'] not in seen:
            seen.add(old['name']); candidates.append({**copy.deepcopy(old),'id':'apartment:'+old['name']})
    response = {'saved':saved, 'revision':a.get('construction_selection_revision',0), 'candidates':candidates, 'evidence':evidence(st,pid,aid), 'history_count':len(a.get('construction_selection_history',[]))}
    if data is None: return response
    s = clean(data,a); issues = []; from drawing_scene import load
    rows, unresolved = load(st,a)
    for r in p['rooms']:
        poly = room_polygon(r)
        if r.get('plan_id') != aid or r.get('floor') != s['floor'] or not poly: continue
        ratio = coverage(poly,s)
        if 1e-6 < ratio < 1-1e-6: issues.append({'kind':'room','id':r['id'],'label':r['name'],'polygon':poly,'message':'Selection cuts through this room; adjust the outline.'})
        if ratio > 1e-6 and r.get('kind') == 'outdoor': issues.append({'kind':'balcony','id':r['id'],'label':r['name'],'polygon':poly,'message':'Confirm this outdoor area belongs to the selected apartment.'})
    for f in rows:
        if f['kind'] not in ('wall','door','window','sliding_door'): continue
        pts = [[x/a['width'],y/a['height']] for x,y in f['points']]
        parts = line_parts(*pts,s,f.get('thickness',0),(a['width'],a['height']))
        total = sum(r-l for l,r in parts)
        if 1e-7 < total < 1-1e-7: issues.append({'kind':f['kind'],'id':f.get('source_id',f.get('id')),'points':pts,'message':'Selection cuts this '+f['kind']+'. '+('Full wall thickness is retained.' if f['kind']=='wall' else 'It will be excluded until fully included.')})
    for r in p['rooms']:
        if r.get('plan_id') != aid or r.get('floor') != s['floor']: continue
        for item in r.get('block_layout',{}).get('items',[]):
            poly = footprint(item,a); ratio = coverage(poly,s)
            if 1e-6 < ratio < 1-1e-6: issues.append({'kind':'furniture','id':item['id'],'label':item['label'],'polygon':poly,'message':'Selection cuts this furniture; it will be excluded.'})
    response.update(selection=s, issues=issues, preview_key=digest([s,response['evidence'],response['revision']]), unknown_geometry=bool(unresolved or not rows), note='Cuts are checked against known geometry only. Check the original for unclassified rooms, fixtures, balconies and voids.')
    return response


def save(st,pid,aid,data):
    from store import editing_busy, now
    if editing_busy(st,pid): raise ValueError('Finish generation before changing the construction selection.')
    a=st.asset(aid); revision=a.get('construction_selection_revision',0)
    if data.get('revision') != revision: raise ValueError('Selection changed. Reload its preview before confirming.')
    if data.get('action') == 'undo':
        history=a.get('construction_selection_history',[])
        if not history: raise ValueError('No previous selection to restore.')
        chosen=copy.deepcopy(history[-1]); remaining=history[:-1]
    else:
        result=inspect(st,pid,aid,data)
        if data.get('preview_key') != result['preview_key']: raise ValueError('Drawing or selection changed. Preview again before confirming.')
        if not data.get('checked'): raise ValueError('Confirm the source outline, ownership, voids and highlighted cuts first.')
        chosen={**result['selection'],'confirmed':True,'review_evidence':result['evidence'],'reviewed_issues':result['issues']}
        remaining=a.get('construction_selection_history',[])+[copy.deepcopy(a.get('construction_selection'))]
    before=copy.deepcopy(st.db)
    try:
        a['construction_selection_revision']=revision+1
        a['construction_selection']=({**chosen,'revision':revision+1,'updated':now()} if chosen else None)
        a['construction_selection_history']=remaining[-30:]
        a['construction_selection_required']=True
        p=st.project(pid); p['updated']=now();p['map_confirmed']=False
        for r in p['rooms']:
            if r.get('plan_id')==aid:st.invalidate(pid,r)
        st.save()
    except Exception:
        st.db=before;raise
    return inspect(st,pid,aid)


def empty_scene(plan, floor=''):
    return {'plan_id':plan['id'],'floor':floor,'bounds':[0,0,1,1],'width':1,'depth':1,'height':0,'surfaces':[],'lines':[],'products':[],'calibrated':False,'camera':None,'saved_camera':None,'issues':['Select area to construct and confirm the original outline first.'],'limits':[],'partial':True,'geometry_validated':False,'architecture_counts':{},'geometry_hash':digest([plan.get('construction_selection_revision',0),'unconfirmed']),'selection_required':True}
