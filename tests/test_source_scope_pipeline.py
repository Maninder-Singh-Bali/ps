import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image, ImageDraw
from store import Store
from engine import Engine, register_asset
import source_scope, source_panels, plan_setup, plan_reading, vision_study
from raster_reconstruction import apply_report

ROOT=Path(__file__).resolve().parents[1]


class ScopePipeline(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir=ROOT/'tests');self.root=Path(self.tmp.name)
        self.st=Store(self.root/'data');self.p=self.st.create_project('Scope integration');self.pid=self.p['id']
        im=Image.new('RGB',(400,200),'red');draw=ImageDraw.Draw(im)
        draw.rectangle((0,0,99,199),fill='blue');draw.rectangle((200,0,299,199),fill='green')
        path=self.root/'source.png';im.save(path)
        self.a=register_asset(self.st,self.pid,path,'plan');self.aid=self.a['id'];self.p['floor_plans']=[self.aid]
        self.a['source_review']={'kind':'mixed','reviewed':True,'revision':1,'source_sha256':self.a['sha256'],
            'panels':[{'id':'west','floor':'Ground','bbox':[0,0,.25,1]}, {'id':'east','floor':'First','bbox':[.5,0,.25,1]}]}
        self.a['plan_reading']={'features':[],'revision':0};plan_setup.initialize(self.a)
        self.engine=Engine(self.st,ROOT)
    def tearDown(self):
        self.engine.session.close();self.tmp.cleanup()
    def pixels(self,path):
        with Image.open(path) as im:
            self.assertEqual(im.size,(100,200));self.assertNotIn((255,0,0),set(im.convert('RGB').getdata()))
    def test_all_reader_inputs_exclude_other_panels_and_sheet_content(self):
        seen=[]
        def detect(path):
            self.pixels(path);seen.append('structure');return [{'kind':'wall','bbox':[.2,.3,.4,.5]}]
        def ocr(path,*args):
            self.pixels(path);seen.append('ocr');return {'rooms':[{'name':'Room','bbox':[.2,.3,.4,.5]}]}
        job=self.st.new_job(self.pid,'plan_setup',plan_id=self.aid)
        with patch('plan_reading.detect',side_effect=detect),patch('plan_setup.analysis.analyze_local',side_effect=ocr):
            plan_setup.run(self.engine,job)
        self.assertEqual(seen.count('structure'),2);self.assertEqual(seen.count('ocr'),2)
        rooms=self.st.project(self.pid)['rooms']
        self.assertEqual([r['floor'] for r in rooms],['Ground','First'])
        self.assertEqual([r['panel_id'] for r in rooms],['west','east'])
        self.assertEqual(rooms[0]['bbox'],[.05,.3,.1,.5]);self.assertEqual(rooms[1]['bbox'],[.55,.3,.1,.5])
        def enhance(path,*args):self.pixels(path);seen.append('upscale');return path,{'scale':1}
        def visual(path,enhanced,*args,**kw):
            self.pixels(path);self.pixels(enhanced);seen.append('visual')
            self.assertEqual(kw['source_scope']['source_sha256'],self.a['sha256'])
            return {'features':[{'id':'symbol','kind':'furniture','object_type':'chair','label':'chair','bbox':[.2,.3,.4,.5]}],
                    'coverage_complete':True,'coverage':{'pending_regions':0},'warnings':[]}
        with patch('plan_upscale.enhance',side_effect=enhance),patch('object_detection.read',side_effect=visual):
            report=vision_study.read_scoped(self.a,source_scope.capture(self.a),{},[],lambda *a:None,self.root/'vision',ROOT,lambda:False)
        self.assertEqual(seen.count('visual'),2);self.assertEqual(seen.count('upscale'),2)
        self.assertEqual([f['bbox'] for f in report['features']],[[.05,.3,.1,.5],[.55,.3,.1,.5]])
        self.assertNotEqual(report['features'][0]['id'],report['features'][1]['id'])
    def test_masked_raster_input_and_exact_pixel_transforms(self):
        scope=source_scope.capture(self.a);panels,masked=source_scope.materialize(self.a,scope,self.root/'crops')
        with Image.open(masked) as im:
            self.assertEqual(im.getpixel((150,100)),(255,255,255));self.assertEqual(im.getpixel((350,100)),(255,255,255))
            self.assertEqual(im.getpixel((250,100)),(0,128,0))
        self.assertEqual(panels[1]['crop_to_sheet'],[1,0,0,1,200,0])
        for actual,expected in zip(source_scope.local_sections([{'id':'r','bbox':[.45,.2,.2,.5]}],panels[1])[0]['bbox'],[0,.2,.6,.5]):self.assertAlmostEqual(actual,expected)
    def approve(self,box=None):
        return source_panels.save(self.st,self.pid,self.aid,{'revision':self.a['source_review']['revision'],'kind':'plan',
            'panels':[{'id':'west','floor':'Ground','bbox':box or [0,0,.25,1]}],'checked':True})
    def test_approval_resumes_blocked_setup_then_semantics_without_duplicate_jobs(self):
        self.st.db['settings']['vision_model']='installed-test-model'
        self.a['source_review']['reviewed']=False
        blocked=self.st.new_job(self.pid,'plan_setup',plan_id=self.aid);plan_setup.run(self.engine,blocked)
        self.assertEqual(blocked['blocked_on'],'source_review')
        self.approve()
        active=[j for j in self.st.db['jobs'].values() if j['status']=='queued']
        self.assertEqual(sorted(j['kind'] for j in active),['plan_setup','raster_reconstruction'])
        job=next(j for j in active if j['kind']=='plan_setup')
        self.assertEqual(job['id'],self.st.new_job(self.pid,'plan_setup',plan_id=self.aid)['id'])
        with patch('plan_reading.detect',return_value=[]),patch('analysis.analyze_local',return_value={'rooms':[]}):
            plan_setup.run(self.engine,job)
        models=[j for j in self.st.db['jobs'].values() if j['kind']=='vision_study']
        self.assertEqual(len(models),1);self.assertEqual(models[0]['source_scope']['revision'],2)
    def test_crop_change_during_ocr_discards_completion_and_undo_cannot_revive_it(self):
        before=source_scope.capture(self.a);self.a['drawing']['features']=[{'id':'manual'}]
        job=self.st.new_job(self.pid,'plan_setup',plan_id=self.aid)
        changed=False
        def reader(*args):
            nonlocal changed
            if not changed:self.approve([.5,0,.25,1]);changed=True
            return {'rooms':[{'name':'obsolete','bbox':[0,0,1,1]}]}
        with patch('plan_reading.detect',return_value=[]),patch('analysis.analyze_local',side_effect=reader):plan_setup.run(self.engine,job)
        self.assertEqual(job['status'],'cancelled');self.assertFalse(self.st.project(self.pid)['rooms'])
        self.assertEqual(self.a['drawing']['features'],[{'id':'manual'}])
        source_panels.save(self.st,self.pid,self.aid,{'revision':2,'action':'undo'})
        self.assertFalse(source_scope.current(self.a,before));self.assertEqual(self.a['source_review']['panels'][0]['bbox'],[0,0,.25,1])
        self.assertIsNone(source_scope.prepare(self.st,job))
    def test_vision_completion_cannot_replace_current_report_after_scope_change(self):
        previous={'features':[],'marker':'preserved'};self.a['vision_report']=copy.deepcopy(previous)
        job=self.st.new_job(self.pid,'vision_study',plan_id=self.aid)
        def read(*args):
            self.approve([.5,0,.25,1]);return {'features':[],'coverage_complete':True}
        with patch.object(self.engine,'get',return_value={'queue_running':[],'queue_pending':[]}),patch.object(self.engine,'post'),patch('engine.memory_headroom',return_value=(64,64)),patch('engine.available_vram',return_value=16),patch('vision_study.ensure_service',return_value={'models':[{'name':vision_study.MODEL}]}),patch('vision_study.read_scoped',side_effect=read):
            vision_study.run(self.engine,job)
        self.assertEqual(job['status'],'cancelled');self.assertEqual(self.a['vision_report']['marker'],'preserved')
        self.assertTrue(job['report']['stale'])
    def test_raster_completion_discards_changed_scope_and_retains_scaled_panel_identity(self):
        import json
        from unittest.mock import Mock
        import raster_reconstruction as raster
        def worker(args,**kwargs):
            with Image.open(args[2]) as im:self.assertEqual(im.getpixel((150,100)),(255,255,255))
            folder=Path(args[3]);Image.new('RGB',(200,100),'white').save(folder/'boundary-overlay.png')
            report={'analysis_size':[200,100],'source_scope':source_panels.digest(self.a['source_review']['panels']),
                'walls':[{'id':'candidate','width_px':3,'geometry':{'type':'line','points':[[110,20],[140,20]]}}],
                'openings':[],'uncertain_spans':[],'regions':[]}
            (folder/'raster-geometry.json').write_text(json.dumps(report),encoding='utf-8')
            if changed:self.approve([0,0,.25,1])
            return Mock(poll=Mock(return_value=0),communicate=Mock(return_value=(b'',b'')),returncode=0)
        changed=False;job=self.st.new_job(self.pid,'raster_reconstruction',plan_id=self.aid)
        with patch('raster_reconstruction.runtime',return_value=Path('python')),patch('raster_reconstruction.subprocess.Popen',side_effect=worker):raster.run(self.engine,job)
        wall=self.a['raster_geometry']['walls'][0]
        self.assertEqual((wall['panel_id'],wall['floor']),('east','First'))
        retained=copy.deepcopy(self.a['raster_geometry']);self.approve([.5,0,.25,1])
        changed=True;job=next(j for j in self.st.db['jobs'].values() if j['kind']=='raster_reconstruction' and j['status']=='queued')
        with patch('raster_reconstruction.runtime',return_value=Path('python')),patch('raster_reconstruction.subprocess.Popen',side_effect=worker):raster.run(self.engine,job)
        self.assertEqual(job['status'],'cancelled');self.assertEqual(self.a['raster_geometry'],retained)
    def test_explicit_native_crop_is_not_bypassed_by_vector_flag(self):
        self.a['plan_source']={'vector':True}
        scope=source_scope.capture(self.a)
        self.assertEqual([p['id'] for p in scope['panels']],['west','east'])
        self.a['source_review']['reviewed']=False
        self.assertFalse(source_panels.ensure(self.st,self.pid,self.aid))
        with self.assertRaises(ValueError):source_scope.capture(self.a)
    def test_classifier_cannot_approve_its_own_panels(self):
        self.a['source_review'].update(reviewed=False,automatic_trace=True,kind='plan')
        job=self.st.new_job(self.pid,'plan_setup',plan_id=self.aid)
        with patch('plan_reading.detect') as detect,patch('analysis.analyze_local') as ocr:
            plan_setup.run(self.engine,job)
            detect.assert_not_called();ocr.assert_not_called()
        self.assertEqual(job['blocked_on'],'source_review')
    def test_source_save_failure_rolls_back_jobs_scope_and_preserves_live_job_identity(self):
        job=self.st.new_job(self.pid,'plan_setup',plan_id=self.aid);before=copy.deepcopy(self.st.db)
        with patch.object(self.st,'save',side_effect=OSError('disk full')):
            with self.assertRaises(OSError):self.approve()
        self.assertEqual(self.st.db,before);self.assertIs(self.st.db['jobs'][job['id']],job)
    def test_obsolete_or_exhausted_activity_cannot_retry(self):
        import job_control
        job=self.st.new_job(self.pid,'vision_study',plan_id=self.aid);self.approve()
        with self.assertRaisesRegex(ValueError,'obsolete'):job_control.recover(self.engine,job)
        new=self.st.new_job(self.pid,'vision_study',plan_id=self.aid)
        new.update(status='failed',report={'coverage_complete':False,'coverage':{'pending_regions':0,'failed_regions':0}})
        with self.assertRaisesRegex(ValueError,'exhausted'):job_control.recover(self.engine,new)
    def test_identical_raster_evidence_does_not_invalidate_manual_edits_or_revision(self):
        r={'source_sha256':'source','analysis_size':[400,200],'walls':[],'uncertain_spans':[],'openings':[],'regions':[]}
        apply_report(self.a,r);self.a['raster_undo']=[{'kept':'review'}]
        revision=self.a['drawing']['revision'];apply_report(self.a,{**r,'cached':True,'overlay_asset_id':'another','elapsed_seconds':99})
        self.assertEqual(self.a['drawing']['revision'],revision);self.assertEqual(self.a['raster_undo'],[{'kept':'review'}])


if __name__=='__main__':unittest.main()
