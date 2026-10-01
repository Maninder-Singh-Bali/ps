"""Persistent local project records. Atomic writes; no image blobs in JSON."""
from pathlib import Path
import copy, json, os, threading, time, uuid

def uid(): return uuid.uuid4().hex[:16]
def now(): return time.time()

def editing_busy(store,pid):
    """Generation owns its inputs; guarded background import suggestions do not."""
    return any(j['project_id']==pid and j['kind'] not in ('plan_setup','vision_study','raster_reconstruction') and
               j['status'] in ('queued','waiting','running') for j in store.db['jobs'].values())

class Store:
    def __init__(self, root):
        self.root=Path(root).resolve();self.root.mkdir(parents=True,exist_ok=True)
        self.lock=threading.RLock();self.path=self.root/'studio.json';self.storage_operations={};self.moving_projects=set();self.storage_errors={}
        if self.path.exists():self.db=json.loads(self.path.read_text(encoding='utf8'))
        else:self.db={'version':1,'projects':{},'assets':{},'jobs':{},'settings':{'comfy_url':'http://127.0.0.1:8190','vision_url':'http://127.0.0.1:11434','vision_model':'','auto_release':True}};self.save()
    def save(self):
        with self.lock:
            temp=self.path.with_suffix('.tmp');temp.write_text(json.dumps(self.db,indent=2),encoding='utf8');os.replace(temp,self.path)
            from project_storage import save_manifest
            for pid,p in self.db['projects'].items():
                if p.get('storage_version')!=2:continue
                try:save_manifest(self,pid);self.storage_errors.pop(pid,None)
                except OSError as e:self.storage_errors[pid]=str(e)
    def snapshot(self):
        with self.lock:return copy.deepcopy(self.db)
    def review_snapshot(self):
        """Read-only request view: expensive geometry work does not lock edits."""
        view=copy.copy(self);view.db=self.snapshot();view.lock=threading.RLock();view._review_cache={}
        def readonly():raise RuntimeError('A review snapshot cannot save changes.')
        view.save=readonly
        return view
    def project(self,pid):
        if pid not in self.db['projects']:raise ValueError('Project not found')
        return self.db['projects'][pid]
    def room(self,pid,rid):
        for r in self.project(pid)['rooms']:
            if r['id']==rid:return r
        raise ValueError('Room not found')
    def create_project(self,name,save_parent=None):
        with self.lock:
            p={'id':uid(),'name':name.strip()[:100] or 'Untitled project','created':now(),'updated':now(),'floor_plans':[],'rooms':[],'map_confirmed':False,'map_revision':0,'seed':2909202661,'style':'Refined contemporary-classic architecture, natural walnut, pale stone, bronze details. Real architectural photography, natural colour, soft daylight and restrained contrast. No people.','music_id':None}
            from project_storage import allocate, save_manifest
            folder=allocate(save_parent or self.root/'projects',p['name'],p['id'])
            p['storage_path']=str(folder);p['storage_version']=2
            self.db['projects'][p['id']]=p
            try:save_manifest(self,p['id']);self.save()
            except Exception:self.db['projects'].pop(p['id'],None);raise
            return p
    def add_room(self,pid,name='New room',floor='Ground floor',plan_id=None,bbox=None,kind='room',**extra):
        with self.lock:
            p=self.project(pid);r={'id':uid(),'name':name[:100],'floor':floor[:50],'kind':kind,'plan_id':plan_id,'bbox':bbox,'notes':'','references':[],'anchor_id':None,'images':[],'videos':[],'approved_image_id':None,'approved_video_id':None,'revision':1,'confidence':'manual','detection_note':'Added manually',**extra}
            p['rooms'].append(r);p['map_confirmed']=False;p['map_revision']+=1;p['updated']=now();self.save();return r
    def invalidate(self,pid,room):
        room['revision']+=1;room['approved_image_id']=None;room['approved_video_id']=None
        self.project(pid)['updated']=now()
    def asset(self,aid):
        if aid not in self.db['assets']:raise ValueError('Asset not found')
        return self.db['assets'][aid]
    def new_job(self,pid,kind,room_id=None,**extra):
        with self.lock:
            p=self.project(pid)
            scoped=kind in ('plan_setup','vision_study','raster_reconstruction') and extra.get('plan_id') in self.db['assets']
            if scoped:
                from source_scope import capture
                extra['source_scope']=capture(self.asset(extra['plan_id']),approved=False)
            if kind=='analysis':
                from source_scope import capture
                extra['source_scopes']={aid:capture(self.asset(aid)) for aid in extra.get('plan_ids',[])}
            for job in self.db['jobs'].values():
                if job['project_id']==pid and job['kind']==kind and job.get('room_id')==room_id and job['status'] in ('queued','waiting','running'):
                    if kind in ('plan_setup','vision_study','raster_reconstruction') and job.get('plan_id')!=extra.get('plan_id'):continue
                    if scoped and job.get('source_scope',{}).get('key')!=extra['source_scope']['key']:continue
                    if kind=='component_download' and job.get('component_id')!=extra.get('component_id'):continue
                    return job
            j={'id':uid(),'project_id':pid,'room_id':room_id,'kind':kind,'status':'queued','stage':'Queued','progress':None,'created':now(),'updated':now(),'error':None,'prompt_id':None,'events':[],**extra}
            self.db['jobs'][j['id']]=j;p['updated']=now();self.save();return j
    def update_job(self,jid,**fields):
        with self.lock:
            j=self.db['jobs'][jid];j.update(fields);j['updated']=now();self.save();return j

def assert_image_gate(project,room):
    if not project['map_confirmed']:raise ValueError('Confirm the room map before generating images.')
    if not room.get('anchor_id') and not room.get('bbox'):raise ValueError('Mark this room on the floor plan, or upload a room reference first.')

def approved_image(store,project,room):
    aid=room.get('approved_image_id')
    if not aid:raise ValueError('Approve a room image before generating video.')
    a=store.asset(aid)
    if a.get('approved_revision')!=room['revision'] or a.get('room_id')!=room['id']:
        raise ValueError('The room changed after approval. Review and approve an updated image first.')
    if a.get('project_id')!=project['id']:raise ValueError('Approved image belongs to another project.')
    import scene_control
    scene_control.file_identity(store,aid)
    source_job=store.db['jobs'].get(a.get('job_id'),{})
    if source_job.get('scene_manifest'):scene_control.assert_scene(store,project,room,source_job['scene_manifest'])
    return a
