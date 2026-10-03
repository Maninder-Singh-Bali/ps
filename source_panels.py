"""Conservative local source triage. Panel rectangles select evidence, not walls."""
import copy,hashlib,json,math
from pathlib import Path
import numpy as np
from PIL import Image,ImageOps

VERSION=1
def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True).encode()).hexdigest()

def metrics(image):
    a=np.asarray(image.convert('RGB'),dtype=float);g=a.mean(2);ink=g<180
    white=float((a.min(2)>225).mean());color=float(((a.max(2)-a.min(2))>28).mean())
    # Long orthogonal strokes distinguish sparse drafting from prose. This is
    # evidence for triage, not a universal learned source classifier.
    long=np.zeros_like(ink);minimum=max(18,int(min(g.shape)*.07))
    for axis in (0,1):
        arr=ink if axis==0 else ink.T;out=long if axis==0 else long.T
        for i,row in enumerate(arr):
            edges=np.flatnonzero(np.diff(np.r_[False,row,False].astype(np.int8)))
            for l,r in zip(edges[::2],edges[1::2]):
                if r-l>=minimum:out[i,l:r]=True
    line=float(long.sum()/max(ink.sum(),1))
    return {'white':round(white,4),'color':round(color,4),'long_stroke_fraction':round(line,4),'ink':round(float(ink.mean()),4)}

def likely(m):return m['white']>.70 and m['color']<.055 and m['long_stroke_fraction']>.12 and .005<m['ink']<.28

def classify(path):
    with Image.open(path) as im:im=ImageOps.exif_transpose(im).convert('RGB');size=im.size;im.thumbnail((900,900))
    m=metrics(im);panels=[];w,h=im.size
    if likely(m):kind='plan';panels=[{'id':'panel1','bbox':[0,0,1,1],'status':'proposed'}]
    else:
        a=np.asarray(im);g=a.mean(2);white=(a.min(2)>225).mean(1);color=((a.max(2).astype(float)-a.min(2))>28).mean(1)
        # Find broad near-white drafting bands, allowing sparse text/line rows.
        window=max(7,h//35);kernel=np.ones(window)/window
        good=(np.convolve(white,kernel,'same')>.69)&(np.convolve(color,kernel,'same')<.16)
        # Merge interruptions from dense annotation rows within a drafting band.
        # These are crop proposals only and still require explicit review.
        gaps=np.flatnonzero(np.diff(np.r_[False,~good,False].astype(np.int8)))
        for a,b in zip(gaps[::2],gaps[1::2]):
            if a>0 and b<h and b-a<h*.07:good[a:b]=True
        edges=np.flatnonzero(np.diff(np.r_[False,good,False].astype(np.int8)))
        for top,bottom in zip(edges[::2],edges[1::2]):
            if bottom-top<h*.17:continue
            crop=im.crop((0,top,w,bottom));mm=metrics(crop)
            if mm['white']<.70 or mm['long_stroke_fraction']<.15 or mm['ink']<.01:continue
            # Split distinct plans at broad empty vertical gutters. Keep the
            # original sheet coordinates; never align floors by crop position.
            ink=np.asarray(crop.convert('L'))<180;occupied=ink.mean(0)>.008
            gap=max(4,w//70);smoothed=np.convolve(occupied,np.ones(gap),'same')>0
            xe=np.flatnonzero(np.diff(np.r_[False,smoothed,False].astype(np.int8)))
            for left,right in zip(xe[::2],xe[1::2]):
                if right-left<w*.10:continue
                panel=im.crop((left,top,right,bottom));pm=metrics(panel)
                if pm['white']>.60 and pm['long_stroke_fraction']>.15:panels.append({'id':f'panel{len(panels)+1}','bbox':[left/w,top/h,(right-left)/w,(bottom-top)/h],'status':'proposed'})
        kind='mixed' if panels else 'perspective_or_photo' if m['color']>.12 and m['white']<.72 else 'uncertain'
    # Mixed/uncertain crops require a quick source review; they never trace until
    # the user confirms/corrects the proposed panels in the dashboard.
    return {'version':VERSION,'kind':kind,'panels':panels,'metrics':m,'source_sha256':hashlib.sha256(Path(path).read_bytes()).hexdigest(),
            'revision':0,'reviewed':False,'automatic_trace':False,'source_size':list(size),
            'method':'CPU whiteness/chroma, long orthogonal strokes and whitespace panel proposals; uncertain sources require crop review.'}

def valid(plan):
    s=plan.get('source_review') or {}
    return s.get('source_sha256')==plan.get('sha256') and s.get('kind') in ('plan','mixed') and bool(s.get('panels')) and s.get('reviewed') is True


def ensure(st,pid,aid):
    """Classify outside the store lock, then attach only to unchanged evidence."""
    with st.lock:
        plan=copy.deepcopy(st.asset(aid))
        if plan.get('plan_source',{}).get('vector'):return valid(plan) if plan.get('source_review') else True
        if plan.get('source_review',{}).get('source_sha256')==plan.get('sha256'):return valid(plan)
    result=classify(plan['path'])
    with st.lock:
        current=st.asset(aid)
        if current.get('sha256')!=plan.get('sha256'):raise ValueError('Source changed during classification. Retry.')
        if current.get('source_review',{}).get('source_sha256')!=current.get('sha256'):
            if current.get('source_review'):current.setdefault('source_review_archive',[]).append(current['source_review'])
            current['source_review']=result;st.save()
        return valid(current)

def save(st,pid,aid,data):
    """Commit crop revision, invalidation and follow-up jobs as one saved change."""
    with st.lock:
        plan=st.asset(aid);project=st.project(pid)
        staged=copy.copy(st)
        staged.db={**st.db,'assets':{**st.db['assets'],aid:copy.deepcopy(plan)},
                   'projects':{**st.db['projects'],pid:copy.deepcopy(project)},'jobs':copy.deepcopy(st.db['jobs'])}
        staged.save=lambda:None
        _save(staged,pid,aid,data)
        old_plan=copy.deepcopy(plan);old_project=copy.deepcopy(project)
        changed={key:value for key,value in staged.db['jobs'].items() if value!=st.db['jobs'].get(key)}
        old_jobs={key:copy.deepcopy(st.db['jobs'].get(key)) for key in changed}
        try:
            plan.clear();plan.update(staged.asset(aid));project.clear();project.update(staged.project(pid))
            for key,value in changed.items():
                if key in st.db['jobs']:st.db['jobs'][key].clear();st.db['jobs'][key].update(value)
                else:st.db['jobs'][key]=value
            st.save()
        except Exception:
            plan.clear();plan.update(old_plan);project.clear();project.update(old_project)
            for key,value in old_jobs.items():
                if value is None:st.db['jobs'].pop(key,None)
                else:st.db['jobs'][key].clear();st.db['jobs'][key].update(value)
            raise
        return plan['source_review']


def _save(st,pid,aid,data):
    from store import editing_busy,now
    plan=st.asset(aid)
    if aid not in st.project(pid)['floor_plans']:raise ValueError('Choose this project’s source.')
    if editing_busy(st,pid):raise ValueError('Finish generation before changing source panels.')
    current=plan.get('source_review') or {};before=copy.deepcopy(plan);project=st.project(pid);old_project=copy.deepcopy(project)
    if data.get('revision')!=current.get('revision',0):raise ValueError('Source review changed. Reopen the panel controls.')
    action=data.get('action','save')
    if action=='undo':
        if not plan.get('source_review_undo'):raise ValueError('No source panel edit to undo.')
        review=plan['source_review_undo'].pop()
    else:
        kind=data.get('kind');panels=data.get('panels',[])
        if kind not in ('plan','mixed','perspective_or_photo','uncertain'):raise ValueError('Choose the source type.')
        if not isinstance(panels,list) or len(panels)>12:raise ValueError('Use at most 12 plan panels.')
        clean=[]
        for i,p in enumerate(panels):
            if not isinstance(p,dict):raise ValueError('Mark a rectangular plan panel.')
            b=p.get('bbox');
            if not isinstance(b,list) or len(b)!=4 or any(type(v) not in (int,float) or not math.isfinite(v) for v in b):raise ValueError('Mark a rectangular plan panel.')
            x,y,w,h=b
            if min(x,y)<0 or min(w,h)<.02 or x+w>1.00001 or y+h>1.00001:raise ValueError('Keep plan panels inside the original.')
            panel_id=str(p.get('id') or f'panel{i+1}')
            if not panel_id.replace('-','').replace('_','').isalnum() or len(panel_id)>60 or any(v['id']==panel_id for v in clean):raise ValueError('Use unique panel identities.')
            clean.append({'id':panel_id,'bbox':b,'floor':str(p.get('floor') or '')[:80],'status':'reviewed'})
        if kind in ('plan','mixed') and not clean:raise ValueError('Mark at least one plan panel.')
        if data.get('checked') is not True:raise ValueError('Confirm that the selected panels contain top-down plans only.')
        plan.setdefault('source_review_undo',[]).append(copy.deepcopy(current))
        review={**current,'kind':kind,'panels':clean if kind in ('plan','mixed') else [],'reviewed':True,'automatic_trace':False}
    review.update(revision=current.get('revision',0)+1,at=now(),source_sha256=plan['sha256'])
    plan['source_review']=review;plan.pop('raster_validation',None)
    try:
        project['map_confirmed']=False
        for room in project['rooms']:
            if room.get('plan_id')==aid:st.invalidate(pid,room)
        st.save()
    except Exception:plan.clear();plan.update(before);project.clear();project.update(old_project);raise
    # Cancel superseded work without deleting its report or manually reviewed data.
    from source_scope import capture
    scope=capture(plan,approved=False)
    for job in list(st.db['jobs'].values()):
        if job.get('plan_id')==aid and job['kind'] in ('plan_setup','vision_study','raster_reconstruction') and job['status'] in ('queued','waiting','running'):
            if job.get('source_scope',{}).get('key')!=scope['key']:
                st.update_job(job['id'],status='cancelled',stage='Superseded by source panel review',finished=now())
    if plan.get('vision_report'):plan['vision_report']['stale']=True
    plan.setdefault('setup',{})['status']='queued' if valid(plan) else 'blocked_source'
    st.save()
    if valid(plan):
        st.new_job(pid,'raster_reconstruction',plan_id=aid)
        st.new_job(pid,'plan_setup',plan_id=aid)
    return review

def mask_for(size,panels):
    w,h=size;mask=np.zeros((h,w),bool)
    for p in panels:
        x,y,ww,hh=p['bbox'];mask[max(0,round(y*h)):min(h,round((y+hh)*h)),max(0,round(x*w)):min(w,round((x+ww)*w))]=True
    return mask
