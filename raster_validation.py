"""Explicit, revision-bound geometry review; never an automatic accuracy claim."""
import copy
import hashlib
import json
import math
from store import now, editing_busy
from raster_identity import correction_for


def signature(plan, project):
    keys=('sha256','width','height','raster_revision','raster_corrections','drawing',
          'plan_reading','review_revision','scale','scene_settings','floor_settings')
    data={k:plan.get(k) for k in keys}
    report=plan.get('raster_geometry') or {}
    data['evidence']={k:report.get(k) for k in ('source_sha256','analysis_size','walls','uncertain_spans','openings','regions')}
    data['orphans']=plan.get('raster_orphaned_corrections',[])
    data['vision']=plan.get('vision_report')
    data['rooms']=[{k:r.get(k) for k in ('id','name','plan_id','floor','bbox','area_polygon')} for r in project['rooms'] if r.get('plan_id')==plan['id']]
    data['measurements']=[m for m in project.get('measurements',[]) if m.get('plan_id')==plan['id']]
    return hashlib.sha256(json.dumps(data,sort_keys=True).encode()).hexdigest()


def _on_span(p,a,b,tolerance):
    d=[b[i]-a[i] for i in (0,1)];length=math.hypot(*d)
    if not length:return math.dist(p,a)<=tolerance
    t=sum((p[i]-a[i])*d[i] for i in (0,1))/(length*length)
    q=[a[i]+max(0,min(1,t))*d[i] for i in (0,1)]
    return math.dist(p,q)<=tolerance


def status(st,pid,aid):
    from drawing_editor import get_document
    from drawing_scene import resolve
    from raster_reconstruction import candidates
    from plan_area import polygon,proportions
    from detection_review import reconcile
    from shared_floor import unresolved_curves
    project=st.project(pid);plan=st.asset(aid)
    if aid not in project['floor_plans']:raise ValueError('Choose this project’s plan.')
    report=plan.get('raster_geometry') or {};issues=[]
    def issue(code,message,ids=()):issues.append({'code':code,'message':message,'ids':list(ids)})
    if not report:issue('missing','Trace the original pixels before completing boundary review.')
    if report.get('source_sha256')!=plan.get('sha256'):issue('source','Source evidence changed. Recheck the original pixels.')
    pending=[]
    for item in candidates(plan):
        edit=correction_for(plan,item['id'])
        if edit.get('action') not in ('accept','reject'):pending.append(item['id'])
        elif edit['action']=='accept':
            if item.get('candidate_opening') and edit.get('kind') not in ('door','window','sliding_door','open_transition'):pending.append(item['id'])
            elif not item.get('width_px') and edit.get('kind') not in ('wall','window'):pending.append(item['id'])
    if pending:issue('pending',f'Review {len(pending)} pending, deferred or edited paths; keep or exclude each.',pending)
    if plan.get('raster_orphaned_corrections'):issue('orphaned','A rescan changed previously corrected evidence. Review the archived corrections, then acknowledge them.')
    doc=get_document(st,pid,aid);architecture,unresolved=resolve(doc)
    if unresolved:issue('unresolved','Resolve architectural paths that cannot be built.',unresolved)
    if not any(v['kind']=='wall' for v in architecture):issue('walls','No supported wall geometry remains. Add or review the actual walls.')
    walls=[v for v in architecture if v['kind']=='wall']
    for row in architecture:
        ps=row.get('points',[])
        if len(ps)!=2 or any(not math.isfinite(v) for p in ps for v in p) or math.dist(*ps)<.01:
            issue('degenerate','Correct a zero-length or invalid architectural path.',[row['source_id']]);continue
        if row['kind'] in ('door','window','sliding_door'):
            # Either a span lies in a wall or its jambs meet adjacent wall ends.
            # Do not bridge a genuine open transition to manufacture an enclosure.
            tolerance=max(2,row.get('thickness',1.5))
            if not all(any(_on_span(p,*w['points'],max(tolerance,w.get('thickness',1.5))) for w in walls) for p in ps):
                issue('opening-host','Attach both opening ends to supported wall geometry or exclude the unsupported opening.',[row['source_id']])
    curves=unresolved_curves(plan,architecture)
    if curves:issue('curves','Resolve the marked curved-wall observations with matching curved geometry.',curves)
    rooms=[r for r in project['rooms'] if r.get('plan_id')==aid and r.get('bbox')]
    if not rooms:issue('sections','Add the reviewed sections and assign their floors in Area & sections.')
    for floor in sorted({r.get('floor') or '' for r in rooms}):
        measurements=[m for m in project.get('measurements',[]) if m.get('plan_id')==aid and m.get('floor')==floor]
        if not floor or not measurements:
            issue('outline',f'Add a reviewed floor outline for {floor or "the unassigned floor"} in Area & sections. Section boxes are not slab boundaries.');continue
        for measurement in measurements:
            try:
                outline=polygon(measurement.get('outline'))
                holes=[polygon(hole) for hole in measurement.get('exclusions',[])]
                sections=[]
                for room in rooms:
                    if room.get('floor')!=floor:continue
                    if not room.get('area_polygon'):raise ValueError('Review each section outline in Area & sections; detection boxes do not establish room geometry.')
                    sections.append(polygon(room['area_polygon']))
                totals=proportions(outline,sections,holes)
                if totals['outside']>1e-6:raise ValueError('Section outlines extend beyond the reviewed floor or into a void. Correct their boundaries.')
                if totals['overlap']>1e-6:raise ValueError('Section outlines overlap. Review the shared/open space boundaries.')
            except ValueError as exc:issue('outline',str(exc))
    visual=plan.get('vision_report')
    if visual:
        conflicts=[v['id'] for v in reconcile(visual)['review_issues'] if v['status'] not in ('accept','reject')]
        if conflicts:issue('conflicts','Resolve the conflicting source observations before completing geometry review.',conflicts)
    token=signature(plan,project);saved=plan.get('raster_validation') or {}
    valid=not issues and saved.get('fingerprint')==token and saved.get('complete') is True
    return {'fingerprint':token,'geometry_validated':bool(valid),'can_complete':not issues,
            'state':'reviewed' if valid else 'stale' if saved else 'incomplete',
            'issues':issues,'reviewed_at':saved.get('at') if valid else None,
            'scope':'User-reviewed geometry, not measured accuracy or generated-image approval.'}


def save(st,pid,aid,data):
    current=status(st,pid,aid);plan=st.asset(aid)
    if editing_busy(st,pid):raise ValueError('Finish active generation before completing boundary review.')
    if data.get('fingerprint')!=current['fingerprint']:raise ValueError('Geometry changed. Refresh its checks before completing review.')
    action=data.get('action','complete')
    if action not in ('complete','reopen','acknowledge-rescan'):raise ValueError('Choose a geometry review action.')
    if action=='complete':
        if not current['can_complete']:raise ValueError(current['issues'][0]['message'])
        if data.get('source_checked') is not True:raise ValueError('Check the original for missing boundaries, openings and floor voids before completing review.')
        if data.get('estimates_acknowledged') is not True:raise ValueError('Acknowledge any estimated scale, thickness and heights; review does not make them measured.')
    before=copy.deepcopy(plan)
    try:
        plan.setdefault('raster_validation_history',[]).append({'action':action,'at':now(),'previous':copy.deepcopy(plan.get('raster_validation'))})
        if action=='complete':plan['raster_validation']={'fingerprint':current['fingerprint'],'complete':True,'at':now(),'source_checked':True,'estimates_acknowledged':True}
        else:
            plan.pop('raster_validation',None)
            if action=='acknowledge-rescan':
                plan['raster_validation_history'][-1]['orphaned']=plan.pop('raster_orphaned_corrections',[])
        st.save()
    except Exception:plan.clear();plan.update(before);raise
    return status(st,pid,aid)
