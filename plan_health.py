"""Deterministic full-plan diagnostics and bounded repair, with an audit trail.
No image recognition guesses or source-pixel edits are performed here.
"""
import copy, hashlib, json, math
from pathlib import Path
from store import editing_busy, now, uid
import project_storage
from object_knowledge import review_report


def fingerprint(plan, project):
    data={'drawing':plan.get('drawing',{}),'reading':plan.get('plan_reading',{}),
          'rooms':[{k:r.get(k) for k in ('id','floor','plan_id','bbox','area_polygon')} for r in project['rooms']],
          'map_revision':project['map_revision']}
    return hashlib.sha256(json.dumps(data,sort_keys=True).encode()).hexdigest()


def cut_interval(points, box):
    """Open rectangle intersection; endpoints on its border remain intact."""
    (x,y),(xx,yy)=points;dx,dy=xx-x,yy-y;lo,hi=0.,1.
    for p,q in ((-dx,x-box[0]),(dx,box[2]-x),(-dy,y-box[1]),(dy,box[3]-y)):
        if abs(p)<1e-12:
            if q<=1e-7:return None
        elif p<0:lo=max(lo,q/p)
        else:hi=min(hi,q/p)
    return (lo,hi) if (hi-lo)*math.hypot(dx,dy)>.5 else None


def repair_plan(plan):
    """Propose wall cuts only inside fully confirmed, narrow opening/passage bounds."""
    features=copy.deepcopy(plan.get('drawing',{}).get('features',[]));repairs=[];uncertain=[]
    verified=[]
    for f in plan.get('plan_reading',{}).get('features',[]):
        if f.get('review_status')!='confirmed' or f.get('kind') not in ('door','window','sliding_door','space'):continue
        if f['kind']=='space' and not f.get('connection_room_id'):continue
        b=f['bbox'];box=[b[0]*plan['width'],b[1]*plan['height'],(b[0]+b[2])*plan['width'],(b[1]+b[3])*plan['height']]
        # Broad room rectangles are never authority to erase architecture.
        if min(box[2]-box[0],box[3]-box[1])>max(box[2]-box[0],box[3]-box[1])*.25:
            uncertain.append({'feature_id':f['id'],'message':'Mark the narrow opening or open transition precisely before automatic repair.'});continue
        verified.append((f,box))
    out=[]
    for wall in features:
        if wall['kind']!='wall':out.append(wall);continue
        intervals=[];evidence=[]
        for f,box in verified:
            cut=cut_interval(wall['points'],box)
            if cut:intervals.append(cut);evidence.append({'id':f['id'],'label':f['label'],'kind':f['kind']})
        if not intervals:out.append(wall);continue
        merged=[]
        for lo,hi in sorted(intervals):
            if merged and lo<=merged[-1][1]:merged[-1][1]=max(hi,merged[-1][1])
            else:merged.append([lo,hi])
        keep=[];last=0
        for lo,hi in merged:
            if lo>last:keep.append([last,lo])
            last=hi
        if last<1:keep.append([last,1])
        a,b=wall['points'];length=math.dist(a,b);pieces=[]
        for i,(lo,hi) in enumerate(keep):
            if (hi-lo)*length<.2:continue
            part={**wall,'id':'newrepair'+hashlib.sha256((wall['id']+str(lo)+str(hi)).encode()).hexdigest()[:20],
                  'points':[[a[k]+(b[k]-a[k])*t for k in (0,1)] for t in (lo,hi)]}
            pieces.append(part);out.append(part)
        repairs.append({'rule':'verified_opening_remains_open','wall_id':wall['id'],'before':wall,'after':pieces,'evidence':evidence,
                        'message':'Remove only the wall portion inside the verified opening / open passage.'})
    return out,repairs,uncertain


def inspect(store,pid,aid):
    p=store.project(pid)
    if aid not in p['floor_plans']:raise ValueError('Choose a full plan from this project.')
    plan=store.asset(aid);_,repairs,uncertain=repair_plan(plan)
    from plan_preflight import report
    rooms=[r for r in p['rooms'] if r.get('plan_id')==aid]
    checks=[report(store,p,r) for r in rooms]
    links=[]
    names={r['id']:r['name'] for r in p['rooms']}
    for f in plan.get('plan_reading',{}).get('features',[]):
        if f.get('connection_room_id') and f.get('review_status')!='rejected':
            links.append({'id':f['id'],'from':names.get(f.get('room_id'),'Unassigned'),'to':names.get(f['connection_room_id'],'Missing section'),
                          'kind':f['kind'],'label':f['label'],'status':f['review_status'],'floor':f['floor'],
                          'constraint':'Continuous space — no partition' if f['kind']=='space' else 'One shared feature for both sections'})
    from raster_validation import status
    from raster_identity import correction_for
    return {'plan_id':aid,'fingerprint':fingerprint(plan,p),'can_generate':bool(checks) and all(c['can_generate'] for c in checks),
            'raster_validation':status(store,pid,aid) if plan.get('raster_geometry') else None,
            'raster_orphaned_corrections':copy.deepcopy(plan.get('raster_orphaned_corrections',[])),
            'review_revision':plan.get('review_revision',0),'analysis_status':'Room analysis incomplete' if not checks else 'Review unresolved items',
            'raster_geometry':copy.deepcopy(plan.get('raster_geometry')),'raster_revision':plan.get('raster_revision',0),
            'raster_corrections':{key:copy.deepcopy(correction_for(plan,key)) for key in plan.get('raster_corrections',{})},
            'sections':checks,'connections':links,'repairs':repairs,'uncertain':uncertain,
            'drawing_revision':plan.get('drawing',{}).get('revision',0),'study_revision':plan.get('plan_reading',{}).get('revision',0),
            'history':copy.deepcopy(plan.get('repair_history',[])[-10:]),'vision_report':review_report(plan.get('vision_report')),
            'scope':'Checks saved full-plan facts. Only fully confirmed, precisely marked openings can trigger repair. Ambiguous plan interpretation requires your review here; source image remains unchanged.'}


def apply(store,pid,aid,expected):
    p=store.project(pid);plan=store.asset(aid)
    if aid not in p['floor_plans']:raise ValueError('Choose a plan from this project.')
    if editing_busy(store,pid):raise ValueError('Finish the current activity before repairing the shared plan.')
    if expected!=fingerprint(plan,p):raise ValueError('The shared plan changed. Run checks again before applying corrections.')
    features,repairs,_=repair_plan(plan)
    if not repairs:return {'changed':False,'report':inspect(store,pid,aid)}
    from drawing_editor import get_document,save_document
    doc=get_document(store,pid,aid);before=copy.deepcopy(doc)
    # Existing versioned drawing exporter preserves the original image and invalidates all sections.
    result=save_document(store,pid,aid,{**doc,'features':features})
    entry={'id':uid(),'created':now(),'rule':'verified_opening_remains_open','before_revision':before['revision'],
           'after_revision':result['revision'],'repairs':repairs,'before':before,'source_sha256':plan.get('sha256')}
    folder=project_storage.project_root(store,pid)/'Supporting_Files'/'Plan_Repairs';folder.mkdir(parents=True,exist_ok=True)
    (folder/(entry['id']+'.json')).write_text(json.dumps(entry,indent=2),encoding='utf-8')
    plan.setdefault('repair_history',[]).append({k:v for k,v in entry.items() if k!='before'});store.save()
    return {'changed':True,'count':len(repairs),'report':inspect(store,pid,aid),
            'message':'Safe corrections saved. Review the updated full plan and confirm the map before rendering.'}

def undo(store,pid,aid,expected):
    p=store.project(pid);plan=store.asset(aid)
    if aid not in p['floor_plans'] or expected!=fingerprint(plan,p):raise ValueError('The plan changed. Refresh Structure check before undoing.')
    entry=next((x for x in reversed(plan.get('repair_history',[])) if not x.get('undone')),None)
    if not entry:raise ValueError('No automatic correction is available to undo.')
    if plan.get('drawing',{}).get('revision')!=entry['after_revision']:raise ValueError('The drawing has newer edits. Restore the needed lines in Refine drawing; undo would overwrite those edits.')
    from drawing_editor import get_document,save_document
    file=project_storage.project_root(store,pid)/'Supporting_Files'/'Plan_Repairs'/(entry['id']+'.json')
    before=json.loads(file.read_text(encoding='utf-8'))['before'];current=get_document(store,pid,aid)
    save_document(store,pid,aid,{**current,'features':before['features'],'edits':before['edits'],'site':before['site']})
    entry['undone']=now();store.save()
    return {'changed':True,'report':inspect(store,pid,aid),'message':'Automatic correction undone; review the restored drawing before rendering.'}
