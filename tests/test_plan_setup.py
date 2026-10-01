import copy
import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image,ImageDraw

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from store import Store
from engine import Engine,register_asset
from server import Handler
import plan_setup
import scene_scale


class PlanSetup(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir=ROOT/'tests');self.root=Path(self.tmp.name)
        self.st=Store(self.root/'data');self.p=self.st.create_project('Import test');self.pid=self.p['id']
        self.path=self.root/'plan.png';im=Image.new('RGB',(400,200),'white');ImageDraw.Draw(im).rectangle((30,30,370,170),outline='black',width=5);im.save(self.path)
        self.a=register_asset(self.st,self.pid,self.path,'plan');self.p['floor_plans'].append(self.a['id'])
        self.a['plan_reading']={'features':[],'revision':0};plan_setup.initialize(self.a)
        self.engine=Engine(self.st,ROOT)
        self.job=self.st.new_job(self.pid,'plan_setup',plan_id=self.a['id'])
        self.result={'rooms':[{'name':'Kitchen','floor':'Ground floor','bbox':[.2,.3,.4,.5]}],'warnings':[]}
    def tearDown(self):self.engine.session.close();self.tmp.cleanup()
    def run_setup(self,reader=None):
        with patch('plan_setup.analysis.analyze_local',side_effect=reader or (lambda *a:self.result)),patch('plan_reading.detect',return_value=[]):
            plan_setup.run(self.engine,self.job)
    def test_automatic_defaults_and_independent_page_jobs(self):
        self.assertEqual(scene_scale.settings(self.a,'Ground floor')['wall_height_m'],3)
        self.assertAlmostEqual(scene_scale.settings(self.a,'Ground floor')['eye_height_m'],1.5664)
        self.assertEqual(self.st.new_job(self.pid,'plan_setup',plan_id=self.a['id'])['id'],self.job['id'])
        self.assertNotEqual(self.st.new_job(self.pid,'plan_setup',plan_id='other')['id'],self.job['id'])
    def test_installed_detection_is_queued_after_import_without_approving_geometry(self):
        self.engine.app_root=self.root
        for name in ('runtime/ollama/ollama.exe','models/upscale/realesr-general-x4v3.pth'):
            target=self.root/name;target.parent.mkdir(parents=True,exist_ok=True);target.touch()
        self.run_setup()
        jobs=[j for j in self.st.db['jobs'].values() if j['kind']=='vision_study']
        self.assertEqual(len(jobs),1);self.assertTrue(jobs[0]['automatic'])
        self.assertEqual(jobs[0]['plan_id'],self.a['id'])
        self.assertEqual(jobs[0]['input_revision'],self.st.project(self.pid)['map_revision'])
        self.assertFalse(self.st.project(self.pid)['map_confirmed'])
    def test_relative_storage_path_is_canonical(self):
        import os
        loaded=Store(os.path.relpath(self.st.root))
        self.assertEqual(loaded.root,self.st.root)
    def test_upload_actually_schedules_setup(self):
        handler=object.__new__(Handler)
        handler.server=type('Server',(),{'store':self.st})()
        out=Handler.save_upload(handler,self.pid,'plan',None,'plan.png',self.path.read_bytes())
        aid=out['assets'][0]['id']
        self.assertIn('model',self.st.asset(aid)['drawing']['site'])
        self.assertTrue(any(j.get('plan_id')==aid and j['kind']=='plan_setup' for j in self.st.db['jobs'].values()))
    def test_idempotent_completion_persists_and_keeps_other_pages(self):
        other=self.st.add_room(self.pid,'Existing','First floor','another',[0,0,1,1]);before=copy.deepcopy(other)
        self.run_setup();self.run_setup()
        p=self.st.project(self.pid);self.assertEqual(len(p['rooms']),2)
        self.assertEqual(p['rooms'][0],before);self.assertFalse(p['map_confirmed'])
        loaded=Store(self.st.root)
        self.assertEqual(loaded.asset(self.a['id'])['setup']['status'],'needs_review')
        self.assertFalse(loaded.asset(self.a['id'])['plan_reading']['reviewed'])
        self.assertEqual(loaded.db['jobs'][self.job['id']]['status'],'completed')
    def test_background_reader_never_overwrites_concurrent_edits(self):
        def edit(*args):
            self.st.add_room(self.pid,'My room','Custom',self.a['id'],[0,0,1,1])
            self.a['drawing']['features']=[{'id':'user-wall'}]
            return self.result
        self.run_setup(edit)
        self.assertEqual([r['name'] for r in self.st.project(self.pid)['rooms']],['My room'])
        self.assertEqual(self.st.asset(self.a['id'])['drawing']['features'],[{'id':'user-wall'}])
        self.assertEqual(self.st.asset(self.a['id'])['setup']['suggested_rooms'][0]['name'],'Kitchen')
    def test_failed_reader_preserves_upload_and_defaults(self):
        def fail(*args):raise RuntimeError('OCR unavailable')
        self.run_setup(fail)
        a=self.st.asset(self.a['id']);self.assertTrue(Path(a['path']).exists())
        self.assertEqual(a['setup']['status'],'needs_review')
        self.assertIn('OCR unavailable',' '.join(a['setup']['warnings']))
        self.assertAlmostEqual(a['drawing']['site']['model']['human_height_m'],1.6764)
    def test_invalid_or_edge_boxes_are_bounded(self):
        rows=plan_setup.normalized_rooms([{'bbox':[.99,.99,.2,.2]},{'bbox':[float('nan'),0,1,1]}],self.a['id'])
        self.assertAlmostEqual(rows[0]['bbox'][2],.01);self.assertIsNone(rows[1]['bbox'])
    def test_native_units_and_invalid_furniture_dimensions(self):
        self.a['plan_source']={'metres_per_pixel':.025}
        self.assertEqual(scene_scale.estimate(self.st,self.a)[0],.025)
        self.a['drawing']['site']['model']['metres_per_pixel']=.04
        self.assertEqual(scene_scale.estimate(self.st,self.a)[0],.04)
        del self.a['drawing']['site']['model']['metres_per_pixel'];self.a['plan_source']['metres_per_pixel']=float('nan')
        r=self.st.add_room(self.pid,'Bad data','Ground',self.a['id'],[0,0,1,1])
        r['block_layout']={'items':[{'width':0,'depth':.1,'preset_id':'chair','physical_size':{'width':.55,'depth':.55}}]}
        self.assertEqual(scene_scale.estimate(self.st,self.a)[1],'Uncalibrated estimate')


if __name__=='__main__':unittest.main()
