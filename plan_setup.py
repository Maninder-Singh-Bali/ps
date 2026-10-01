"""Automatic import preparation. Source evidence stays unapproved.

Each page gets one queued job. Slow readers never hold the project lock; results
are applied only if the target page is untouched. Other floors remain editable.
"""
import copy
import math
from store import now
from scene_scale import clean_model
import analysis
import plan_reading
import project_storage

PROTOCOL_VERSION = 2


def queue_visual(engine,pid,aid):
    """Use installed local capabilities; never download dependencies on import."""
    root=engine.app_root
    if (root/'runtime'/'ollama'/'ollama.exe').exists() or engine.store.db.get('settings',{}).get('vision_model'):
        st=engine.store
        st.new_job(pid,'vision_study',plan_id=aid,section_ids=[],input_revision=st.project(pid)['map_revision'],
                   study_revision=st.asset(aid).get('plan_reading',{}).get('revision',0),automatic=True)


def initialize(plan):
    site=plan.setdefault('drawing',{}).setdefault('site',{})
    site['model']=clean_model(site.get('model',{}))
    plan.setdefault('setup',{'protocol_version':PROTOCOL_VERSION,'status':'queued',
                            'warnings':[],'reviewed':False})


def fingerprint(plan,project):
    return copy.deepcopy([plan.get('sha256'),plan.get('drawing'),plan.get('plan_reading'),
                          [r for r in project['rooms'] if r.get('plan_id')==plan['id']]])


def normalized_rooms(rows,aid):
    result=[]
    for row in rows[:100]:
        box=row.get('bbox')
        if isinstance(box,list) and len(box)==4 and all(type(v) in (float,int) and math.isfinite(v) for v in box):
            x,y,w,h=box;x=max(0,min(1,x));y=max(0,min(1,y))
            w=min(w,1-x);h=min(h,1-y);box=[x,y,w,h] if min(w,h)>=.005 else None
        else:box=None
        result.append(dict(name=str(row.get('name','Unlabelled area'))[:100],
                           floor=str(row.get('floor','Needs floor assignment'))[:50],
                           plan_id=aid,bbox=box,kind=row.get('kind') if row.get('kind') in ('room','outdoor','circulation') else 'room',
                           confidence='proposal',detection_note=str(row.get('detection_note','Review suggested boundary.'))[:500]))
    return result


def run(engine,job):
    st=engine.store;pid=job['project_id'];aid=job['plan_id']
    with st.lock:
        p=st.project(pid);a=st.asset(aid)
        if aid not in p['floor_plans']:raise ValueError('The imported plan is no longer in this project.')
        if a.get('setup',{}).get('status') in ('ready','needs_review'):
            st.update_job(job['id'],status='completed',stage='Plan already prepared',progress=100,finished=now());return
        original=fingerprint(a,p);plan=copy.deepcopy(a)
    st.update_job(job['id'],status='running',stage='Preparing floor plan',progress=None)
    warnings=[];rooms=[];reading=None
    try:reading=plan_reading.propose_reading(plan,plan.get('plan_reading',{}))
    except Exception as exc:warnings.append('Structure reading needs review: '+str(exc)[:250])
    try:
        folder=project_storage.analysis_folder(st,pid,job['id'],aid)
        result=analysis.analyze_local(plan['path'],aid,folder,
             lambda stage,value:st.update_job(job['id'],stage=stage,progress=value))
        rooms=normalized_rooms(result.get('rooms',[]),aid)
        warnings.extend(result.get('warnings',[]))
    except Exception as exc:warnings.append('Room labels need review: '+str(exc)[:250])
    warnings.extend((reading or {}).get('warnings',[]))
    if not plan.get('plan_source',{}).get('metres_per_pixel'):
        warnings.append('Plan scale is estimated until a known dimension is supplied. Wall and human heights do not determine drawing scale.')
    with st.lock:
        # An editor/save or another reader wins over background proposals.
        current=st.asset(aid);project=st.project(pid)
        if fingerprint(current,project)!=original or any(r.get('plan_id')==aid for r in project['rooms']):
            current['setup']={**current.get('setup',{}),'status':'needs_review','warnings':warnings,
                              'suggested_rooms':rooms,'suggested_reading':reading,'reviewed':False,
                              'note':'Plan changed during setup; existing edits were preserved.'}
            st.update_job(job['id'],status='completed',stage='Suggestions ready; existing edits kept',progress=100,finished=now())
            queue_visual(engine,pid,aid);return
        staged=copy.copy(st);staged.db={**st.db,'projects':{**st.db['projects'],pid:copy.deepcopy(project)},
            'assets':{**st.db['assets'],aid:copy.deepcopy(current)},'jobs':copy.deepcopy(st.db['jobs'])}
        staged.save=lambda:None
        for row in rooms:staged.add_room(pid,**row)
        target=staged.asset(aid)
        if reading:target['plan_reading']=reading
        target['setup']={'protocol_version':PROTOCOL_VERSION,'status':'needs_review',
                         'warnings':list(dict.fromkeys(warnings)),'reviewed':False,'completed':now()}
        staged.project(pid)['map_confirmed']=False
        staged.update_job(job['id'],status='completed',stage=f'{len(rooms)} suggested sections · review required',progress=100,finished=now())
        previous=st.db
        try:st.db=staged.db;st.save()
        except Exception:st.db=previous;raise
        queue_visual(engine,pid,aid)
