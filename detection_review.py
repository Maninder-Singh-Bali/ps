"""Deterministic proposal reconciliation. No model confidence is an approval."""
import copy
import hashlib
import json
import re

VERSION=1
ALIASES={'wc':'toilet','water closet':'toilet','lavatory':'toilet','wash basin':'basin','washbasin':'basin',
         'couch':'sofa','settee':'sofa','arm chair':'armchair','dining chair':'chair','stools':'stool',
         'stairs':'stair','staircase':'stair','sliding doors':'sliding door','windows':'window',
         'doors':'door','coffee tables':'coffee table','side tables':'side table','chairs':'chair'}

def category(f):
    name=re.sub(r'[^a-z0-9]+',' ',str(f.get('object_type') or f.get('label') or f.get('kind','unknown')).lower()).strip()
    return ALIASES.get(name,name)

def iou(a,b):
    overlap=max(0,min(a[0]+a[2],b[0]+b[2])-max(a[0],b[0]))*max(0,min(a[1]+a[3],b[1]+b[3])-max(a[1],b[1]))
    union=a[2]*a[3]+b[2]*b[3]-overlap
    return overlap/union if union>0 else 0

def identity(value):return hashlib.sha256(json.dumps(value,sort_keys=True).encode()).hexdigest()[:20]

def reconcile(report):
    """Keep incompatible alternatives together. Never mutate saved observations."""
    result=copy.deepcopy(report);rows=result.get('features',[]);issues=[]
    for f in rows:
        f.setdefault('id','observation'+identity([result.get('source_sha256'),f.get('bbox'),category(f),f.get('kind')]))
        f.setdefault('original_location_unresolved',bool(f.get('location_unresolved')))
    parents=list(range(len(rows)))
    def root(i):
        while parents[i]!=i:i=parents[i]
        return i
    # An exact-ish box shared by incompatible classes is a conflict, whereas
    # room membership and supported parent/child overlaps are not duplicates.
    hierarchy=[{'bed','pillow'},{'bed','cushion'},{'kitchen counter','sink'},
               {'countertop','sink'},{'kitchen counter','hob'},{'desk','lamp'},
               {'table','lamp'},{'sofa','cushion'}]
    for i,a in enumerate(rows):
        if a.get('kind')=='space':continue
        for j in range(i+1,len(rows)):
            b=rows[j]
            if a.get('panel_id')!=b.get('panel_id'):continue
            if b.get('kind')=='space' or category(a)==category(b):continue
            if {category(a),category(b)} in hierarchy:continue
            if iou(a['bbox'],b['bbox'])>=.8:
                parents[root(j)]=root(i)
    groups={}
    for i in range(len(rows)):groups.setdefault(root(i),[]).append(rows[i])
    for members in groups.values():
        if len(members)<2:continue
        key='conflict-'+identity(sorted(f['id'] for f in members))
        xs=[f['bbox'][0] for f in members];ys=[f['bbox'][1] for f in members]
        right=max(f['bbox'][0]+f['bbox'][2] for f in members);bottom=max(f['bbox'][1]+f['bbox'][3] for f in members)
        issues.append({'id':key,'type':'classification_conflict','status':'unresolved','element_ids':[f['id'] for f in members],
            'bbox':[min(xs),min(ys),right-min(xs),bottom-min(ys)],'message':'Conflicting labels: '+', '.join(dict.fromkeys(f.get('label',category(f)) for f in members)),
            'alternatives':[{'id':f['id'],'label':f.get('label',category(f)),'evidence':f.get('evidence','')} for f in members]})
        for f in members:f.update(conflict_id=key,location_unresolved=True)
    for f in rows:
        if f.get('source_agreement')=='disagrees':
            issues.append({'id':'agreement-'+f['id'],'type':'source_disagreement','status':'unresolved','element_ids':[f['id']],
                           'bbox':f['bbox'],'message':f.get('label','Object')+': original and enhanced readings disagree.'})
            f['location_unresolved']=True
    result['review_issues']=issues
    for issue in issues:
        decision=result.get('review_decisions',{}).get(issue['id'])
        if not decision:continue
        issue['status']=decision['action'];issue['decision']=decision
        for f in rows:
            if f['id'] not in issue['element_ids']:continue
            if decision['action']=='accept' and decision.get('element_id')==f['id']:
                f['review_resolution']='accepted'
                # Classification choice cannot make an unknown footprint valid.
                if f.get('kind')!='unknown':f['location_unresolved']=f['original_location_unresolved']
            elif decision['action'] in ('reject','accept'):f['review_resolution']='rejected'
    # A classification choice cannot also resolve a separate source disagreement.
    unresolved_ids={element for issue in issues if issue['status'] not in ('accept','reject') for element in issue['element_ids']}
    for f in rows:
        if f['id'] in unresolved_ids:f['location_unresolved']=True
    result['geometry_validated']=False
    result['user_reviewed']=bool(result.get('reviewed',False))
    result['reconciliation_version']=VERSION
    return result

def save_decision(store,pid,aid,data):
    import time
    plan=store.asset(aid);project=store.project(pid)
    if aid not in project['floor_plans']:raise ValueError('Choose this project’s plan.')
    report=plan.get('vision_report')
    if not report:raise ValueError('No analysis to review yet.')
    revision=plan.get('review_revision',0)
    if data.get('revision')!=revision:raise ValueError('Review changed. Refresh before saving.')
    if data.get('source_sha256')!=report.get('source_sha256') or data.get('pipeline_key')!=report.get('pipeline_key'):
        raise ValueError('Analysis changed. Review the updated evidence.')
    if report.get('stale'):raise ValueError('This analysis is outdated. Review the source and wait for current-scope analysis.')
    current=reconcile(report);issue=next((v for v in current['review_issues'] if v['id']==data.get('issue_id')),None)
    if not issue:raise ValueError('This issue is no longer present.')
    action=data.get('action');element=data.get('element_id')
    if action not in ('accept','reject','defer'):raise ValueError('Choose accept, reject or defer.')
    if action=='accept' and element not in issue['element_ids']:raise ValueError('Choose one of the shown alternatives.')
    decision={'action':action,'element_id':element if action=='accept' else None,'updated':time.time()}
    before=copy.deepcopy(plan)
    try:
        report.setdefault('review_decisions',{})[issue['id']]=decision
        plan.setdefault('review_history',[]).append({'issue_id':issue['id'],**decision,'revision':revision+1})
        plan['review_revision']=revision+1;store.save()
    except Exception:
        plan.clear();plan.update(before)
        raise
    return {'revision':revision+1,'report':reconcile(report)}

def compare_sources(enhanced,original):
    for f in enhanced:
        matches=[v for v in original if category(f)==category(v) and iou(f['bbox'],v['bbox'])>=.5]
        f['source_agreement']='agrees' if matches else 'disagrees'
        f['original_matches']=[v['id'] for v in matches]
    return enhanced
