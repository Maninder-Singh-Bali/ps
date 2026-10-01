import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import tempfile, threading, unittest, json, io
import requests
from PIL import Image
from server import make_server,bbox,ROOT
from store import approved_image,assert_image_gate
from engine import register_asset,Engine,local_url
from analysis import parse_ocr

class StudioTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='pixeloid-test-',dir=ROOT/'tests');self.root=Path(self.temp.name)
        self.http=make_server(self.root,0,False);self.http.engine.health=lambda **kw:{'connected':False}
        threading.Thread(target=self.http.serve_forever,daemon=True).start();self.url=f'http://127.0.0.1:{self.http.server_port}'
        self.client=requests.Session();self.client.trust_env=False;self.st=self.http.store
        self.p=self.call('/api/projects',{'name':'Test residence'});self.pid=self.p['id']
        self.r=self.call(f'/api/projects/{self.pid}/rooms',{'name':'Living','floor':'Ground floor','bbox':[.1,.1,.3,.3]});self.rid=self.r['id'];self.route=f'/api/projects/{self.pid}/rooms/{self.rid}'
    def tearDown(self):self.http.shutdown();self.http.server_close();self.client.close();self.temp.cleanup()
    def call(self,path,data,method='POST',status=200):
        r=self.client.request(method,self.url+path,json=data);self.assertEqual(r.status_code,status,r.text);return r.json()
    def asset(self,kind='image',**kw):
        path=self.root/('source-'+kind+'.png');Image.new('RGB',(1920,1080),'white').save(path)
        return register_asset(self.st,self.pid,path,kind,self.rid,input_revision=self.st.room(self.pid,self.rid)['revision'],status='review',**kw)
    def approve(self):
        self.call(f'/api/projects/{self.pid}/confirm-map',{});a=self.asset();r=self.st.room(self.pid,self.rid);r['images'].append(a['id']);self.st.save();self.call(self.route+'/approve-image',{'asset_id':a['id']});return a
    def test_map_and_image_approval_gates(self):
        self.call(self.route+'/generate-image',{},status=400)
        self.call(self.route+'/generate-video',{},status=400)
        self.call(f'/api/projects/{self.pid}/confirm-map',{})
        self.call(self.route+'/generate-video',{},status=400)
        a=self.approve();j=self.call(self.route+'/generate-video',{'duration':5,'motion':'still'})
        self.assertEqual(j['source_image_id'],a['id']);self.assertEqual(j['status'],'queued')
    def test_scene_control_api_stale_edits_and_running_work(self):
        a=self.approve();r=self.st.room(self.pid,self.rid);r['anchor_id']=a['id'];before=r['revision']
        body={'revision':before,'mode':'region','source_id':a['id'],'region':[.5,.5,.3,.3],'instruction':'Replace selected chair','denoise':.75}
        self.call(self.route+'/scene-control',body);self.assertEqual(r['revision'],before+1);self.assertIsNone(r['approved_image_id'])
        self.call(self.route+'/scene-control',body,status=400)
        j=self.call(self.route+'/generate-image',{});self.assertEqual(j['scene_ticket']['content']['control']['mode'],'region')
        self.call(self.route+'/scene-control',{**body,'revision':r['revision']},status=400)
    def test_prompt_preparation_does_not_change_source_or_approval(self):
        a=self.approve();before=self.st.snapshot()
        result=self.call(self.route+'/prepare-edit',{'instruction':'replace this chair with the refrence, dont change the table','mode':'region'})
        self.assertIn('do not change the table',result['prompt']);self.assertEqual(self.st.snapshot(),before)
    def test_locked_video_anchors_end_and_crops_guides(self):
        a=self.approve();room=self.st.room(self.pid,self.rid);engine=Engine(self.st,ROOT);engine.upload=lambda path:Path(path).name
        job=self.st.new_job(self.pid,'video',self.rid,input_revision=room['revision'],source_image_id=a['id'],duration=5,motion='still')
        graph,_=engine.build_video(job,self.root)
        self.assertEqual(graph['35']['inputs']['image'],['10',0]);self.assertEqual(graph['35']['inputs']['frame_idx'],120);self.assertEqual(graph['29']['inputs']['samples'],['36',2])
        job['motion']='push';graph,_=engine.build_video(job,self.root);self.assertNotIn('35',graph)
    def test_reference_edits_invalidate_approval_and_queued_work(self):
        a=self.approve();j=self.call(self.route+'/generate-video',{})
        self.call(self.route,{'notes':'Change furniture placement'},'PATCH')
        self.call(self.route+'/generate-video',{},status=400)
        self.call(self.route+'/approve-image',{'asset_id':a['id']},status=400)
        engine=Engine(self.st,ROOT)
        with self.assertRaises(ValueError):engine.build_video(self.st.db['jobs'][j['id']],self.root)
    def test_dedup_and_cancel_without_interrupting_engine(self):
        self.call(f'/api/projects/{self.pid}/confirm-map',{})
        source=self.asset('anchor');self.st.room(self.pid,self.rid)['anchor_id']=source['id'];self.st.save()
        one=self.call(self.route+'/generate-image',{});two=self.call(self.route+'/generate-image',{})
        self.assertEqual(one['id'],two['id']);self.call('/api/jobs/'+one['id']+'/cancel',{})
        self.assertEqual(self.st.db['jobs'][one['id']]['status'],'cancelled')
    def test_cross_room_approval_is_rejected(self):
        self.call(f'/api/projects/{self.pid}/confirm-map',{})
        a=self.asset();self.call(self.route+'/approve-image',{'asset_id':a['id']},status=400)
    def test_upload_roundtrip_and_public_state(self):
        b=io.BytesIO();Image.new('RGB',(80,60)).save(b,format='PNG')
        res=self.client.post(self.url+f'/api/projects/{self.pid}/upload?kind=anchor&room_id={self.rid}',data=b.getvalue(),headers={'Content-Type':'application/octet-stream','X-Filename':'../../room.png'})
        self.assertEqual(res.status_code,200,res.text);aid=res.json()['assets'][0]['id']
        a=self.st.asset(aid);self.assertTrue(Path(a['path']).is_relative_to(self.root));self.assertEqual(a['display_name'],'room.png')
        public=self.client.get(self.url+'/api/state').json();self.assertNotIn('path',public['assets'][aid])
        media=self.client.get(self.url+'/media/'+aid,headers={'Range':'bytes=0-7'});self.assertEqual(media.status_code,206);self.assertEqual(len(media.content),8)
    def test_external_origin_and_bad_engine_address_blocked(self):
        response=self.client.post(self.url+'/api/projects',json={'name':'Bad'},headers={'Origin':'https://other.example'})
        self.assertEqual(response.status_code,403)
        self.call('/api/settings',{'comfy_url':'https://remote.example'},'PATCH',400)
        for b in [[.9,.1,.5,.3],[-.1,.1,.3,.2],[.1,.1,0,.2]]:
            with self.assertRaises(ValueError):bbox(b)
    def test_native_graphs_and_exact_approved_video_source(self):
        a=self.approve();room=self.st.room(self.pid,self.rid);room['anchor_id']=a['id'];engine=Engine(self.st,ROOT);engine.upload=lambda path:'test.png'
        j=self.st.new_job(self.pid,'image',self.rid,input_revision=room['revision']);g,node=engine.build_image(j,self.root)
        self.assertEqual(g['20']['inputs']['width'],1920);self.assertEqual(g['20']['inputs']['height'],1088);self.assertEqual(g['23']['inputs']['height'],1080)
        self.assertFalse(any('Upscale' in n['class_type'] for n in g.values()))
        v=self.st.new_job(self.pid,'video',self.rid,input_revision=room['revision'],source_image_id=a['id'],duration=5,motion='still');vg,_=engine.build_video(v,self.root)
        self.assertEqual(vg['11']['inputs']['width'],1920);self.assertEqual(vg['11']['inputs']['length'],121);self.assertEqual(vg['34']['inputs']['length'],120)
        self.assertFalse(any('Upscale' in n['class_type'] for n in vg.values()))
    def test_progress_is_prompt_scoped(self):
        e=Engine(self.st,ROOT);j=self.st.new_job(self.pid,'image',self.rid,input_revision=1);j['prompt_id']='ours'
        graph=json.loads((ROOT/'templates/flux.json').read_text(encoding='utf8'))
        e.event(j,{'type':'progress','data':{'prompt_id':'other','node':'21','value':3,'max':4}},graph);self.assertIsNone(j['progress'])
        e.event(j,{'type':'progress','data':{'prompt_id':'ours','node':'21','value':2,'max':4}},graph);self.assertEqual(j['progress'],50)
        e.event(j,{'type':'executing','data':{'prompt_id':'ours','node':'22'}},graph);self.assertEqual(j['progress'],50);self.assertIn('Decoding',j['stage'])
    def test_scene_time_guidance_flows_to_flux_and_approved_ltx(self):
        from scene_sun import clean_site
        anchor=self.approve();r=self.st.room(self.pid,self.rid);r['anchor_id']=anchor['id'];plan=self.asset('plan');r['plan_id']=plan['id']
        site=clean_site({'latitude':0,'longitude':0,'north_confirmed':True,'north_angle':90,'date':'2026-03-20','time':'00:00','utc_offset':0,'sun_enabled':True})
        plan['drawing']={'site':site};e=Engine(self.st,ROOT);e.upload=lambda path:Path(path).name
        j=self.st.new_job(self.pid,'image',self.rid,input_revision=r['revision']);g,_=e.build_image(j,self.root)
        self.assertIn('No direct sunlight',g['6']['inputs']['text']);self.assertNotIn('openings, lighting and all objects',j['prompt']);self.assertTrue((self.root/'scene-lighting.json').exists())
        # Site settings can have an exported CAD preview; lighting alone must
        # not add that competing architecture image to the conditioning.
        plan['drawing'].update(guidance_asset_id='unused-preview',edits={},features=[])
        again,_=e.build_image(j,self.root);self.assertNotIn('200',again)
        anchor['job_id']=j['id'];v=self.st.new_job(self.pid,'video',self.rid,input_revision=r['revision'],source_image_id=anchor['id'],duration=5);vg,_=e.build_video(v,self.root)
        self.assertEqual(v['scene_lighting']['site'],site);self.assertEqual(vg['8']['inputs']['image'],Path(anchor['path']).name);self.assertIn('Exposure and daylight direction stay constant',v['prompt'])
    def test_label_reader_does_not_claim_legend_is_complete_map(self):
        lines=[{'text':t,'words':[{'x':10,'y':i*20}]} for i,t in enumerate(['1. Living Room','2. Kitchen','3. Bedroom'])]
        result=parse_ocr({'width':600,'height':500,'lines':lines},'plan');self.assertEqual(len(result['rooms']),3);self.assertTrue(result['warnings']);self.assertTrue(all(r['bbox'] is None for r in result['rooms']))
    def test_prompt_reference_is_native_and_requires_explicit_selection(self):
        j=self.call(self.route+'/generate-reference',{'prompt':'A sculptural walnut chair with plain cream linen upholstery','purpose':'product','category':'Chair'})
        self.assertFalse(self.st.project(self.pid)['map_confirmed'])
        e=Engine(self.st,ROOT);g,_=e.build_reference(self.st.db['jobs'][j['id']],self.root)
        self.assertEqual(g['20']['inputs']['width'],1920);self.assertEqual(g['20']['inputs']['height'],1088)
        self.assertFalse(any(n['class_type']=='ReferenceLatent' for n in g.values()))
        a=self.asset('reference_candidate',reference_purpose='product');r=self.st.room(self.pid,self.rid);r['reference_candidates']=[a['id']];self.st.save()
        self.assertEqual(r['references'],[])
        self.call(self.route+'/use-reference',{'asset_id':a['id']});self.assertIn(a['id'],r['references']);self.assertEqual(r['revision'],2)
        self.call(self.route+'/generate-video',{},status=400)
    def test_background_reference_control_uses_exact_room_anchor(self):
        a=self.asset('anchor');r=self.st.room(self.pid,self.rid);r['anchor_id']=a['id'];self.st.save()
        j=self.call(self.route+'/generate-reference',{'prompt':'Replace only the lamp with a bronze lamp','purpose':'environment','use_environment':True})
        self.assertEqual(j['reference_anchor_id'],a['id']);e=Engine(self.st,ROOT);seen=[];e.upload=lambda path:seen.append(path) or 'exact-anchor.png'
        g,_=e.build_reference(self.st.db['jobs'][j['id']],self.root);self.assertEqual(g['4']['inputs']['image'],'exact-anchor.png');self.assertEqual(seen,[a['path']])

    def test_visual_placements_saved_and_passed_to_generation(self):
        from placement_map import current_layout
        plan=self.asset('plan');sofa=self.asset('reference',category='Sofa');r=self.st.room(self.pid,self.rid)
        r['plan_id']=plan['id'];r['references']=[sofa['id']];self.st.project(self.pid)['floor_plans']=[plan['id']];self.st.save()
        approved=self.approve();revision=r['revision']
        payload={'revision':revision,'items':[{'asset_id':sofa['id'],'x':.2,'y':.7,'angle':90}]}
        self.call(self.route+'/placement-map',payload)
        self.assertIsNone(r['approved_image_id']);self.assertEqual(r['revision'],revision+1)
        self.assertEqual(current_layout(r)['items'][0]['x'],.2)
        self.call(self.route+'/placement-map',payload,status=400) # stale editor cannot overwrite
        j=self.st.new_job(self.pid,'image',self.rid,input_revision=r['revision']);e=Engine(self.st,ROOT);e.upload=lambda path:Path(path).name
        g,_=e.build_image(j,self.root)
        self.assertEqual(g['200']['inputs']['image'],'furniture_placement_guide.png')
        self.assertIn('Marker 1 is the product in image 2',j['prompt'])
        self.assertEqual(g['20']['inputs']['width'],1920);self.assertEqual(g['20']['inputs']['height'],1088)
        self.assertTrue((self.root/'furniture_placement_guide.png').is_file())
        self.st.update_job(j['id'],status='completed');r['bbox']=[.2,.2,.3,.3];self.st.save()
        self.assertFalse(current_layout(r));self.call(self.route+'/generate-image',{},status=400)

    def test_multi_product_layout_stays_within_klein_reference_budget(self):
        a=self.approve();r=self.st.room(self.pid,self.rid);r['anchor_id']=a['id']
        plan=self.asset('plan');r['plan_id']=plan['id'];self.p['floor_plans']=[plan['id']]
        refs=[self.asset('reference',category=label) for label in ['Sofa','Coffee table','Chair']]
        r['references']=[a['id'] for a in refs]
        self.call(self.route+'/placement-map',{'revision':r['revision'],'items':[{'asset_id':a['id'],'x':.2+i*.2,'y':.5,'angle':0} for i,a in enumerate(refs)]})
        self.call(f'/api/projects/{self.pid}/confirm-map',{})
        engine=Engine(self.st,ROOT);engine.upload=lambda p:Path(p).name
        j=self.st.new_job(self.pid,'image',self.rid,input_revision=r['revision']);g,_=engine.build_image(j,self.root)
        self.assertEqual(sum(n['class_type']=='LoadImage' for n in g.values()),3)
        self.assertEqual(j['placement_control']['conditioning_image_count'],3)
        self.assertIn('product 3',j['prompt'].lower());self.assertNotIn('Product image 4',j['prompt'])
        self.assertTrue((self.root/'furniture_product_board.png').exists())

    def test_placement_validation_is_atomic(self):
        plan=self.asset('plan');sofa=self.asset('reference');r=self.st.room(self.pid,self.rid)
        r['plan_id']=plan['id'];r['references']=[sofa['id']];self.st.save()
        for row in [{'asset_id':'wrong','x':.2,'y':.7,'angle':90},{'asset_id':sofa['id'],'x':2,'y':.7,'angle':90},{'asset_id':sofa['id'],'x':.2,'y':.7,'angle':'NaN'}]:
            self.call(self.route+'/placement-map',{'revision':r['revision'],'items':[row]},status=400)
        self.assertNotIn('furniture_layout',r)

if __name__=='__main__':unittest.main()
