import sys,json,tempfile,copy,unittest,threading
from pathlib import Path
from unittest.mock import patch,Mock
from PIL import Image
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from store import Store
from engine import register_asset
import raster_reconstruction as raster
import job_control

class RasterReviewTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(dir=Path(__file__).parent);self.root=Path(self.tmp.name)
  self.st=Store(self.root/'data');self.p=self.st.create_project('Raster correction test')
  image=self.root/'source.png';Image.new('RGB',(100,100),'white').save(image)
  self.a=register_asset(self.st,self.p['id'],image,'plan');self.p['floor_plans']=[self.a['id']]
  self.a['raster_geometry']={'source_sha256':self.a['sha256'],'analysis_size':[100,100],'walls':[{'id':'wall-a','width_px':6,'geometry':{'type':'polyline','points':[[10,10],[10,80]]}}],'uncertain_spans':[{'id':'edge-b','geometry':{'type':'polyline','points':[[70,10],[70,80]]}}]}
  self.st.save()
 def tearDown(self):self.tmp.cleanup()
 def correction(self,**kw):return raster.correct(self.st,self.p['id'],self.a['id'],{'revision':self.a.get('raster_revision',0),'source_sha256':self.a['sha256'],'id':'wall-a','action':'edit','points':[[12,10],[12,80]],**kw})
 def test_edit_undo_redo_persists_and_changes_shared_draft(self):
  original=Path(self.a['path']).read_bytes();report=copy.deepcopy(self.a['raster_geometry'])
  first=raster.draft(self.st,self.p['id'],self.a['id'])['geometry_hash']
  self.correction();edited=raster.draft(self.st,self.p['id'],self.a['id'])['geometry_hash'];self.assertNotEqual(first,edited)
  self.assertEqual(Store(self.st.root).asset(self.a['id'])['raster_corrections']['wall-a']['points'][0],[12,10])
  self.correction(action='undo');self.assertEqual(first,raster.draft(self.st,self.p['id'],self.a['id'])['geometry_hash'])
  self.correction(action='redo');self.assertEqual(edited,raster.draft(self.st,self.p['id'],self.a['id'])['geometry_hash'])
  self.assertEqual(report,self.a['raster_geometry']);self.assertEqual(original,Path(self.a['path']).read_bytes())
 def test_uncertain_contour_and_detection_box_do_not_create_walls(self):
  self.a['vision_report']={'features':[{'kind':'wall','bbox':[0,0,1,1]}]}
  self.assertEqual([e['id'] for e in raster.elements(self.a)],['wall-a'])
  self.correction(id='edge-b',action='accept',kind='window',points=None)
  self.assertEqual(raster.elements(self.a)[1]['kind'],'window')
 def test_invalid_kind_does_not_mutate_history(self):
  before=copy.deepcopy(self.a)
  with self.assertRaises(ValueError):self.correction(kind='sofa')
  self.assertEqual(self.a,before)
 def test_opening_needs_explicit_classification_and_open_transition_stays_empty(self):
  self.a['raster_geometry']['openings']=[{'id':'gap','points':[[10,35],[10,50]],'width_px':15,'wall_ids':['wall-a']}]
  self.assertEqual([e['id'] for e in raster.elements(self.a)],['wall-a'])
  self.correction(id='gap',points=None,action='accept',kind='door')
  door=next(e for e in raster.elements(self.a) if e['id']=='gap')
  self.assertEqual(door['kind'],'door');self.assertIn('stroke-width="6.0000"',door['svg'])
  self.correction(id='gap',points=None,action='accept',kind='open_transition')
  self.assertEqual([e['id'] for e in raster.elements(self.a)],['wall-a'])
  self.correction(action='undo')
  self.assertIn('door',[e['kind'] for e in raster.elements(self.a)])
 def test_revision_and_source_guards(self):
  for override in ({'revision':3},{'source_sha256':'wrong'},{'points':[[0,0],[101,12]]},{'points':[[0,0],[float('nan'),12]]}):
   before=copy.deepcopy(self.a)
   with self.assertRaises(ValueError):self.correction(**override)
   self.assertEqual(self.a,before)
 def test_save_failure_rolls_back(self):
  before=copy.deepcopy(self.a)
  with patch.object(self.st,'save',side_effect=OSError('Full disk')):
   with self.assertRaises(OSError):self.correction()
  self.assertEqual(self.a,before)
 def test_native_draft_exists_before_room_recognition(self):
  self.a.pop('raster_geometry');self.a['plan_source']={'vector':True,'metres_per_pixel':.02}
  self.a['drawing']={'features':[{'id':'wall-native','kind':'wall','points':[[10,10],[10,80]],'thickness':4}]}
  scene=raster.draft(self.st,self.p['id'],self.a['id'])
  self.assertGreater(len(scene['surfaces']),0);self.assertTrue(scene['partial'])
  self.assertIn('native',scene['floor']);self.assertEqual(self.p['rooms'],[])
 def test_partial_draft_cuts_supported_door_span_without_filling_it(self):
  self.a.pop('raster_geometry');self.a['drawing']={'features':[
   {'id':'wall','kind':'wall','points':[[10,10],[10,80]],'thickness':4},
   {'id':'door','kind':'door','points':[[10,35],[10,50]],'thickness':4}]}
  scene=raster.draft(self.st,self.p['id'],self.a['id'])
  door=[s for s in scene['surfaces'] if s['kind']=='door']
  self.assertTrue(door);self.assertGreaterEqual(min(p[2] for s in door for p in s['points']),2.2)
  self.assertEqual(len([s for s in scene['surfaces'] if s['kind']=='wall_candidate']),10)
 def test_draft_cannot_read_another_projects_plan(self):
  other=self.st.create_project('Other project')
  with self.assertRaises(ValueError):raster.draft(self.st,other['id'],self.a['id'])
 def test_partial_draft_cannot_claim_verification_or_invent_slab(self):
  scene=raster.draft(self.st,self.p['id'],self.a['id'])
  self.assertTrue(scene['partial']);self.assertFalse(scene['geometry_validated'])
  self.assertTrue(all(s['kind']!='floor' for s in scene['surfaces']))

class JobControlTests(unittest.TestCase):
 def engine(self):
  e=Mock();e.store.update_job.side_effect=lambda jid,**kw:kw;return e
 def test_interrupt_only_owned_running_prompt(self):
  e=self.engine();e.get.return_value={'queue_running':[[0,'ours']],'queue_pending':[]}
  job_control.cancel(e,{'id':'j','status':'running','prompt_id':'ours'})
  e.post.assert_called_once_with('/interrupt',{})
 def test_other_render_not_interrupted(self):
  e=self.engine();e.get.return_value={'queue_running':[[0,'theirs']],'queue_pending':[[1,'ours']]}
  job_control.cancel(e,{'id':'j','status':'queued','prompt_id':'ours'})
  e.post.assert_called_once_with('/queue',{'delete':['ours']})
 def test_ambiguous_submission_never_retried(self):
  e=self.engine();e.get.side_effect=[{'queue_running':[],'queue_pending':[]},{}]
  with self.assertRaises(ValueError):job_control.recover(e,{'id':'j','status':'failed','submission_intent':1})
  e.store.update_job.assert_not_called()
 def test_recover_matches_owned_history(self):
  e=self.engine();e.get.side_effect=[{'queue_running':[],'queue_pending':[]},{'p':{'prompt':[0,'p',{}, {'pixeloid_job_id':'j'}]}}]
  job={'id':'j','status':'failed','submission_intent':1};result=job_control.recover(e,job)
  self.assertEqual(job['prompt_id'],'p');self.assertEqual(result['status'],'queued')
 def test_cancelled_render_requires_new_version(self):
  with self.assertRaises(ValueError):job_control.recover(self.engine(),{'id':'j','status':'cancelled','prompt_id':'p'})

if __name__=='__main__':unittest.main()
