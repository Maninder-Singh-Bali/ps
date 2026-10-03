"""Explicitly linked manual plans use the active Store as their atomic authority.
Unlinked correction drafts stay isolated. No implicit activation or generation.
"""
import copy
import plan_drafts
from store import editing_busy


def linked_plan(store,key):
    matches=[a for a in store.db['assets'].values() if a.get('manual_draft_id')==key]
    if len(matches)>1:raise ValueError('This editable plan is linked to multiple assets; resolve the link before editing.')
    return matches[0] if matches else None


def get(store,key):
    plan=linked_plan(store,key)
    if not plan:return plan_drafts.get(key)
    return copy.deepcopy(plan['manual_document'])


def listing(store):
    rows=plan_drafts.listing()
    for plan in store.db['assets'].values():
        if not plan.get('manual_draft_id'):continue
        d=plan['manual_document'];rows=[r for r in rows if r['id']!=d['id']]
        rows.insert(0,{k:d.get(k) for k in ('id','name','revision','updated') }|{'count':len(d['features']),'active_project_id':plan['project_id']})
    return rows


def save(store,key,data):
    with store.lock:
        plan=linked_plan(store,key)
        if not plan:return plan_drafts.save(key,data)
        p=store.project(plan['project_id']);base=plan['manual_document']
        if editing_busy(store,p['id']):raise ValueError('Wait for this project’s current job before editing its shared scene.')
        if data.get('revision')!=base['revision']:raise ValueError('This plan changed in another window. Reopen before saving.')
        d=plan_drafts.validate(data,base)
        if not d.get('calibration'):raise ValueError('The active apartment must retain a verified drawing scale.')
        old=copy.deepcopy(store.db)
        try:
            d.update(revision=base['revision']+1,updated=plan_drafts.stamp(),active_project_id=p['id'])
            drawing=plan['drawing'];before=copy.deepcopy(drawing)
            drawing.update(features=copy.deepcopy(d['features']),surface_design=copy.deepcopy(d.get('surface_design',{})))
            drawing['site']['model'].update(metres_per_pixel=d['calibration']['metres_per_pixel'])
            drawing['site']['model']['wall_heights'][plan['manual_floor']]=d['wall_height_m']
            plan['manual_document']=d
            if before!=drawing:
                for r in p['rooms']:
                    if r.get('plan_id')==plan['id']:store.invalidate(p['id'],r)
                p['map_revision']+=1
                plan['manual_edit_review']='Saved geometry/design changed; review updated guide before any further generation.'
            store.save()
        except Exception:store.db=old;raise
        return copy.deepcopy(d)


def preview(store,data):
    plan=linked_plan(store,data.get('id'))
    if not plan:return plan_drafts.preview(data)
    snap=store.review_snapshot();plan=linked_plan(snap,data['id']);d=plan_drafts.validate(data,plan['manual_document'])
    plan['drawing'].update(features=d['features'],surface_design=d.get('surface_design',{}))
    plan['drawing']['site']['model'].update(metres_per_pixel=d['calibration']['metres_per_pixel'])
    plan['drawing']['site']['model']['wall_heights'][plan['manual_floor']]=d['wall_height_m']
    from shared_floor import build
    p=snap.project(plan['project_id']);room=next(r for r in p['rooms'] if r['id']==p['manual_preview_room_id'])
    return build(snap,room)
