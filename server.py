"""Pixeloid Studio: loopback-only HTTP app and persistent rendering queue."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/'vendor'))
import argparse, json, mimetypes, os, re, threading, time, traceback, io
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse,parse_qs,unquote
from PIL import Image, ImageOps
from store import Store, uid, now, assert_image_gate, approved_image
from engine import Engine, register_asset, local_url

import project_storage
from placement_map import validate_layout, current_layout
from plan_preview import ensure_preview
from plan_area import save_measurement, polygon, summarize, exclusions
from drawing_editor import get_document, save_document
from scene_sun import clean_site, solar_summary
import scene_control
from prompt_compiler import prepare_edit
import standalone
import products
import local_area
import plan_reading
import plan_setup
import plan_import
import plan_preflight
import plan_health
import shared_floor
import vision_study
import furniture_blocks
import maps_location
from web_image import fetch_public_image

MAX_UPLOAD=32*1024*1024
Image.MAX_IMAGE_PIXELS=45000000
ACTIVE=('queued','waiting','running')

def bbox(value):
    if value is None:return None
    if not isinstance(value,list) or len(value)!=4 or not all(isinstance(x,(int,float)) for x in value):raise ValueError('Select a rectangular room area.')
    x,y,w,h=map(float,value)
    if not all(0<=v<=1 for v in (x,y,w,h)) or w<.005 or h<.005 or x+w>1.001 or y+h>1.001:raise ValueError('Room area must fit inside the floor plan.')
    return [x,y,min(w,1-x),min(h,1-y)]

def public_state(store,engine):
    d=store.snapshot()
    for a in d['assets'].values():a.pop('path',None);a['url']='/media/'+a['id']
    for j in d['jobs'].values():j.pop('prompt',None)
    d['engine']=engine.health();d['storage']={'default_parent':str((store.root/'projects').resolve()),'errors':store.storage_errors.copy()};return d

class Handler(BaseHTTPRequestHandler):
    server_version='PixeloidStudio/1.0'
    def log_message(self,fmt,*args):
        if self.path not in ('/api/state','/api/health'):print(time.strftime('%H:%M:%S'),fmt%args,flush=True)
    @property
    def store(self):return self.server.store
    def reply(self,data,status=200):
        raw=json.dumps(data).encode();self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
    def origin_check(self):
        expected={'127.0.0.1:'+str(self.server.server_port),'localhost:'+str(self.server.server_port)}
        if self.headers.get('Host') not in expected:raise PermissionError('Open the dashboard from its local address.')
        origin=self.headers.get('Origin')
        if origin and origin not in {'http://'+h for h in expected}:raise PermissionError('This request did not come from the local dashboard.')
        if self.headers.get('Sec-Fetch-Site')=='cross-site':raise PermissionError('Cross-site requests are not allowed.')
    def body(self):
        if not self.headers.get('Content-Type','').startswith('application/json'):raise ValueError('Expected JSON request.')
        n=int(self.headers.get('Content-Length','0'))
        if n>1000000:raise ValueError('Request is too large.')
        d=json.loads(self.rfile.read(n) or b'{}')
        if not isinstance(d,dict):raise ValueError('Expected a JSON object.')
        return d
    def do_GET(self):
        try:
            self.origin_check();path=urlparse(self.path).path
            if path=='/api/state':return self.reply(public_state(self.store,self.server.engine))
            if path=='/api/health':return self.reply(self.server.engine.health())
            if path=='/api/identity':return self.reply({'app':'Pixeloid Studio','root':str(ROOT),'pid':os.getpid(),'standalone':True})
            if path=='/api/system-status':return self.reply(standalone.diagnostics(self.store,self.server.engine))
            if path=='/api/local-setup':
                import local_setup
                return self.reply(local_setup.status(self.server.engine))
            if path.startswith('/product-photo/'):return self.send_file(products.thumbnail(path.split('/')[-1],int(parse_qs(urlparse(self.path).query).get('image',['0'])[0])))
            structure=re.fullmatch(r'/api/projects/([a-zA-Z0-9]+)/plans/([a-zA-Z0-9]+)/(structure|shared-scene|scene-document|model\.glb|raster-draft)',path)
            if structure:
                with self.store.lock:
                    pid,aid,kind=structure.groups()
                    if kind=='structure':return self.reply(plan_health.inspect(self.store,pid,aid))
                    if kind=='raster-draft':
                        from raster_reconstruction import draft
                        return self.reply(draft(self.store,pid,aid))
                    if kind=='scene-document':
                        from scene_document import from_plan
                        from drawing_scene import load
                        p=self.store.project(pid)
                        if aid not in p['floor_plans']:raise ValueError('Plan does not belong to project.')
                        plan=self.store.asset(aid);architecture,_=load(self.store,plan)
                        return self.reply(from_plan(plan,[r for r in p['rooms'] if r['plan_id']==aid],architecture))
                    room_id=parse_qs(urlparse(self.path).query).get('room_id',[''])[0]
                    if kind=='model.glb' and (self.store.asset(aid).get('raster_geometry') or not room_id):
                        from raster_reconstruction import draft
                        from model_export import glb
                        raw=glb(draft(self.store,pid,aid));self.send_response(200);self.send_header('Content-Type','model/gltf-binary');self.send_header('Content-Length',str(len(raw)));self.send_header('Content-Disposition','attachment; filename=Pixeloid-partial-draft.glb');self.end_headers();self.wfile.write(raw);return
                    room=self.store.room(pid,room_id)
                    if room.get('plan_id')!=aid:raise ValueError('Choose a section on this plan.')
                    scene=shared_floor.build(self.store,room);scene['issues']=shared_floor.readiness(self.store,room)
                    if kind=='model.glb':
                        from model_export import glb
                        raw=glb(scene);self.send_response(200);self.send_header('Content-Type','model/gltf-binary');self.send_header('Content-Length',str(len(raw)));self.send_header('Content-Disposition','attachment; filename=Pixeloid-draft.glb');self.end_headers();self.wfile.write(raw);return
                    return self.reply(scene)
            drawing=re.fullmatch(r'/api/projects/([a-zA-Z0-9]+)/plans/([a-zA-Z0-9]+)/drawing',path)
            if drawing:
                with self.store.lock:return self.reply(get_document(self.store,drawing[1],drawing[2]))
            reading=re.fullmatch(r'/api/projects/([a-zA-Z0-9]+)/plans/([a-zA-Z0-9]+)/reading',path)
            if reading:
                with self.store.lock:return self.reply(plan_reading.get_reading(self.store,reading[1],reading[2]))
            match=re.fullmatch(r'/api/projects/([a-zA-Z0-9]+)/storage',path)
            if match:return self.reply(project_storage.describe(self.store,match[1]))
            match=re.fullmatch(r'/api/projects/([a-zA-Z0-9]+)/rooms/([a-zA-Z0-9]+)/local-area',path)
            if match:return self.reply(local_area.for_room(self.store,self.store.room(match[1],match[2])))
            match=re.fullmatch(r'/api/projects/([a-zA-Z0-9]+)/rooms/([a-zA-Z0-9]+)/preflight',path)
            if match:
                with self.store.lock:return self.reply(plan_preflight.report(self.store,self.store.project(match[1]),self.store.room(match[1],match[2])))
            if path.startswith('/media/'):
                a=self.store.asset(path.split('/')[-1]);return self.send_file(Path(a['path']))
            if path.startswith('/api/'):return self.reply({'error':'Not found'},404)
            file=(ROOT/'static'/('index.html' if path=='/' else unquote(path).lstrip('/'))).resolve()
            if not file.is_relative_to((ROOT/'static').resolve()):raise PermissionError('Invalid file path.')
            self.send_file(file)
        except (ValueError,FileNotFoundError):self.reply({'error':'Not found'},404)
        except PermissionError as e:self.reply({'error':str(e)},403)
        except (BrokenPipeError,ConnectionResetError,ConnectionAbortedError):pass
    def send_file(self,path):
        if not path.is_file():raise FileNotFoundError()
        size=path.stat().st_size;start=0;end=size-1;status=200
        r=self.headers.get('Range')
        if r:
            m=re.fullmatch(r'bytes=(\d*)-(\d*)',r)
            if not m or not any(m.groups()):self.send_error(416);return
            if m[1]:start=int(m[1]);end=int(m[2]) if m[2] else end
            else:start=max(0,size-int(m[2]))
            if start>=size or start>end:self.send_response(416);self.send_header('Content-Range',f'bytes */{size}');self.end_headers();return
            end=min(end,size-1);status=206
        self.send_response(status);self.send_header('Content-Type',mimetypes.guess_type(path.name)[0] or 'application/octet-stream');self.send_header('X-Content-Type-Options','nosniff');self.send_header('Accept-Ranges','bytes');self.send_header('Cache-Control','no-cache')
        self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' blob: data:; media-src 'self' blob:; connect-src 'self'; frame-ancestors 'none'")
        if status==206:self.send_header('Content-Range',f'bytes {start}-{end}/{size}')
        self.send_header('Content-Length',str(end-start+1));self.end_headers()
        with path.open('rb') as f:
            f.seek(start);remaining=end-start+1
            while remaining:
                chunk=f.read(min(1024*1024,remaining))
                if not chunk:break
                self.wfile.write(chunk);remaining-=len(chunk)
    def do_POST(self):self.mutate('POST')
    def do_PATCH(self):self.mutate('PATCH')
    def do_DELETE(self):self.mutate('DELETE')
    def mutate(self,method):
        try:
            self.origin_check();u=urlparse(self.path);parts=u.path.strip('/').split('/')
            if len(parts)==4 and parts[:2]==['api','projects'] and parts[3]=='upload' and method=='POST':
                with self.store.lock:return self.reply(self.upload(parts[2],parse_qs(u.query)))
            d=self.body()
            if parts==['api','renderer','start'] and method=='POST':return self.reply(standalone.start_renderer(self.server.engine))
            if parts==['api','products','search'] and method=='POST':
                with self.store.lock:
                    p=self.store.project(d.get('project_id'));r=self.store.room(p['id'],d.get('room_id'));context=p.get('style','')+' '+r.get('notes','')
                    area=local_area.for_room(self.store,r)
                result=products.search(d.get('query',''),d.get('market','IN'),context,area);result['local_area']=area
                return self.reply(result)
            if parts==['api','products','lookup'] and method=='POST':return self.reply(products.lookup(d.get('url','')))
            if parts==['api','products','inspect'] and method=='POST':return self.reply(products.lookup(d.get('url',''),require_offer=False))
            if len(parts)==6 and parts[:2]==['api','projects'] and parts[3]=='rooms' and parts[5]=='add-product' and method=='POST':
                product=products.get_product(d.get('product_id',''))
                result=self.import_image(parts[2],{'kind':'reference','room_id':parts[4],'url':products.product_image(product,d.get('image_index',0))})
                with self.store.lock:
                    for item in result['assets']:
                        a=self.store.asset(item['id']);a['category']=product['title'][:100];a['display_name']=product['title'];a['source_product']=product
                    self.store.save()
                return self.reply(result)
            if len(parts)==4 and parts[:2]==['api','projects'] and parts[3]=='import-image' and method=='POST':return self.reply(self.import_image(parts[2],d))
            if parts==['api','choose-folder'] and method=='POST':return self.reply(project_storage.choose_folder(d.get('initial','')))
            if len(parts)==4 and parts[:2]==['api','projects'] and parts[3]=='storage' and method=='POST':return self.reply(project_storage.relocate(self.store,parts[2],d.get('parent','')))
            with self.store.lock:result=self.route(method,parts,d)
            self.reply(result)
        except PermissionError as e:self.reply({'error':str(e)},403)
        except (ValueError,KeyError,TypeError) as e:self.reply({'error':str(e)},400)
        except Exception as e:traceback.print_exc();self.reply({'error':'Could not complete this activity: '+str(e)},500)
    def route(self,method,s,d):
        st=self.store
        if s==['api','projects'] and method=='POST':return st.create_project(str(d.get('name','New project')),d.get('save_parent'))
        if s==['api','local-setup','connect']:
            import local_setup
            return local_setup.connect(self.server.engine,d)
        if s==['api','local-setup','start-reader']:
            import local_setup
            return local_setup.start_vision(self.server.engine)
        if s==['api','local-setup','download']:
            import component_setup
            return component_setup.queue(self.server.engine,d.get('project_id'),d)
        if s==['api','settings'] and method=='PATCH':
            if any(j['status'] in ACTIVE for j in st.db['jobs'].values()):raise ValueError('Finish or cancel queued activities before changing engine settings.')
            for k in ['comfy_url','vision_url']:
                if k in d:st.db['settings'][k]=local_url(str(d[k]))
            for k in ['vision_model','auto_release']:
                if k in d:st.db['settings'][k]=str(d[k])[:100] if k=='vision_model' else bool(d[k])
            st.save();return {'ok':True}
        if len(s)==4 and s[:2]==['api','jobs'] and s[3]=='cancel':
            from job_control import cancel
            return cancel(self.server.engine,st.db['jobs'][s[2]])
        if len(s)==4 and s[:2]==['api','jobs'] and s[3]=='recover':
            from job_control import recover
            return recover(self.server.engine,st.db['jobs'][s[2]])
        if s==['api','location-from-map'] and method=='POST':return maps_location.resolve(d.get('url',''))
        if len(s)==6 and s[:2]==['api','projects'] and s[3]=='plans' and s[5]=='review-decision':
            from detection_review import save_decision
            return save_decision(st,s[2],s[4],d)
        if len(s)==6 and s[:2]==['api','projects'] and s[3]=='plans' and s[5]=='raster-correction':
            from raster_reconstruction import correct
            return correct(st,s[2],s[4],d)
        if len(s)==6 and s[:2]==['api','projects'] and s[3]=='plans' and s[5]=='reconstruct':
            if s[4] not in st.project(s[2])['floor_plans']:raise ValueError('Choose this project’s plan.')
            return st.new_job(s[2],'raster_reconstruction',plan_id=s[4])
        if len(s)<3 or s[:2]!=['api','projects']:raise ValueError('Unknown action.')
        p=st.project(s[2]);pid=p['id']
        if pid in st.moving_projects:raise ValueError('This project is being copied. Wait until its new folder is ready.')
        if len(s)==6 and s[3]=='rooms' and s[5]=='blocks' and method=='POST':
            return furniture_blocks.request(st,pid,s[4],d)
        if len(s)==6 and s[3]=='plans' and s[5] in ('read-visual','import-visual') and method=='POST':
            if s[4] not in p['floor_plans']:raise ValueError('Choose a plan from this project.')
            if s[5]=='import-visual':return vision_study.import_proposals(st,pid,s[4],d)
            ids=d.get('section_ids',[])
            if not isinstance(ids,list) or len(ids)>100 or any(not any(r['id']==i and r['plan_id']==s[4] and r.get('bbox') for r in p['rooms']) for i in ids):raise ValueError('Choose selected sections from this full plan (up to 100).')
            if not st.asset(s[4]).get('plan_source',{}).get('vector'):st.new_job(pid,'raster_reconstruction',plan_id=s[4])
            return st.new_job(pid,'vision_study',plan_id=s[4],section_ids=ids,input_revision=p['map_revision'],study_revision=st.asset(s[4]).get('plan_reading',{}).get('revision',0))
        if len(s)==6 and s[3]=='plans' and s[5] in ('repair-structure','undo-structure','floor-camera','camera-preview') and method=='POST':
            if s[5]=='camera-preview':return shared_floor.preview_camera(st,pid,s[4],d)
            if s[5]=='floor-camera':return shared_floor.save_camera(st,pid,s[4],d)
            return (plan_health.apply if s[5]=='repair-structure' else plan_health.undo)(st,pid,s[4],d.get('fingerprint'))
        if len(s)==6 and s[3]=='plans' and s[5] in ('reading','study','study-section') and method=='POST':
            if s[5]=='study-section':return plan_reading.make_section(st,pid,s[4],d)
            return (plan_reading.study if s[5]=='study' else plan_reading.save_reading)(st,pid,s[4],d)
        if len(s)==6 and s[3]=='plans' and s[5] in ('drawing','sun-preview') and method=='POST':
            if s[4] not in p['floor_plans']:raise ValueError('Choose a plan from this project.')
            if s[5]=='drawing':return save_document(st,pid,s[4],d)
            site=clean_site(d.get('site',{}));return {'solar':solar_summary(site),'site':site}
        if len(s)==6 and s[3]=='plans' and s[5] in ('area-preview','area') and method=='POST':
            if s[4] not in p['floor_plans']:raise ValueError('Choose a floor plan from this project.')
            if s[5]=='area':return save_measurement(st,pid,s[4],d)
            rows=d.get('sections',[])
            if not isinstance(rows,list) or len(rows)>60:raise ValueError('Use up to 60 sections per floor.')
            polys=[polygon(row['polygon']) for row in rows]
            if sum(map(len,polys))>1200:raise ValueError('Simplify outlines to fewer corners.')
            a=st.asset(s[4])
            return summarize(polygon(d.get('outline')),polys,d.get('scale',{}),a['width'],a['height'],exclusions(d))
        if len(s)==6 and s[3]=='plans' and s[5]=='enhance' and method=='POST':
            if s[4] not in p['floor_plans']:raise ValueError('Choose a floor plan from this project.')
            a=ensure_preview(st,st.asset(s[4]));return {'asset_id':a['id']}
        if len(s)==3 and method=='PATCH':
            if 'name' in d:p['name']=str(d['name'])[:100]
            changed=any(k in d and d[k]!=p[k] for k in ['style','seed'])
            if 'seed' in d:
                seed=int(d['seed'])
                if not 0<=seed<=2**53-1:raise ValueError('Seed must be a non-negative integer below 2^53.')
                p['seed']=seed
            if 'style' in d:p['style']=str(d['style'])[:6000]
            if changed:
                for r in p['rooms']:st.invalidate(pid,r)
            st.save();return p
        if len(s)==4 and s[3]=='analyze':
            if not p['floor_plans']:raise ValueError('Upload a floor plan first.')
            if any(j['project_id']==pid and j['kind']=='plan_setup' and j['status'] in ACTIVE for j in st.db['jobs'].values()):raise ValueError('Automatic plan setup is already reading the uploaded pages.')
            if p['rooms']:raise ValueError('Your room map already contains edits. Create a new project to analyze another floor plan.')
            return st.new_job(pid,'analysis',plan_ids=p['floor_plans'][:],input_revision=p['map_revision'])
        if len(s)==4 and s[3]=='confirm-map':
            if not p['rooms']:raise ValueError('Add at least one room or section.')
            plan_reading.assert_reviewed(st,p)
            for r in p['rooms']:
                if not r['name'].strip() or not r['floor'].strip() or r['floor']=='Needs floor assignment':raise ValueError('Give every section a name and a floor before confirming.')
                if not r.get('bbox') and not r.get('anchor_id'):raise ValueError('Mark each section on the plan or upload its room reference before confirming.')
            p['map_confirmed']=True;p.setdefault('analysis',{})['reviewed']=True;st.save();return p
        if len(s)==4 and s[3]=='rooms' and method=='POST':
            plan_id=d.get('plan_id') or (p['floor_plans'][0] if p['floor_plans'] else None)
            if plan_id and plan_id not in p['floor_plans']:raise ValueError('Choose a floor plan from this project.')
            return st.add_room(pid,str(d.get('name','New section')),str(d.get('floor','Ground floor')),plan_id,bbox(d.get('bbox')),d.get('kind','room') if d.get('kind') in ['room','outdoor','circulation'] else 'room')
        if len(s)<5 or s[3]!='rooms':raise ValueError('Unknown project action.')
        r=st.room(pid,s[4])
        if len(s)==5 and method=='DELETE':
            if any(j.get('room_id')==r['id'] and j['status'] in ACTIVE for j in st.db['jobs'].values()):raise ValueError('Finish this room’s activity before removing it.')
            p['rooms'].remove(r);p['map_confirmed']=False;p['map_revision']+=1;st.save();return {'ok':True}
        if len(s)==5 and method=='PATCH':
            changed=False;map_change=False
            for k in ['name','floor','kind','notes','bbox','plan_id']:
                if k not in d:continue
                v=bbox(d[k]) if k=='bbox' else str(d[k])[:6000 if k=='notes' else 100]
                if k=='plan_id' and v not in p['floor_plans']:raise ValueError('Choose a floor plan from this project.')
                if k=='kind' and v not in ['room','outdoor','circulation']:raise ValueError('Unknown section type.')
                if v!=r[k]:r[k]=v;changed=True;map_change|=k!='notes'
            if changed:st.invalidate(pid,r)
            if map_change:p['map_confirmed']=False;p['map_revision']+=1
            st.save();return r
        if len(s)!=6:raise ValueError('Unknown room action.')
        action=s[5]
        if action=='prepare-edit' and method=='POST':
            mode=d.get('mode','region')
            if mode not in ('region','structure','reference'):raise ValueError('Choose an edit mode.')
            products=[st.asset(a).get('category','Furniture') for a in r['references'] if st.asset(a).get('enabled',True)]
            return prepare_edit(d.get('instruction',''),r['name'],mode,products)
        if action=='scene-control' and method=='POST':
            if any(j.get('room_id')==r['id'] and j['status'] in ACTIVE for j in st.db['jobs'].values()):raise ValueError('Finish this room’s current generation before changing consistency controls.')
            if d.get('revision')!=r['revision']:raise ValueError('This room changed. Reopen consistency controls before saving.')
            control=scene_control.clean_control(st,p,r,d)
            if control!=r.get('scene_control',{'mode':'reference'}):
                r['scene_control']=control;st.invalidate(pid,r);st.save()
            return r
        if action=='placement-map' and method=='POST':
            if any(j.get('room_id')==r['id'] and j['status'] in ACTIVE for j in st.db['jobs'].values()):raise ValueError('Finish this room’s generation before changing its furniture map.')
            layout=validate_layout(r,d)
            if not layout['items'] and not r.get('furniture_layout',{}).get('items'):return r
            if layout!=r.get('furniture_layout'):
                r['furniture_layout']=layout;st.invalidate(pid,r);st.save()
            return r
        if action=='generate-reference':
            prompt=str(d.get('prompt','')).strip();purpose=d.get('purpose','product')
            if not 8<=len(prompt)<=6000:raise ValueError('Describe the reference in at least eight characters (up to 6,000).')
            if purpose not in ('product','environment'):raise ValueError('Choose furniture or room environment.')
            anchor=r.get('anchor_id') if d.get('use_environment') else None
            if d.get('use_environment') and not anchor:raise ValueError('Upload a room reference first to guide the existing background.')
            return st.new_job(pid,'reference',r['id'],input_revision=r['revision'],reference_prompt=prompt,reference_purpose=purpose,reference_anchor_id=anchor,category=str(d.get('category','Furniture'))[:100])
        if action in ('use-reference','reject-reference'):
            aid=d['asset_id']
            if aid not in r.get('reference_candidates',[]):raise ValueError('This generated reference does not belong to the room.')
            a=st.asset(aid)
            if action=='reject-reference':a['status']='rejected';st.save();return a
            if a.get('reference_anchor_id') and (a.get('input_revision')!=r['revision'] or a['reference_anchor_id']!=r.get('anchor_id')):raise ValueError('The room environment changed while this reference was generated. Generate an updated reference first.')
            if a.get('reference_purpose')=='environment':r['anchor_id']=aid
            elif aid not in r['references']:r['references'].append(aid)
            else:return a
            a['enabled']=True;a['placement']=str(d.get('placement',''))[:1000];a['status']='selected';st.invalidate(pid,r);st.save();return a
        if action=='reference':
            aid=d['asset_id']
            if aid not in r['references']:raise ValueError('Reference does not belong to this room.')
            if method=='DELETE':r['references'].remove(aid)
            else:
                a=st.asset(aid)
                for k in ['category','placement','enabled']:
                    if k in d:a[k]=bool(d[k]) if k=='enabled' else str(d[k])[:1000]
            st.invalidate(pid,r);st.save();return r
        if action=='generate-image':
            if r.get('plan_id'):
                health=plan_health.inspect(st,pid,r['plan_id'])
                if health['repairs']:
                    result=plan_health.apply(st,pid,r['plan_id'],health['fingerprint'])
                    raise ValueError(result['message'])
            if r.get('furniture_layout',{}).get('items') and not current_layout(r):raise ValueError('The room boundary changed. Reopen and save its furniture placement map before generating.')
            assert_image_gate(p,r);scene_control.clean_control(st,p,r,r.get('scene_control',{}))
            check=plan_preflight.assert_ready(st,p,r)
            return st.new_job(pid,'image',r['id'],input_revision=r['revision'],scene_ticket=scene_control.scene_snapshot(st,p,r),plan_check=check)
        if action=='generate-video':
            if not p['map_confirmed']:raise ValueError('Confirm the room map first.')
            a=approved_image(st,p,r);duration=int(d.get('duration',5));motion=d.get('motion','still')
            if duration not in (5,8) or motion not in ('still','push','slide'):raise ValueError('Choose a supported duration and camera movement.')
            return st.new_job(pid,'video',r['id'],input_revision=r['revision'],source_image_id=a['id'],duration=duration,motion=motion,
                scene_ticket=scene_control.scene_snapshot(st,p,r),source_image_identity=scene_control.file_identity(st,a['id']))
        if action in ['approve-image','reject-image','approve-video','reject-video']:
            kind=action.split('-')[1];aid=d['asset_id']
            if aid not in r['images' if kind=='image' else 'videos']:raise ValueError('This output does not belong to the room.')
            a=st.asset(aid)
            if a.get('input_revision')!=r['revision']:raise ValueError('References changed since this version. Generate an updated image before approving.')
            if action.startswith('approve'):
                source_job=st.db['jobs'].get(a.get('job_id'),{})
                if source_job.get('scene_manifest'):scene_control.assert_scene(st,p,r,source_job['scene_manifest'])
                scene_control.file_identity(st,a['id'])
                if not p['map_confirmed']:raise ValueError('Confirm the room map before approving outputs.')
                if kind=='video' and a.get('source_image_id')!=r.get('approved_image_id'):raise ValueError('This video uses an older image approval.')
                a['status']='approved';a['approved_revision']=r['revision'];a['approved_at']=now();r['approved_'+kind+'_id']=aid
                if kind=='image':r['approved_video_id']=None
            else:
                a['status']='rejected';a['review_note']=str(d.get('reason','Needs revision'))[:2000]
                if r.get('approved_'+kind+'_id')==aid:r['approved_'+kind+'_id']=None
                if kind=='image':r['approved_video_id']=None
            st.save();return a
        raise ValueError('Unknown room action.')
    def import_image(self,pid,d):
        kind=d.get('kind','reference');rid=d.get('room_id')
        with self.store.lock:
            self.store.project(pid)
            if kind not in ('plan','reference','anchor'):raise ValueError('Unknown upload type.')
            if kind!='plan':self.store.room(pid,rid)
            if pid in self.store.moving_projects:raise ValueError('Wait until the project folder copy is complete.')
        raw,name=fetch_public_image(d.get('url',''))
        try:
            with Image.open(io.BytesIO(raw)) as im:
                im.verify();extension={'JPEG':'.jpg','PNG':'.png','WEBP':'.webp','GIF':'.gif','BMP':'.bmp','AVIF':'.avif'}.get(im.format)
                if not extension:raise ValueError('Use a PNG, JPG or WEBP image.')
        except (OSError,SyntaxError):raise ValueError('The link did not return a readable image. Save the photo and upload it instead.')
        name=Path(name).stem+extension
        with self.store.lock:return self.save_upload(pid,kind,rid,name,raw)
    def upload(self,pid,q):
        kind=q.get('kind',['reference'])[0];rid=q.get('room_id',[None])[0]
        n=int(self.headers.get('Content-Length','0'))
        if not 0<n<=MAX_UPLOAD:raise ValueError('Upload a file smaller than 32 MB.')
        name=unquote(self.headers.get('X-Filename','upload.png'))
        return self.save_upload(pid,kind,rid,name,self.rfile.read(n),q.get('category',['Furniture'])[0][:100])
    def save_upload(self,pid,kind,rid,name,raw,category='Furniture'):
        st=self.store;p=st.project(pid)
        if pid in st.moving_projects:raise ValueError('Wait until the project folder copy is complete before uploading.')
        if kind not in ('plan','reference','anchor'):raise ValueError('Unknown upload type.')
        room=st.room(pid,rid) if kind!='plan' else None
        if not 0<len(raw)<=MAX_UPLOAD:raise ValueError('Upload a file smaller than 32 MB.')
        name=Path(name.replace('\\','/')).name
        folder=project_storage.upload_folder(st,pid,kind,rid,uid());folder.mkdir(parents=True)
        original=folder/('original'+Path(name).suffix.lower());original.write_bytes(raw);paths=[];documents={}
        if original.suffix in ('.pdf','.dxf','.dwg') and kind=='plan':
            for item in plan_import.import_file(original,folder):paths.append(item['path']);documents[str(item['path'])]=item
        else:
            out=folder/'image.png'
            if kind=='plan':
                from raster_prepare import prepare
                metadata=prepare(original,out);documents[str(out)]={'path':out,'vector_path':None,'metadata':metadata}
            else:
                with Image.open(original) as im:
                    im.load();im=ImageOps.exif_transpose(im).convert('RGB');im.save(out)
            paths.append(out)
        assets=[]
        with st.lock:
            for path in paths:
                a=register_asset(st,pid,path,kind,rid,display_name=name,category=category,placement='',enabled=True);assets.append(a)
                if kind=='plan':
                    p['floor_plans'].append(a['id'])
                    a['plan_reading']={'version':1,'revision':0,'features':[],'checks':{},'reviewed':False,'warnings':[]}
                    if str(path) in documents:
                        plan_import.attach(st,a,documents[str(path)],original)
                        if documents[str(path)]['metadata']['format'] not in ('PDF','DXF'):ensure_preview(st,a)
                    # Keep native vectors; do not trace or enlarge them again.
                    else:ensure_preview(st,a)
                    plan_setup.initialize(a)
                elif kind=='anchor':room['anchor_id']=a['id']
                else:room['references'].append(a['id'])
            if room:st.invalidate(pid,room)
            else:
                p['map_confirmed']=False;p['map_revision']+=1
                for r in p['rooms']:st.invalidate(pid,r)
            st.save()
            if kind=='plan':
                for a in assets:
                    if not a.get('plan_source',{}).get('vector'):st.new_job(pid,'raster_reconstruction',plan_id=a['id'])
                    st.new_job(pid,'plan_setup',plan_id=a['id'])
        return {'assets':[{'id':a['id'],'url':'/media/'+a['id']} for a in assets]}

def make_server(data,port=8777,start_worker=True):
    st=Store(data);engine=Engine(st,ROOT);http=ThreadingHTTPServer(('127.0.0.1',port),Handler);http.store=st;http.engine=engine
    if start_worker:threading.Thread(target=engine.worker,daemon=True,name='Pixeloid render queue').start()
    return http

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--port',type=int,default=8777);ap.add_argument('--data',default=str(ROOT/'data'));args=ap.parse_args()
    http=make_server(args.data,args.port)
    (ROOT/'server.pid').write_text(str(os.getpid()))
    print(f'Pixeloid Studio is ready at http://127.0.0.1:{http.server_port}',flush=True)
    try:http.serve_forever()
    finally:http.engine.stop.set();http.server_close()
