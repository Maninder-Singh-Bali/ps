"""Local architectural evidence and reviewed semantics; never an automatic approval.

Raster inference is deliberately conservative: enclosed white regions and repeated
straight strokes are proposals, not named rooms or certified staircases. Corrections
are plan-owned, versioned, and survive a rescan. No villa-specific geometry lives here.
"""
import copy, hashlib, json, math, time
from pathlib import Path
from collections import deque
import numpy as np
from PIL import Image, ImageOps, ImageFilter
from store import editing_busy, uid, now
from plan_area import polygon, bounds, area
import project_storage

KINDS = {'space':'Room / open space', 'wall':'Wall', 'curved_wall':'Curved wall',
         'door':'Hinged door', 'sliding_door':'Sliding door', 'window':'Window',
         'stair':'Staircase', 'furniture':'Furniture', 'unknown':'Unclassified symbol'}
RULES = [
    {'kind':'stair','title':'Stairs','evidence':'Repeated treads within a flight, landings and an ascent arrow or UP/DN label. A hatch or row of cushions alone is insufficient.'},
    {'kind':'door','title':'Hinged doors','evidence':'A wall opening with a leaf and swing arc. The arc is clearance, not a curved wall.'},
    {'kind':'sliding_door','title':'Sliding doors','evidence':'Overlapping leaves or tracks across an opening; check the panel count and travel direction.'},
    {'kind':'window','title':'Windows','evidence':'Glazing lines within a wall opening; distinguish them from tread lines and furniture.'},
    {'kind':'wall','title':'Walls & curved walls','evidence':'Continuous paired lines or thick cut strokes defining enclosures. Preserve curves and openings.'},
    {'kind':'furniture','title':'Furniture','evidence':'Seats, cushions, beds, tables and sanitary fixtures are contents, not structural partitions.'},
    {'kind':'space','title':'Rooms & connections','evidence':'Use enclosure, openings and labels together. A legend names types; it does not count every room.'},
]
CHECKS = ('walls','openings','rooms','stairs')

def _runs(a):
    padded=np.r_[False,a,False].astype(np.int8);edges=np.flatnonzero(np.diff(padded))
    return list(zip(edges[::2],edges[1::2]))

def repeated_strokes(gray):
    """Find uniform bars in either axis. Always return ambiguous, reviewable symbols."""
    h,w=gray.shape;ink=gray<155;out=[]
    for turn,mask in enumerate((ink,ink.T)):
        lines=[];mh,mw=mask.shape
        for y,row in enumerate(mask):
            for x,xx in _runs(row):
                if max(6,mw*.012)<=xx-x<=mw*.24:
                    # A thick wall occupies adjacent scan rows; it is not a run
                    # of treads. Only count the first row of a distinct stroke.
                    if y and mask[y-1,x+1:xx-1].mean()>.55:continue
                    if not any(abs(y-yy)<=2 and abs(x-a)<=2 and abs(xx-b)<=2 for yy,a,b in lines[-80:]):lines.append((y,int(x),int(xx)))
        used=set()
        for i,(y,x,xx) in enumerate(lines):
            if i in used:continue
            group=[(i,y,x,xx)]
            for j,(yy,a,b) in enumerate(lines[i+1:],i+1):
                if yy-y>mh*.24:break
                if abs(a-x)<=max(2,(xx-x)*.1) and abs(b-xx)<=max(2,(xx-x)*.1):group.append((j,yy,a,b))
            if len(group)<5:continue
            # Split at large gaps; furniture rows usually lack regular, dense treads.
            chain=[group[0]]
            for row in group[1:]:
                # Tread spacing scales with flight width, not the page margins.
                # This also works when the same detail is scanned/cropped larger.
                if 2<=row[1]-chain[-1][1]<=max(4,min(mh*.08,(xx-x)*.38)):chain.append(row)
                elif len(chain)<5:chain=[row]
                else:break
            gaps=np.diff([v[1] for v in chain])
            if len(chain)<5 or gaps.std()/gaps.mean()>.26:continue
            a=min(v[2] for v in chain);b=max(v[3] for v in chain);c=chain[0][1];d=chain[-1][1]
            if d-c<max(8,mh*.018) or not .45<=(d-c)/(b-a)<=6:continue
            box=[a/w,c/h,(b-a)/w,(d-c+1)/h] if not turn else [c/w,a/h,(d-c+1)/w,(b-a)/h]
            out.append({'kind':'unknown','label':'Possible stair / repeated hatch','bbox':box,'confidence':'low',
                        'evidence':f'{len(chain)} evenly spaced parallel strokes. Confirm treads, landing and direction; wardrobes and hatching can look similar.'})
            used.update(v[0] for v in chain)
            if len(out)>=24:return out
    return out

def enclosures(gray):
    """Connected enclosed regions after a small gap closure, never exact wall polygons."""
    h,w=gray.shape;mask=Image.fromarray(np.where(gray<175,255,0).astype('uint8'))
    k=max(3,int(min(h,w)*.008)//2*2+1)
    mask=np.array(mask.filter(ImageFilter.MaxFilter(k)))>0
    seen=mask.copy();out=[]
    for y in range(h):
        for x in range(w):
            if seen[y,x]:continue
            seen[y,x]=True;q=deque([(x,y)]);n=0;left=right=x;top=bottom=y;border=False
            while q:
                xx,yy=q.popleft();n+=1;left=min(left,xx);right=max(right,xx);top=min(top,yy);bottom=max(bottom,yy)
                if xx in (0,w-1) or yy in (0,h-1):border=True
                for a,b in ((xx-1,yy),(xx+1,yy),(xx,yy-1),(xx,yy+1)):
                    if 0<=a<w and 0<=b<h and not seen[b,a]:seen[b,a]=True;q.append((a,b))
            if border or n<w*h*.006 or n>w*h*.75 or min(right-left,bottom-top)<min(w,h)*.055:continue
            out.append({'kind':'space','label':'Possible enclosed space','bbox':[left/w,top/h,(right-left+1)/w,(bottom-top+1)/h],
                        'confidence':'low','evidence':'Enclosed region in the scan after bridging small gaps. Its rectangle is a search area, not a measured room boundary.'})
    return sorted(out,key=lambda v:-v['bbox'][2]*v['bbox'][3])[:30]

def detect(path):
    with Image.open(path) as image:
        im=ImageOps.exif_transpose(image).convert('L');im.thumbnail((1000,1000));gray=np.asarray(im)
    return enclosures(gray)+repeated_strokes(gray)

def get_reading(st,pid,aid):
    p=st.project(pid)
    if aid not in p['floor_plans']:raise ValueError('Choose a floor plan from this project.')
    a=st.asset(aid);saved=copy.deepcopy(a.get('plan_reading',{}))
    return {'revision':0,'features':[],'reviewed':False,'checks':{},'warnings':[],**saved,
            'map_revision':p['map_revision'],'rules':RULES,'kinds':KINDS,'source':a.get('plan_source',{}),
            'width':a['width'],'height':a['height']}

def overlap(a,b):
    x,y,w,h=a;xx,yy,ww,hh=b
    inter=max(0,min(x+w,xx+ww)-max(x,xx))*max(0,min(y+h,yy+hh)-max(y,yy))
    return inter/max(1e-9,min(w*h,ww*hh))

def _idle(st,pid):
    if editing_busy(st,pid):
        raise ValueError('Finish this project’s active activity before changing its plan study.')

def _save(st,pid,aid,record):
    a=st.asset(aid);p=st.project(pid);a['plan_reading']=record
    folder=project_storage.project_root(st,pid)/'Supporting_Files'/'Plan_Studies';folder.mkdir(parents=True,exist_ok=True)
    path=folder/f'{aid}_v{record["revision"]}_{uid()}.json';path.write_text(json.dumps(record,indent=2),encoding='utf8')
    a['plan_study_file']=str(path);p['map_confirmed']=False;p['map_revision']+=1
    for r in p['rooms']:
        if r.get('plan_id')==aid:st.invalidate(pid,r)
    st.save();return get_reading(st,pid,aid)

def study(st,pid,aid,data):
    doc=get_reading(st,pid,aid);_idle(st,pid)
    if data.get('revision')!=doc['revision']:raise ValueError('This plan study changed. Reopen it before scanning.')
    from source_panels import ensure
    if not ensure(st,pid,aid):raise ValueError('Approve source panels before scanning.')
    return _save(st,pid,aid,propose_reading(st.asset(aid),doc))


def propose_reading(a,doc):
    """Build review evidence without writes, locks or automatic confirmation."""
    start=time.monotonic()
    import source_scope
    scope=source_scope.capture(a)
    panels,_=source_scope.materialize(a,scope,Path(a['path']).parent/'Scoped_Readers')
    found=[]
    for panel in panels:
        found.extend(source_scope.map_row(f,panel,scope) for f in detect(panel['path']))
    # Native vector layer names provide evidence, not semantic truth.
    for feature in a.get('plan_source',{}).get('symbol_candidates',[]):
        x,y,w,h=feature['bbox']
        for panel in scope['panels']:
            px,py,pw,ph=panel['bbox']
            if px<=x and py<=y and x+w<=px+pw and y+h<=py+ph:
                value=copy.deepcopy(feature);value.update(panel_id=panel['id'],source_scope_key=scope['key'])
                if panel.get('floor'):value['floor']=panel['floor']
                found.append(value);break
    preserved=copy.deepcopy([f for f in doc.get('features',[]) if f.get('review_status')!='pending' or f.get('source')=='manual'])
    for f in found:
        if any((f['kind']==v['kind'] or f['kind']=='unknown' and v['kind'] in ('unknown','stair','furniture'))
               and overlap(f['bbox'],v['bbox'])>.65 for v in preserved):continue
        f.update(id=uid(),floor=f.get('floor',''),room_id=None,connection_room_id=None,review_status='pending',source='local_inference',notes='',shape='unspecified')
        preserved.append(f)
    warnings=['Proposals require review: a scan cannot establish wall heights, structural loads or hidden connections.',
              'Curved furniture, wardrobes and hatching can resemble stairs. Confirm symbols against their surroundings.']
    if min(a['width'],a['height'])<700:warnings.insert(0,'Small original drawing: missing line detail cannot be recovered by enlargement. Prefer a vector PDF or DXF if available.')
    return {'version':1,'revision':doc.get('revision',0)+1,'features':preserved[:300],'checks':{},'reviewed':False,
                            'warnings':warnings,'source_scope':scope,'engine':'Local enclosure + repeated-stroke evidence + CAD layer hints',
                            'elapsed_seconds':round(time.monotonic()-start,2),'updated':now()}

def clean_features(data,project,aid):
    rows=data.get('features');out=[];seen=set();rooms={r['id']:r for r in project['rooms']}
    if not isinstance(rows,list) or len(rows)>300:raise ValueError('Use up to 300 architectural features.')
    for row in rows:
        key=row.get('id');kind=row.get('kind');status=row.get('review_status')
        if not isinstance(key,str) or not key.isalnum() or len(key)>50 or key in seen:raise ValueError('Invalid or duplicate feature.')
        if kind not in KINDS or status not in ('pending','confirmed','rejected'):raise ValueError('Choose a feature type and review status.')
        seen.add(key);box=row.get('bbox')
        if not isinstance(box,list) or len(box)!=4 or any(type(v) not in (int,float) or not math.isfinite(v) for v in box):raise ValueError('Mark this feature on the plan.')
        x,y,w,h=box
        if min(x,y)<0 or min(w,h)<.001 or x+w>1.00001 or y+h>1.00001:raise ValueError('Keep the feature inside the drawing.')
        rid=row.get('room_id') or None;arrival=row.get('connection_room_id') or None
        if rid and (rid not in rooms or rooms[rid]['plan_id']!=aid):raise ValueError('Choose a section on this plan.')
        if arrival and arrival not in rooms:raise ValueError('Choose a connected section from this project.')
        if arrival:
            if not rid or arrival==rid:raise ValueError('Choose two different sections for a shared feature.')
            if kind!='stair' and (rooms[arrival]['plan_id']!=aid or rooms[arrival]['floor']!=rooms[rid]['floor']):raise ValueError('Shared walls and openings must use sections on the same floor and full plan.')
        floor=str(row.get('floor') or '').strip()[:80]
        if status=='confirmed' and (kind=='unknown' or not floor):raise ValueError('Classify confirmed symbols and assign their floor.')
        pts=polygon(row['polygon']) if row.get('polygon') else None
        if pts:box=bounds(pts)
        seats=row.get('seat_count')
        if seats in ('',None):seats=None
        else:
            if type(seats) is bool or type(seats) is float and not seats.is_integer():raise ValueError('Use a whole number for seat count.')
            try:seats=int(seats)
            except (ValueError,TypeError):raise ValueError('Use a whole number for seat count.')
            if not 1<=seats<=12:raise ValueError('Use 1 to 12 seats, or leave the count unknown.')
        out.append({'id':key,'kind':kind,'review_status':status,'bbox':box,'polygon':pts,'floor':floor,'room_id':rid,
                    'seat_count':seats if kind=='furniture' else None,'object_type':str(row.get('object_type',''))[:70] if kind=='furniture' else '',
                    'connection_room_id':arrival,'label':str(row.get('label',KINDS[kind]))[:120],
                    'shape':str(row.get('shape') or 'unspecified')[:60],'notes':str(row.get('notes') or '')[:1200],
                    'source':str(row.get('source','manual'))[:80],'confidence':str(row.get('confidence','user'))[:30],
                    'evidence':str(row.get('evidence','Marked by user'))[:1000],
                    'panel_id':str(row.get('panel_id',''))[:60], 'source_scope_key':str(row.get('source_scope_key',''))[:64]})
    return out

def save_reading(st,pid,aid,data):
    doc=get_reading(st,pid,aid);_idle(st,pid);p=st.project(pid)
    if data.get('revision')!=doc['revision'] or data.get('map_revision')!=p['map_revision']:raise ValueError('The drawing changed. Reopen the study before saving.')
    features=clean_features(data,p,aid);checks={k:data.get('checks',{}).get(k) is True for k in CHECKS}
    previous={f['id']:f for f in clean_features(doc,p,aid)}
    editable=('kind','label','bbox','polygon','floor','room_id','connection_room_id','shape','notes','review_status','seat_count','object_type')
    for f in features:
        old=previous.get(f['id'])
        if not old or any(f.get(k)!=old.get(k) for k in editable):
            f['source']='manual'
    reviewed=data.get('reviewed') is True
    if reviewed and (not all(checks.values()) or any(f['review_status']=='pending' for f in features)):
        raise ValueError('Resolve every proposal and review walls, openings, room divisions and stairs before marking the study reviewed.')
    return _save(st,pid,aid,{'version':1,'revision':doc['revision']+1,'features':features,'checks':checks,'reviewed':reviewed,
                            'warnings':doc['warnings'],'elapsed_seconds':doc.get('elapsed_seconds'), 'updated':now()})

def assert_reviewed(st,project):
    for aid in project['floor_plans']:
        doc=st.asset(aid).get('plan_reading')
        if doc and not doc.get('reviewed'):raise ValueError('Review the architectural plan study before confirming the room map.')

def make_section(st,pid,aid,data):
    doc=get_reading(st,pid,aid);_idle(st,pid)
    if data.get('revision')!=doc['revision'] or data.get('map_revision')!=doc['map_revision']:raise ValueError('The study changed. Reopen it first.')
    f=next((f for f in doc['features'] if f['id']==data.get('feature_id')),None)
    if not f or f['kind']!='space' or f['review_status']!='confirmed':raise ValueError('Confirm a named room or open space before adding it as a section.')
    if f.get('room_id'):return {'room_id':f['room_id'],'reading':doc}
    r=st.add_room(pid,f['label'],f['floor'],aid,f['bbox'],confidence='user reviewed',detection_note='Created from a reviewed architectural feature; refine the boundary before measuring area.')
    if f.get('polygon'):r.update(area_polygon=f['polygon'],area_bbox=f['bbox'])
    f['room_id']=r['id'];doc['reviewed']=False;doc['checks']['rooms']=False
    saved=save_reading(st,pid,aid,{**doc,'map_revision':st.project(pid)['map_revision']})
    return {'room_id':r['id'],'reading':saved}

def instruction(plan,room):
    doc=plan.get('plan_reading',{});rows=[]
    for f in doc.get('features',[]):
        if f['review_status']!='confirmed' or f['floor']!=room['floor']:continue
        if f.get('room_id') and room['id'] not in (f['room_id'],f.get('connection_room_id')):continue
        if not f.get('room_id') and room.get('bbox') and overlap(f['bbox'],room['bbox'])<.05:continue
        text=f'{KINDS[f["kind"]]}: {f["label"]}; plan bounds {f["bbox"]}; form {f["shape"]}. {f["notes"]}'
        if f['kind']=='furniture':text+=f" Object type: {f.get('object_type') or 'unspecified'}; seats: {f.get('seat_count') or 'unknown'}. This is one distinct object, not a group to merge."
        if f['kind']=='space' and f.get('connection_room_id'):text+=' OPEN CONNECTION: no dividing wall, door or partition at this section boundary. The bounds are a relationship marker, not construction geometry.'
        if f.get('connection_room_id'):text+=f" Shared feature {f['id']} connects sections {f.get('room_id')} and {f['connection_room_id']}; use this same plan position and opening type from both sides. Preserve its meaning in both section views."
        if f['kind']=='stair' and not f.get('connection_room_id'):text+=' Upper/lower arrival is unresolved; do not invent a landing or connecting room.'
        rows.append(text)
    return ('REVIEWED ARCHITECTURAL FEATURES (plan coordinates, not camera coordinates):\n'+'\n'.join(rows)+
            '\nPreserve these features. Furniture symbols are not walls. Openings are not solid partitions.') if rows else ''
