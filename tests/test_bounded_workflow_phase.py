import copy,tempfile,unittest
from pathlib import Path
from store import Store
from generation_phase import assert_dispatch
from job_control import recover
from types import SimpleNamespace
class BoundedWorkflowTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.st=Store(Path(self.tmp.name));self.p=self.st.create_project('Disposable phase fixture');self.r=self.st.add_room(self.p['id'])
  scope={'room_id':self.r['id'],'input_revision':1,'view_id':'camera1','scene_fingerprint':'exact-scene'}
  self.p['generation_phase']={'id':'new-test','status':'active','allowed_jobs':{'image':scope,'video':{**scope,'video_preset':'ltx-preview-768x432-2s-v1','duration':2,'motion':'still'}},'allowances':{'image':{'used':0,'limit':1},'video':{'used':0,'limit':1},'reference':{'used':0,'limit':0}},'continuing_job_ids':[]};self.st.save()
 def tearDown(self):self.tmp.cleanup()
 def create(self,kind='image',**kw):
  return self.st.new_job(self.p['id'],kind,self.r['id'],**{'input_revision':1,'view_id':'camera1','scene_ticket':{'fingerprint':'exact-scene'},**kw})
 def source(self):
  j=self.create();j['status']='completed';self.st.db['assets']['image1']={'id':'image1','job_id':j['id'],'project_id':self.p['id'],'path':str(self.st.path)};return j
 def test_reserves_once_and_pauses_after_both(self):
  image=self.source()
  with self.assertRaises(ValueError):self.create()
  video=self.create('video',source_image_id='image1',duration=2,motion='still',video_preset='ltx-preview-768x432-2s-v1')
  self.assertEqual(self.p['generation_phase']['status'],'paused')
  self.assertTrue(image['single_submission']);assert_dispatch(self.st,video)
  self.st.save();assert_dispatch(Store(self.st.root),video)
  with self.assertRaises(ValueError):self.create('video')
 def test_reference_and_different_scene_never_consume(self):
  for kind,kw in [('reference',{}),('image',{'input_revision':2}),('image',{'view_id':'other'}),('image',{'scene_ticket':{'fingerprint':'changed'}}),('image',{'video_capture':'capture'})]:
   before=copy.deepcopy(self.st.db)
   with self.assertRaises(ValueError):self.create(kind,**kw)
   self.assertEqual(before,self.st.db)
 def test_old_or_failed_image_is_rejected(self):
  self.st.db['assets']['old']={'id':'old','job_id':'old-job','project_id':self.p['id'],'path':str(self.st.path)}
  with self.assertRaises(ValueError):self.create('video',source_image_id='old',duration=2,motion='still',video_preset='ltx-preview-768x432-2s-v1')
  image=self.source();image['status']='failed'
  with self.assertRaises(ValueError):self.create('video',source_image_id='image1',duration=2,motion='still',video_preset='ltx-preview-768x432-2s-v1')
 def test_no_capture_wrong_preset_or_retry(self):
  image=self.source()
  for kw in [{'video_preset':'ltx-native-1080p-v1'},{'motion':'orbit'},{'video_capture':'capture'},{'duration':5}]:
   with self.assertRaises(ValueError):self.create('video',**{'source_image_id':'image1','duration':2,'motion':'still','video_preset':'ltx-preview-768x432-2s-v1',**kw})
  with self.assertRaises(ValueError):recover(SimpleNamespace(store=self.st),image)
  image['scene_ticket']['fingerprint']='changed'
  with self.assertRaises(ValueError):assert_dispatch(self.st,image)
if __name__=='__main__':unittest.main()
