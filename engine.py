"""ComfyUI integration: one owned job at a time, real sampling events, approval gates."""
from pathlib import Path
import copy, ctypes, hashlib, json, mimetypes, shutil, threading, time, re, subprocess
from urllib.parse import urlparse
import requests
import project_storage
import render_progress
from placement_map import create_guide, spatial_instructions, current_layout, room_dimensions, create_product_board
from PIL import Image
from store import uid, now, assert_image_gate, approved_image
from scene_sun import lighting_instruction
import scene_control
from prompt_compiler import prepare_edit

def local_url(value):
    u=urlparse(value)
    if u.scheme!='http' or u.hostname not in ('127.0.0.1','localhost','::1') or u.username or u.password or u.query or u.fragment:
        raise ValueError('Use a local HTTP engine address, such as http://127.0.0.1:8190.')
    return value.rstrip('/')

def memory_headroom():
    class Mem(ctypes.Structure):
        _fields_=[('length',ctypes.c_ulong),('load',ctypes.c_ulong)]+[(n,ctypes.c_ulonglong) for n in ['total','available','commit_total','commit_available','virtual_total','virtual_available','extended']]
    m=Mem();m.length=ctypes.sizeof(m)
    try:ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m));return m.available/2**30,m.commit_available/2**30
    except (AttributeError,OSError):return 999,999


def available_vram():
    """Probe without loading a model. None means unavailable, not unlimited VRAM."""
    try:
        result=subprocess.run(['nvidia-smi','--query-gpu=memory.free','--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=4,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        if result.returncode==0:return max(float(v)/1024 for v in result.stdout.strip().splitlines())
    except (OSError,ValueError,subprocess.SubprocessError):pass
    return None

def register_asset(store,pid,path,kind,room_id=None,**extra):
    path=Path(path)
    a={'id':uid(),'project_id':pid,'room_id':room_id,'kind':kind,'name':path.name,'path':str(path.resolve()),'created':now(),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),**extra}
    if kind not in ('video','music','film','pdf'):
        with Image.open(path) as im:a['width'],a['height']=im.size
    with store.lock:store.db['assets'][a['id']]=a;store.save()
    return a

class Engine:
    def __init__(self,store,app_root):
        self.store=store;self.app_root=Path(app_root);self.session=requests.Session();self.session.trust_env=False
        self.health_cache={};self.stop=threading.Event();self._worker_guard=threading.Lock();self._worker_started=False
    @property
    def url(self):return self.store.db['settings']['comfy_url']
    def get(self,route,timeout=20):
        r=self.session.get(self.url+route,timeout=timeout);r.raise_for_status();return r.json()
    def post(self,route,body):
        r=self.session.post(self.url+route,json=body,timeout=30);r.raise_for_status();return r.json() if r.content else {}
    def health(self,force=False):
        if not force and time.time()-self.health_cache.get('checked',0)<5:return self.health_cache
        try:
            q=self.get('/queue',3);stats=self.get('/system_stats',3)
            self.health_cache={'connected':True,'running':len(q['queue_running']),'pending':len(q['queue_pending']),'device':stats.get('devices',[{}])[0].get('name','Local engine'),'checked':time.time()}
        except Exception:self.health_cache={'connected':False,'running':0,'pending':0,'device':'Unavailable','checked':time.time()}
        self.health_cache['available_ram_gb']=round(memory_headroom()[0],1);return self.health_cache
    def upload(self,path):
        path=Path(path)
        with path.open('rb') as f:r=self.session.post(self.url+'/upload/image',files={'image':(path.name,f,'image/png')},data={'subfolder':'Pixeloid_Studio','type':'input'},timeout=40)
        r.raise_for_status();d=r.json();return (d.get('subfolder','')+'/'+d['name']).lstrip('/')
    def plan_crop(self,room,folder):
        a=self.store.asset(room['plan_id']);box=room['bbox']
        drawing=a.get('drawing',{})
        if drawing.get('guidance_asset_id') and (drawing.get('edits') or drawing.get('features')):a=self.store.asset(drawing['guidance_asset_id'])
        with Image.open(a['path']) as im:
            w,h=im.size;coords=(int(box[0]*w),int(box[1]*h),int((box[0]+box[2])*w),int((box[1]+box[3])*h))
            p=folder/'room_plan_reference.png';im.crop(coords).save(p);return p
    def build_image(self,job,folder):
        p=self.store.project(job['project_id']);room=self.store.room(p['id'],job['room_id']);assert_image_gate(p,room)
        if room['revision']!=job['input_revision']:raise ValueError('Room inputs changed while this image was queued. Generate again with the updated references.')
        scene=scene_control.assert_scene(self.store,p,room,job.get('scene_ticket'))
        control=scene_control.clean_control(self.store,p,room,room.get('scene_control',{}))
        from placement_map import active_references
        refs=active_references(self.store,room)
        surface_cleanup=control['mode']=='region' and bool(re.search(r'\b(remove|erase|clean)\b.{0,100}\b(text|writing|lettering|letters|watermarks?)\b',control.get('instruction',''),re.I))
        if surface_cleanup:refs=[]
        if len(refs)>6:raise ValueError('Use up to six active product references per image. You can keep more uploaded and disable unused ones.')
        anchor=self.store.asset(room['anchor_id']) if room.get('anchor_id') else None
        if control['mode']!='reference':anchor=self.store.asset(control['source_id'])
        # A saved block layout is the spatial authority for a new room view.
        # Explicit region/full-image edits retain their selected master instead.
        if control['mode']=='reference' and room.get('block_layout',{}).get('items'):anchor=None
        primary=Path(anchor['path']) if anchor else self.plan_crop(room,folder)
        from perspective_layout import create as create_perspective_layout
        perspective=create_perspective_layout(self.store,room,refs,folder) if not anchor else None
        if perspective:
            primary=perspective[0]
            job['layout_guide_id']=register_asset(self.store,p['id'],primary,'layout_guide',room['id'],job_id=job['id'])['id']
            job['perspective_layout']=perspective[1]
        g=json.loads((self.app_root/'templates/flux.json').read_text())
        for k in ['5','8','9','11','14','15']:g.pop(k,None)
        g['4']['inputs']['image']=self.upload(primary);g['10']['inputs']['pixels']=['4',0]
        pos,neg=['12',0],['13',0]
        descriptions=[]
        plan=self.store.asset(room['plan_id']) if room.get('plan_id') else {}
        drawing=plan.get('drawing',{})
        has_layout=not surface_cleanup and not perspective and bool(current_layout(room).get('items') or drawing.get('guidance_asset_id') and (drawing.get('edits') or drawing.get('features')))
        packed=len(refs)+1+int(has_layout)>4
        board=create_product_board(refs,folder) if packed else None
        for i,a in enumerate(refs):
            if packed and i>0:continue
            key=100+i*5
            g[str(key)]={'class_type':'LoadImage','inputs':{'image':self.upload(board if packed else a['path'])}}
            g[str(key+1)]={'class_type':'ImageScaleToTotalPixels','inputs':{'image':[str(key),0],'upscale_method':'lanczos','megapixels':1.0,'resolution_steps':16}}
            g[str(key+2)]={'class_type':'VAEEncode','inputs':{'pixels':[str(key+1),0],'vae':['3',0]}}
            g[str(key+3)]={'class_type':'ReferenceLatent','inputs':{'conditioning':pos,'latent':[str(key+2),0]}}
            g[str(key+4)]={'class_type':'ReferenceLatent','inputs':{'conditioning':neg,'latent':[str(key+2),0]}}
            pos,neg=[str(key+3),0],[str(key+4),0]
            descriptions.append(f"Image {i+2}: {a.get('category','furniture')} product reference only. Placement: {a.get('placement') or 'Use a plausible placement within the selected room without blocking circulation.'} Preserve this product's visible silhouette and materials; do not import its photographed room.")
        if packed:
            descriptions=["Image 2 is a labelled product-reference sheet, not the output composition. Use the product design in each numbered tile and ignore its photographed background. "+' '.join(f"Product {i+1}: {a.get('category','furniture')}. {a.get('placement','')}" for i,a in enumerate(refs))]
        guide=None if perspective or surface_cleanup else create_guide(self.store,room,refs,folder,packed)
        constraints=spatial_instructions(self.store,room,refs,packed,edit_existing=bool(anchor)) if guide or perspective else ''
        if guide:
            path,instructions=guide;key=200
            g[str(key)]={'class_type':'LoadImage','inputs':{'image':self.upload(path)}}
            g[str(key+1)]={'class_type':'VAEEncode','inputs':{'pixels':[str(key),0],'vae':['3',0]}}
            g[str(key+2)]={'class_type':'ReferenceLatent','inputs':{'conditioning':pos,'latent':[str(key+1),0]}}
            g[str(key+3)]={'class_type':'ReferenceLatent','inputs':{'conditioning':neg,'latent':[str(key+1),0]}}
            pos,neg=[str(key+2),0],[str(key+3),0]
            descriptions.append(f"Image {3 if packed else len(refs)+2} is the user's top-down furniture placement diagram, not a room photograph. Use its numbered markers and facing arrows to place each corresponding product in the room. Preserve architecture from image 1. Do not render the diagram, numbers, arrows, labels or borders in the photograph. "+instructions)
        if perspective:
            prompt=(f"Turn image 1 into a natural full-frame architectural photograph of the {room['name']}. Image 1 is a perspective layout guide computed from corrected plan lines and furniture markers. Keep its camera view, wall openings, furniture positions and depth ordering. Replace each simple furniture placeholder with the corresponding real product design in images 2 onward, matching object category and the specified placement. The furniture references define the design; image 1 defines the composition. Keep exactly one instance of each product at its placeholder location. Preserve the curved product shapes from their references instead of copying the rectangular placeholder shapes. Repaint every surface with natural photographic materials and soft daylight. Deliver one edge-to-edge interior photograph without a border, diagram, lettering, picture-in-picture or extra reference objects. ")
        elif anchor:
            prompt=f"Edit image 1, the visual authority for the {room['name']}. Keep its camera viewpoint, background architecture, stair connections, openings, lighting and all objects except the requested furniture changes. Do not blend in a different room or restage the background. "
        else:
            prompt=f"Create a natural architectural photograph of the {room['name']} on {room['floor']}. Image 1 is this room's floor-plan area: use it to guide wall, door and window placement and circulation, but do not render the drawing, labels, symbols or a collage. The room should be physically plausible and connected to the plan. "
        if constraints:
            prompt=constraints+'\nARCHITECTURE REFERENCE: '+prompt
            job['placement_control']={'version':4,'layout':copy.deepcopy(current_layout(room)),'dimensions':room_dimensions(self.store,room),'constraints':constraints,'product_board':packed,'conditioning_image_count':1+(1 if packed else len(refs))+int(bool(guide)),'perspective_guide':bool(perspective),'enforcement':'reference conditioning plus spatial instructions; requires visual review'}
            (folder/'placement-constraints.json').write_text(json.dumps(job['placement_control'],indent=2),encoding='utf8')
        prompt+=p['style']+'\n'+room.get('notes','')+'\n'+'\n'.join(descriptions)+'\nPreserve realistic scale, readable material junctions, neutral colour, natural glass reflections and soft highlight rolloff. No host, people, added text, watermarks, maze-pattern textures, sharpening halos or waxy smoothing.'
        lighting,scene=lighting_instruction(plan)
        if control['mode']!='reference':
            prepared=prepare_edit(control.get('instruction',''),room['name'],control['mode'],[a.get('category','Furniture') for a in refs])
            job['prompt_preparation']=prepared
            (folder/'prepared-edit.json').write_text(json.dumps(prepared,indent=2),encoding='utf8')
            prompt=(prepared['prompt']+'\nPreserve all UNCHANGED objects, background dining table and chairs, stair, openings, rug, joinery and materials. '+
                    ('Preserve the existing scene lighting. ' if control['mode']=='region' else '')+
                    '\n'+room.get('notes','')+'\n'+'\n'.join(descriptions)+
                    '\nPhotographic detail, no extra objects, labels, sharpening or stylization.')
            scene_control.protect_graph(g,control)
        if lighting and control['mode']!='region':
            prompt=prompt.replace('openings, lighting and all objects','openings and all objects')+'\n'+lighting
            job['scene_lighting']=copy.deepcopy(scene)
            (folder/'scene-lighting.json').write_text(json.dumps(scene,indent=2),encoding='utf8')
        from plan_reading import instruction as architectural_instruction
        if perspective:
            from flux_layout_prompt import compile_prompt
            prompt,preparation=compile_prompt(p,room,refs,plan,lighting,packed=packed,projection=perspective[1].get('projected_objects'))
            job['layout_prompt_preparation']=preparation
            (folder/'layout-prompt-preparation.json').write_text(json.dumps(preparation,indent=2),encoding='utf8')
        else:
            prompt+='\n'+architectural_instruction(plan,room)
        if surface_cleanup:
            prompt='Edit image 1. '+control['instruction']+' The edited patch is a continuous clean unmarked surface matching the surrounding material and illumination. Preserve the rest of this photograph exactly.'
            job['surface_cleanup']={'reference_count':1,**scene_control.focus_surface_graph(g,control)}
        g['6']['inputs']['text']=prompt;g['16']['inputs'].update(positive=pos,negative=neg)
        g['17']['inputs']['noise_seed']=p['seed'];g['24']['inputs']['filename_prefix']='Pixeloid_Studio/'+job['id']+'/Image';g['25']['inputs']['filename_prefix']='Pixeloid_Studio/'+job['id']+'/Raw1920x1088'
        job['seed']=p['seed'];job['source_assets']=[a['id'] for a in refs]+([anchor['id']] if anchor else [room['plan_id']])+([room['plan_id']] if guide else []);job['prompt']=prompt
        scene_control.save_manifest(job,folder,scene_control.assert_scene(self.store,p,room,job.get('scene_ticket')),
            model='FLUX.2 Klein 4B',master_image=scene_control.file_identity(self.store,anchor['id']) if anchor else None,
            preservation=control,workflow_sha256=scene_control.digest(g))
        return g,'24'
    def build_video(self,job,folder):
        p=self.store.project(job['project_id']);room=self.store.room(p['id'],job['room_id']);a=approved_image(self.store,p,room)
        if room['revision']!=job['input_revision'] or a['id']!=job['source_image_id']:raise ValueError('Image approval changed while the video was queued. Review and queue it again.')
        scene=scene_control.assert_scene(self.store,p,room,job.get('scene_ticket'))
        source_identity=scene_control.file_identity(self.store,a['id'])
        if job.get('source_image_identity') and source_identity!=job['source_image_identity']:raise ValueError('The approved image changed after the video was queued.')
        g=json.loads((self.app_root/'templates/ltx.json').read_text())
        seconds=job.get('duration',5);frames=int(seconds*24);latent_frames=frames+1
        g['8']['inputs']['image']=self.upload(a['path']);g['11']['inputs']['length']=latent_frames;g['13']['inputs']['frames_number']=latent_frames;g['34']['inputs']['length']=frames;g['15']['inputs']['noise_seed']=p['seed']
        with Image.open(a['path']) as source:
            if source.size!=(1920,1080):raise ValueError('Video needs an approved native 1920 Ã— 1080 image. No source enlargement is performed.')
        g['9']={'class_type':'ImagePadForOutpaint','inputs':{'image':['8',0],'left':0,'right':0,'top':4,'bottom':4,'feathering':0}}
        g['12']['inputs']['strength']=1.0
        if job.get('motion','still')=='still':
            # Anchor the end to the same approved view, then remove appended
            # guide tokens before decoding. Moving-camera shots do not use this.
            g['35']={'class_type':'LTXVAddGuide','inputs':{'positive':['7',0],'negative':['7',1],'vae':['3',0],'latent':['12',0],'image':['10',0],'frame_idx':frames,'strength':1.0}}
            g['14']['inputs']['video_latent']=['35',2]
            g['16']['inputs'].update(positive=['35',0],negative=['35',1])
            g['36']={'class_type':'LTXVCropGuides','inputs':{'positive':['35',0],'negative':['35',1],'latent':['20',0]}}
            g['29']['inputs']['samples']=['36',2]
        motion={'still':'The camera is locked on a tripod. Only subtle natural foliage movement.','push':'A very slow, straight five-centimetre camera push toward the subject. Fixed focal length, level horizon.','slide':'A tiny five-centimetre lateral camera slide, fixed focal length and level horizon.'}.get(job.get('motion'),'The camera is locked on a tripod.')
        source_job=self.store.db['jobs'].get(a.get('job_id'),{})
        saved_camera=copy.deepcopy(source_job.get('scene_manifest',{}).get('content',{}).get('floor_camera'))
        if saved_camera:
            motion+=' Begin at the exact approved camera composition. Keep its lens and viewing direction; do not reframe or cut to a different viewpoint.'
        job['camera_guidance']={'source_image_id':a['id'],'camera':saved_camera,'motion':job.get('motion','still'),'mode':'approved-image conditioning and motion prompt','path_enforced':False}
        prompt=f"{seconds}-second natural architectural film of this exact approved {room['name']} image. {motion} Preserve every object, furniture silhouette, background, wall and door frame. Exposure and daylight direction stay constant. No extra glass panels or new openings. All furniture and stone geometry remain rigid. Keep reflections physically plausible and restrained; no texture crawling, jitter, morphing or lighting transitions. No people, speech, music, text or watermark."
        g['5']['inputs']['text']=prompt;g['32']['inputs']['filename_prefix']='Pixeloid_Studio/'+job['id']+'/Video'
        source_job=self.store.db['jobs'].get(a.get('job_id'),{})
        if source_job.get('scene_manifest'):scene_control.assert_scene(self.store,p,room,source_job['scene_manifest'])
        if source_job.get('scene_lighting'):job['scene_lighting']=copy.deepcopy(source_job['scene_lighting'])
        job['seed']=p['seed'];job['source_assets']=[a['id']];job['prompt']=prompt
        scene_control.save_manifest(job,folder,scene,model='LTX 2.5',approved_image=source_identity,
            camera_guidance=copy.deepcopy(job['camera_guidance']),
            parent_image_scene=copy.deepcopy(source_job.get('scene_manifest')),workflow_sha256=scene_control.digest(g),
            preservation={'first_frame_strength':1.0,'end_frame_guidance':job.get('motion','still')=='still','source_resize':False,'motion':job.get('motion','still'),
                          'scope':'Exact approved input; subsequent generated frames require full motion review.'})
        return g,'32'
    def build_reference(self,job,folder):
        p=self.store.project(job['project_id']);room=self.store.room(p['id'],job['room_id'])
        g=json.loads((self.app_root/'templates/flux.json').read_text())
        for key in ['5','8','9','11','14','15']:g.pop(key,None)
        anchor_id=job.get('reference_anchor_id');sources=[]
        if anchor_id:
            anchor=self.store.asset(anchor_id)
            if anchor.get('project_id')!=p['id'] or anchor.get('room_id')!=room['id']:raise ValueError('Room reference does not belong to this section.')
            g['4']['inputs']['image']=self.upload(anchor['path']);g['10']['inputs']['pixels']=['4',0]
            pos,neg=['12',0],['13',0];sources=[anchor_id]
            prefix='Edit image 1 according to the following request. Preserve the room architecture, viewpoint, background, door and stair connections and unchanged objects. '
        else:
            for key in ['4','10','12','13']:g.pop(key,None)
            pos,neg=['6',0],['7',0]
            prefix=('Create a photographic furniture or material reference. Show one coherent product or material study with realistic construction, scale, fine material detail, natural lighting and a quiet neutral background. ' if job['reference_purpose']=='product' else 'Create a realistic architectural room reference photograph. '+p['style']+' ')
        prompt=prefix+job['reference_prompt']+'\nNatural photographic materials, realistic glass reflections and soft highlight rolloff. No people, watermark, text, collage, embossed maze textures, exaggerated sharpening or waxy smoothing.'
        g['6']['inputs']['text']=prompt;g['16']['inputs'].update(positive=pos,negative=neg);g['17']['inputs']['noise_seed']=p['seed']
        g['24']['inputs']['filename_prefix']='Pixeloid_Studio/'+job['id']+'/Reference';g['25']['inputs']['filename_prefix']='Pixeloid_Studio/'+job['id']+'/Raw1920x1088'
        job['seed']=p['seed'];job['source_assets']=sources;job['prompt']=prompt
        return g,'24'
    def validate_graph(self,g):
        specs=self.get('/object_info')
        for key,n in g.items():
            if n['class_type'] not in specs:raise RuntimeError('ComfyUI is missing required node: '+n['class_type'])
            spec=specs[n['class_type']]
            for req in spec['input'].get('required',{}):
                if req not in n['inputs']:raise RuntimeError(f'Missing workflow input {key}.{req}')
    def run_render(self,job):
        jid=job['id'];folder=project_storage.job_folder(self.store,job);folder.mkdir(parents=True,exist_ok=True)
        graph_path=folder/'workflow.api.json'
        if not self.ensure_renderer(job):return
        if not job.get('prompt_id'):
            # Never submit into another application's active queue.
            while True:
                if self.store.db['jobs'][jid]['status']=='cancelled':return
                q=self.get('/queue');ram,commit=memory_headroom();vram=available_vram()
                if not q['queue_running'] and not q['queue_pending'] and ram>=12 and commit>=20 and (vram is None or vram>=2):break
                stage='Waiting for the shared renderer' if q['queue_running'] or q['queue_pending'] else 'Waiting for available memory'
                self.store.update_job(jid,status='waiting',stage=stage,progress=None);self.stop.wait(3)
                if self.stop.is_set():return
            if job.get('submission_intent'):raise RuntimeError('A previous submission did not acknowledge its job ID. Use Recover in Activity to reconcile local history; no duplicate was submitted.')
            self.store.update_job(jid,status='running',stage='Preparing references',progress=None,started=job.get('started') or now())
            g,node=({'image':self.build_image,'reference':self.build_reference,'video':self.build_video}[job['kind']])(job,folder)
            self.validate_graph(g);graph_path.write_text(json.dumps(g,indent=2),encoding='utf8');(folder/'prompt.txt').write_text(job['prompt'],encoding='utf8')
            job['output_node']=node;job['submission_intent']=now();job.update(render_progress.initialize(job,g,list(self.store.db['jobs'].values())));self.store.save()
            # Connect first so fast/cached nodes do not outrun progress collection.
            ws=self.connect_events(jid)
            response=self.post('/prompt',{'prompt':g,'client_id':jid,'extra_data':{'pixeloid_job_id':jid}})
            if response.get('node_errors'):raise RuntimeError('Workflow validation failed: '+str(response['node_errors'])[:600])
            self.store.update_job(jid,prompt_id=response['prompt_id'],stage='Loading models')
        else:
            g=json.loads(graph_path.read_text());node=job['output_node'];ws=self.connect_events(jid)
        pid=job['prompt_id'];start=time.time();last_poll=0
        try:
            while not self.stop.is_set():
                if self.store.db['jobs'][jid]['status']=='cancelled':return
                if ws:
                    try:
                        raw=ws.recv()
                        if isinstance(raw,str):self.event(job,json.loads(raw),g)
                    except Exception:pass
                else:self.stop.wait(1)
                if time.time()-last_poll<1:continue
                last_poll=time.time();h=self.get('/history/'+pid).get(pid)
                if h:
                    (folder/'history.json').write_text(json.dumps(h,indent=2),encoding='utf8')
                    if h['status']['status_str']!='success':raise RuntimeError('ComfyUI could not complete this render. '+str(h['status'].get('messages',[])[-1:])[:500])
                    if self.store.db['jobs'][jid]['status']=='cancelled':return
                    self.finish_render(job,h,folder);return
                q=self.get('/queue')
                present=any(x[1]==pid for x in q['queue_running']+q['queue_pending'])
                if not present and time.time()-start>20:raise RuntimeError('Saved render is absent from queue and history. Inspect the engine before retrying; it was not resubmitted.')
        finally:
            if ws:
                try:ws.close()
                except Exception:pass
    def ensure_renderer(self,job):
        """Start an installed service once; keep readiness and cancellation in the job."""
        if self.health(force=True).get('connected'):return True
        from standalone import start_renderer,config
        if not config(self.app_root).get('auto_start_renderer'):
            raise ValueError('Local renderer is offline. Open Setup and connect installed components, then retry this activity.')
        self.store.update_job(job['id'],status='waiting',stage='Starting local renderer',progress=None)
        start_renderer(self,self.app_root)
        deadline=time.monotonic()+180
        while time.monotonic()<deadline:
            if self.stop.is_set() or self.store.db['jobs'][job['id']]['status']=='cancelled':return False
            if self.health(force=True).get('connected'):return True
            self.stop.wait(2)
        raise ValueError('The local renderer did not become ready within 3 minutes. Open Setup to check its status, then retry. No render was submitted.')
    def connect_events(self,jid):
        try:
            import websocket
            return websocket.create_connection(self.url.replace('http://','ws://')+'/ws?clientId='+jid,timeout=1,http_proxy_host=None)
        except Exception:return None
    def event(self,job,event,g):
        fields=render_progress.event_fields(job,event,g,now())
        if fields:self.store.update_job(job['id'],**fields)
    def finish_render(self,job,history,folder):
        # Keep the last measured bar position while output validation runs.
        self.store.update_job(job['id'],stage='Saving and checking output')
        outputs=history['outputs'].get(job['output_node'],{})
        entries=outputs.get('images') or outputs.get('videos') or outputs.get('gifs') or []
        if not entries:raise RuntimeError('Renderer finished but returned no media output.')
        is_image=job['kind'] in ('image','reference')
        entry=entries[0];ext='.png' if is_image else '.mp4';path=project_storage.output_folder(self.store,job,folder)/('result'+ext)
        response=self.session.get(self.url+'/view',params=entry,timeout=180);response.raise_for_status();path.write_bytes(response.content)
        p=self.store.project(job['project_id']);room=self.store.room(p['id'],job['room_id'])
        if job['kind']!='reference' and room['revision']!=job['input_revision']:raise RuntimeError('Output was preserved, but room references changed during rendering. It cannot be approved as current.')
        if job['kind']=='video':
            current=approved_image(self.store,p,room)
            if current['id']!=job['source_image_id']:raise RuntimeError('Output preserved; its source approval changed during rendering.')
            from video_checks import inspect
            job['video_check']=inspect(path,current['path'],job['duration'])
            (folder/'video-check.json').write_text(json.dumps(job['video_check'],indent=2),encoding='utf8')
            import av
            with av.open(str(path)) as container:
                stream=container.streams.video[0]
                if (stream.width,stream.height)!=(1920,1080):raise RuntimeError('Video output is not 1920x1080; preserved for inspection.')
                if stream.average_rate and abs(float(stream.average_rate)-24)>.01:raise RuntimeError('Video frame rate does not match 24 fps.')
                duration=float(stream.duration*stream.time_base) if stream.duration else float(container.duration/1000000)
                if abs(duration-job['duration'])>.1:raise RuntimeError('Video duration does not match the requested length.')
        if is_image:
            with Image.open(path) as im:
                if im.size!=(1920,1080):raise RuntimeError('Output is not 1920x1080; it was preserved for inspection.')
            raw=history['outputs'].get('25',{}).get('images',[])
            if raw:
                response=self.session.get(self.url+'/view',params=raw[0],timeout=180);response.raise_for_status();(folder/'raw_1920x1088.png').write_bytes(response.content)
        if job.get('scene_manifest'):
            scene_control.assert_scene(self.store,p,room,job['scene_manifest'])
            control=job['scene_manifest'].get('preservation',{})
            if is_image and control.get('mode')=='region':
                qa=scene_control.check_protected_output(self.store.asset(control['source_id'])['path'],path,control)
                job['consistency_check']=qa
                (folder/'consistency-check.json').write_text(json.dumps(qa,indent=2),encoding='utf8')
                if not qa['outside_exact_match']:raise RuntimeError('The protected background pixel check failed. Output preserved for inspection; it cannot be approved.')
        (folder/'resolution-provenance.json').write_text(json.dumps({'sampling_width':1920,'sampling_height':1088,'output_width':1920,'output_height':1080,'crop_top':4,'crop_bottom':4,'output_upscaler':False,'source_conditioning_may_be_resized':True,'workflow':'workflow.api.json','seed':job['seed']},indent=2),encoding='utf8')
        a=register_asset(self.store,p['id'],path,'reference_candidate' if job['kind']=='reference' else job['kind'],room['id'],input_revision=job['input_revision'],job_id=job['id'],seed=job['seed'],status='review',source_image_id=job.get('source_image_id'),native_sampling=[1920,1088],output_upscaled=False,duration=job.get('duration'),reference_purpose=job.get('reference_purpose'),reference_prompt=job.get('reference_prompt'),reference_anchor_id=job.get('reference_anchor_id'),category=job.get('category','Furniture'))
        with self.store.lock:
            room.setdefault('reference_candidates' if job['kind']=='reference' else 'images' if job['kind']=='image' else 'videos',[]).append(a['id']);self.store.save()
        self.store.update_job(job['id'],status='completed',stage='Ready for review',progress=100,eta=None,result_asset_id=a['id'],finished=now())
    def run_analysis(self,job):
        from analysis import analyze_local,analyze_vision
        p=self.store.project(job['project_id']);plan_ids=list(job['plan_ids']);combined=[];warnings=[];engines=[]
        self.store.update_job(job['id'],status='running',stage='Reading floor plan',progress=None)
        def progress(stage,value):self.store.update_job(job['id'],stage=stage,progress=value)
        for i,aid in enumerate(plan_ids):
            a=self.store.asset(aid);folder=project_storage.analysis_folder(self.store,p['id'],job['id'],aid);folder.mkdir(parents=True,exist_ok=True)
            if self.store.db['settings'].get('vision_model'):result=analyze_vision(a['path'],aid,self.store.db['settings'],progress)
            else:result=analyze_local(a['path'],aid,folder,progress)
            combined+=result['rooms'];warnings+=result.get('warnings',[]);engines.append(result['engine']);progress(f'Read {i+1} of {len(plan_ids)} plan pages',round(100*(i+1)/len(plan_ids)))
        with self.store.lock:
            if p['map_revision']!=job['input_revision']:raise ValueError('The room map changed while analysis was running. Results were not applied; analyze again when ready.')
            # Preserve user edits: analysis is only allowed on an empty map.
            if p['rooms']:raise ValueError('Rooms already exist. Create another project to analyze a replacement plan without losing your work.')
            for row in combined:
                r=self.store.add_room(p['id'],row['name'],row['floor'],row['plan_id'],row.get('bbox'),row.get('kind','room'),confidence=row.get('confidence','medium'),detection_note=row.get('detection_note','Review this proposal.'))
            p['analysis']={'engine':', '.join(sorted(set(engines))),'warnings':list(dict.fromkeys(warnings)),'label_count':len(combined),'reviewed':False};self.store.save()
        self.store.update_job(job['id'],status='completed',stage=f'{len(combined)} suggested sections Â· review required',progress=100,finished=now())
    def worker(self):
        # One bounded CPU lane and one existing model-owning lane. Re-entering
        # startup must not create additional GPU owners.
        with self._worker_guard:
            if self._worker_started:return
            self._worker_started=True
        cpu=threading.Thread(target=self._worker_lane,args=(True,),daemon=True,name='plan-cpu')
        cpu.start()
        try:self._worker_lane(False)
        finally:self.stop.set();cpu.join(6)

    def _worker_lane(self,cpu):
        while not self.stop.is_set():
            with self.store.lock:
                candidates=sorted([j for j in self.store.db['jobs'].values() if j['status'] in ('queued','waiting','running') and (j['kind'] in ('raster_reconstruction','plan_setup'))==cpu],key=lambda j:j['created'])
            if not candidates:self.stop.wait(1);continue
            if cpu and memory_headroom()[0]<2:self.stop.wait(1);continue
            job=candidates[0]
            with self.store.lock:
                job=self.store.db['jobs'][job['id']]
                if job['status'] not in ('queued','waiting','running'):continue
                first=job.get('first_dispatch_at',time.time())
                self.store.update_job(job['id'],status='running',lane='cpu' if cpu else 'model',first_dispatch_at=first,queue_wait_seconds=round(first-job['created'],3))
            try:
                if job['kind']=='plan_setup':
                    import plan_setup
                    plan_setup.run(self,job)
                elif job['kind']=='vision_study':
                    import vision_study
                    vision_study.run(self,job)
                elif job['kind']=='raster_reconstruction':
                    import raster_reconstruction
                    raster_reconstruction.run(self,job)
                elif job['kind']=='component_download':
                    import component_setup
                    component_setup.run(self,job)
                elif job['kind']=='analysis':self.run_analysis(job)
                else:self.run_render(job)
            except Exception as exc:self.store.update_job(job['id'],status='failed',stage='Needs attention',error=str(exc)[:900],eta=None,finished=now())
            if self.store.db['settings'].get('auto_release') and job['kind'] in ('image','video','reference'):
                try:
                    q=self.get('/queue')
                    if not q['queue_running'] and not q['queue_pending']:self.post('/free',{'unload_models':True,'free_memory':True})
                except Exception:pass
