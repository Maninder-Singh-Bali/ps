"""Mac/lightweight backend adapter. Browser never receives the worker credential."""
import copy, hashlib, ipaddress, json, threading, time
from pathlib import Path
from urllib.parse import urlparse
import requests
from engine import Engine
from worker_protocol import contract
import project_storage

class WorkerResponseError(ValueError):
    def __init__(self,message,status_code):
        super().__init__(message);self.status_code=status_code

class Client:
    def __init__(self,path):
        p=Path(path).resolve();c=json.loads(p.read_text(encoding='utf-8-sig'))
        self.url=c['url'].rstrip('/');u=urlparse(self.url)
        if u.scheme!='https' or not ipaddress.ip_address(u.hostname).is_private or u.path or u.query or u.fragment or u.username:
            raise ValueError('Worker requires a private LAN IP and HTTPS, with no credentials in its URL.')
        self.session=requests.Session();self.session.trust_env=False
        self.session.verify=str((p.parent/c['certificate']).resolve())
        self.session.headers['Authorization']='Bearer '+(p.parent/c['token_file']).read_text().strip()
    def request(self,method,path,**kw):
        r=self.session.request(method,self.url+path,timeout=kw.pop('timeout',30),allow_redirects=False,**kw)
        if r.status_code!=200:
            try:message=r.json().get('error','Worker request failed')
            except Exception:message='Worker request failed'
            raise WorkerResponseError(message,r.status_code)
        return r
    def get(self,path):return self.request('GET',path).json()
    def post(self,path,body):return self.request('POST',path,json=body).json()

class RemoteServices:
    # The client lane must stay alive to reconcile even when renderer is stopped.
    prepared=True
    process=None
    def __init__(self,engine):
        self.engine=engine;self._status=None;self._check_lock=threading.Lock()
    def snapshot(self,force=False):
        # Passive dashboard reads must never wake/contact the PC. Dispatch and
        # persistent job reconciliation retain their own live protocol checks.
        if force:
            with self._check_lock:
                try:
                    status=self.engine.remote.request('GET','/v1/status',timeout=5).json()
                    expected=contract(self.engine.app_root)
                    from hardware_status import describe
                    self._status={**status,'remote':True,'reachable':True,'checked':time.time(),
                        'checks':[describe(c) for c in status.get('checks',[])],
                        'video_capture_compatible':status.get('video_capture')==expected['video_capture'],
                        'video_compatible':bool(status.get('video') and all(status.get(k)==expected[k] for k in ('protocol','workflow','video_workflow')))}
                except Exception:
                    self._status={'state':'PC unavailable','message':'The PC could not be reached. You can keep designing on this Mac.',
                        'remote':True,'reachable':False,'checked':time.time(),'prepared':False,'ownership':'none','active_jobs':0}
        status=copy.deepcopy(self._status) if self._status else {
            'state':'Local design','message':'PC not checked. Keep it off for local design; image and video generation require the PC.',
            'remote':True,'reachable':False,'checked':None,'prepared':False,'ownership':'none','active_jobs':0}
        status['cached']=not force
        status['stale']=not status['checked'] or time.time()-status['checked']>30
        return status
    def prepare(self):return self.engine.remote.post('/v1/actions/prepare',{})
    def release(self):return self.engine.remote.post('/v1/actions/release',{})
    def stop_services(self):return self.engine.remote.post('/v1/actions/stop',{})
    def pause(self):return self.engine.remote.post('/v1/actions/pause',{})
    def resume(self):return self.engine.remote.post('/v1/actions/resume',{})
    def before_model(self,job):
        if job['kind'] not in ('image','reference','video'):raise ValueError('Remote mode supports images and video; model-based detection is unavailable.')

class RemoteEngine(Engine):
    def __init__(self,store,root,configuration):
        super().__init__(store,root);self.remote=Client(configuration);self.services=RemoteServices(self)
        with store.lock:
            for job in store.db['jobs'].values():
                if job.get('remote_job_id') and job['status'] in ('running','waiting','queued','interrupted'):
                    job.update(status='queued',stage='Reconnecting to saved PC job')
            store.save()
    def health(self,force=False):
        s=self.services.snapshot(force=force);return {'connected':bool(s.get('prepared') and not s['stale']),'running':s.get('active_jobs',0),'pending':0,'device':'Windows PC worker','checked':s['checked'],'cached':s['cached'],'stale':s['stale'],'remote':True}
    def get(self,route,timeout=20):
        if route=='/object_info':return self.remote.get('/v1/nodes')
        raise ValueError('This local renderer operation is unavailable in remote mode.')
    def upload(self,path):
        d=self.remote.request('POST','/v1/inputs',data=Path(path).read_bytes(),headers={'Content-Type':'application/octet-stream'},timeout=90).json()
        return 'asset:'+d['id']
    def download_output(self,entry):
        aid=entry['worker_asset'];raw=self.remote.request('GET','/v1/outputs/'+aid,timeout=180).content
        if hashlib.sha256(raw).hexdigest()!=aid:raise ValueError('Worker output checksum mismatch; nothing installed.')
        return raw
    def run_render(self,job):
        from generation_phase import assert_dispatch
        assert_dispatch(self.store,job)
        folder=project_storage.job_folder(self.store,job);folder.mkdir(parents=True,exist_ok=True)
        request_path=folder/'remote-request.json'
        if not job.get('remote_job_id'):
            status=self.remote.get('/v1/status');expected=contract(self.app_root)
            if status.get('protocol')!=expected['protocol'] or status.get('workflow')!=expected['workflow']:raise ValueError('Worker version differs. Deploy the same tested snapshot while idle.')
            if job['kind']=='video' and (not status.get('video') or status.get('video_workflow')!=expected['video_workflow']):raise ValueError('PC video support is not deployed or differs. Update the worker while idle; no input was transferred.')
            if job.get('video_capture') and status.get('video_capture')!=expected['video_capture']:raise ValueError('PC capture support is not deployed or differs; no input was transferred.')
            if job.get('video_capture'):
                from video_capture import missing
                absent=missing(self.app_root,self.remote.get('/v1/nodes'))
                if absent:raise ValueError('PC capture nodes unavailable: '+', '.join(absent))
            if not status.get('prepared'):raise ValueError('Prepare Studio on the PC worker before generation.')
            graph,node=({'image':self.build_image,'reference':self.build_reference,'video':self.build_video}[job['kind']])(job,folder)
            body={**expected,'id':job['id'],'kind':job['kind'],'graph':graph,'output_node':node}
            if job['kind']=='video':body['video_settings']={'duration':job['duration'],'motion':job.get('motion','still'),'preset':job['video_preset']}
            if job.get('video_capture'):body['video_settings']['capture']=job['video_capture']
            request_path.write_text(json.dumps(body),encoding='utf-8')
            (folder/'workflow.api.json').write_text(json.dumps(graph,indent=2),encoding='utf-8')
            job.update(remote_job_id=job['id'],output_node=node,started=time.time());self.store.save()
        body=json.loads(request_path.read_text(encoding='utf-8'))
        while not self.stop.is_set():
            if job['status']=='cancelled':return
            try:
                # Repeating this exact ID + body reconnects; it cannot add inference.
                if job['kind']=='video' or job.get('single_submission'):
                    try:result=self.remote.get('/v1/jobs/'+job['remote_job_id'])
                    except WorkerResponseError as exc:
                        if exc.status_code!=400 or not str(exc).startswith('Worker job not found.'):raise
                        # A saved client request is not proof the PC admitted it. Recheck
                        # approval/scene before a first or uncertain submission retry.
                        assert_dispatch(self.store,job)
                        if job['kind']=='video':self.assert_video_source(job)
                        elif job['kind']=='image':
                            from interior_style import view_context
                            import scene_control
                            project=self.store.project(job['project_id'])
                            room=view_context(self.store.room(project['id'],job['room_id']),job.get('view_id'))
                            if room['revision']!=job['input_revision']:raise ValueError('Room inputs changed before image submission.')
                            scene_control.assert_scene(self.store,project,room,job.get('scene_ticket'))
                            scene_control.assert_edit(room,job)
                        if job.get('single_submission'):
                            if job.get('remote_submission_intent'):
                                raise ValueError('Single-attempt submission was already attempted; worker has no matching job. No second submission allowed.')
                            job['remote_submission_intent']=time.time();self.store.save()
                        result=self.remote.post('/v1/jobs',body)
                else:result=self.remote.post('/v1/jobs',body)
                if result['status']=='completed':
                    history=self.remote.get('/v1/jobs/'+job['remote_job_id']+'/result')
                    (folder/'history.json').write_text(json.dumps(history,indent=2),encoding='utf-8')
                    if job.get('video_capture'):
                        from video_capture import evidence
                        manifest=evidence(history,job['id'])
                        if manifest.get('mp4',{}).get('sha256') not in result.get('outputs',{}):raise ValueError('Capture MP4 identity differs from worker output; evidence retained.')
                        (folder/'capture-manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
                    job['remote_result']=result;self.store.save()
                    self.finish_render(job,history,folder);return
                if result['status'] in ('failed','cancelled','interrupted'):
                    self.store.update_job(job['id'],status=result['status'],stage=result['stage'],error='PC job stopped. Inputs and any outputs retained; no automatic rerun.',finished=time.time());return
                self.store.update_job(job['id'],status='waiting',stage=result['stage'],**{k:result.get(k) for k in ('progress','progress_scope','steps','eta','render_tracking','node_type')})
            except (requests.RequestException,WorkerResponseError) as exc:
                if isinstance(exc,WorkerResponseError) and exc.status_code<500:raise
                self.store.update_job(job['id'],status='waiting',stage='Disconnected from PC; will reconnect to the same job',progress=None)
            self.stop.wait(2)
