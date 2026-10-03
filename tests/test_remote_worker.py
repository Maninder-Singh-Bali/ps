import copy, io, json, tempfile, unittest, zipfile
from pathlib import Path
from unittest.mock import Mock,patch
from PIL import Image
from worker_service import Worker
from worker_protocol import contract,validate
from store import Store
from portable_project import export_project,import_project
from engine import Engine

ROOT=Path(__file__).resolve().parents[1]
class WorkerTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.w=Worker(ROOT,self.tmp.name,'http://127.0.0.1:8191')
  self.w.engine.validate_graph=Mock();self.w.engine.get=Mock(return_value={'queue_running':[],'queue_pending':[]})
  self.w.engine.post=Mock();self.w.watch=Mock();self.w.services.prepared=True
  patcher=patch('worker_service.memory_headroom',return_value=(32,40));patcher.start();self.addCleanup(patcher.stop)
  self.body={**contract(ROOT),'id':'a'*16,'kind':'image','output_node':'1','graph':{'1':{'class_type':'SaveImage','inputs':{'images':['2',0],'filename_prefix':'../../unsafe'}}}}
 def tearDown(self):self.tmp.cleanup()
 def test_idempotency_conflict_and_restart(self):
  self.w.submit(self.body);self.w.submit(self.body)
  self.assertEqual(len(self.w.store.db['jobs']),1)
  b=copy.deepcopy(self.body);b['output_node']='2'
  with self.assertRaisesRegex(ValueError,'different'):self.w.submit(b)
  w2=Worker(ROOT,self.tmp.name,'http://127.0.0.1:8191')
  self.assertEqual(w2.submit(self.body)['id'],self.body['id'])
 def test_paths_and_code_nodes_are_not_exposed(self):
  g=validate(ROOT,self.body,{})
  self.assertTrue(g['1']['inputs']['filename_prefix'].startswith('Pixeloid_Worker/'))
  for cls in ('PythonExec','LoadImage'):
   b=copy.deepcopy(self.body);b['graph']['1']={'class_type':cls,'inputs':{'image':'C:/secret.png'}}
   with self.assertRaises(ValueError):validate(ROOT,b,{})
 def test_version_mismatch(self):
  self.body['protocol']=999
  with self.assertRaisesRegex(ValueError,'mismatch'):self.w.submit(self.body)
 def test_pause_does_not_cancel_current_and_no_duplicate_submit(self):
  self.w.submit(self.body);self.w.action('pause');self.w.tick();self.w.engine.post.assert_not_called()
  self.w.action('resume');j=self.w.store.db['jobs'][self.body['id']]
  self.w.engine.post.return_value={'prompt_id':j['comfy_id']}
  self.w.tick();self.assertEqual(j['attempts'],1)
  self.w.engine.get.side_effect=lambda r: {} if r.startswith('/history') else {'queue_running':[[0,j['comfy_id'],{},{}]],'queue_pending':[]}
  self.w.action('pause');self.w.tick();self.assertEqual(j['status'],'running');self.assertEqual(self.w.engine.post.call_count,1)
 def test_unknown_submission_is_interrupted_never_rerun(self):
  self.w.submit(self.body);j=self.w.store.db['jobs'][self.body['id']]
  j.update(status='submitting',submission_intent=1,attempts=1)
  self.w.engine.get.side_effect=lambda r: {} if r.startswith('/history') else {'queue_running':[],'queue_pending':[]}
  self.w.tick();self.assertEqual(j['status'],'interrupted');self.w.engine.post.assert_not_called()
 def test_surviving_job_is_reconciled_after_worker_restart(self):
  self.w.submit(self.body);j=self.w.store.db['jobs'][self.body['id']]
  j.update(status='running',submission_intent=1,prompt_id=j['comfy_id'],attempts=1);self.w.store.save()
  w2=Worker(ROOT,self.tmp.name,'http://127.0.0.1:8191');w2.engine.post=Mock()
  w2.engine.get=Mock(side_effect=lambda r:{} if r.startswith('/history') else {'queue_running':[[0,j['comfy_id'],{},{}]],'queue_pending':[]})
  w2.tick();self.assertEqual(w2.job(j['id'])['status'],'running');w2.engine.post.assert_not_called()
 def test_only_targeted_cancellation(self):
  self.w.submit(self.body);j=self.w.store.db['jobs'][self.body['id']];j.update(status='running',submission_intent=1,prompt_id=j['comfy_id'])
  self.w.engine.get.side_effect=lambda r: {} if r.startswith('/history') else {'queue_running':[[0,j['comfy_id'],{},{}]],'queue_pending':[]}
  self.w.cancel(j['id']);self.w.engine.post.assert_any_call('/interrupt',{'prompt_id':j['comfy_id']})
 def test_upload_content_address_and_dedup(self):
  im=io.BytesIO();Image.new('RGB',(8,8),'red').save(im,format='PNG');self.w.engine.upload=Mock(return_value='safe.png')
  a=self.w.upload(im.getvalue());b=self.w.upload(im.getvalue());self.assertEqual(a,b);self.w.engine.upload.assert_called_once()
 def test_external_services_are_never_stopped(self):
  self.w.engine.health=Mock(return_value={'connected':True})
  with self.assertRaisesRegex(ValueError,'[Ee]xternal'):self.w.action('stop')

class PortableTests(unittest.TestCase):
 def test_retrieving_completed_output_twice_preserves_one_child(self):
  with tempfile.TemporaryDirectory() as d:
   st=Store(d);p=st.create_project('Reconnect');r=st.add_room(p['id']);j=st.new_job(p['id'],'image',r['id'],input_revision=r['revision'],seed=1,output_node='24',source_image_id='preserved-parent')
   engine=Engine(st,ROOT);raw=io.BytesIO();Image.new('RGB',(1920,1080)).save(raw,format='PNG');engine.download_output=Mock(return_value=raw.getvalue())
   history={'outputs':{'24':{'images':[{'worker_asset':'x'}]}}}
   engine.finish_render(j,history,Path(d));first=j['result_asset_id'];engine.finish_render(j,history,Path(d))
   self.assertEqual(j['result_asset_id'],first);self.assertEqual(r['images'],[first]);self.assertEqual(st.asset(first)['status'],'review');self.assertEqual(st.asset(first)['source_image_id'],'preserved-parent')
 def test_copy_import_and_no_overwrite(self):
  with tempfile.TemporaryDirectory() as d:
   d=Path(d);st=Store(d/'source');p=st.create_project('Private test');other=st.create_project('Exclude')
   image=d/'test.png';Image.new('RGB',(8,8)).save(image)
   st.db['assets']['a']={'id':'a','project_id':p['id'],'path':str(image),'kind':'image','source_image_id':'parent','status':'review'};st.save()
   z=d/'private.zip';export_project(st.path,p['id'],z);import_project(z,d/'restored');new=Store(d/'restored')
   self.assertEqual(list(new.db['projects']),[p['id']]);self.assertEqual(new.db['assets']['a']['source_image_id'],'parent')
   self.assertTrue(Path(new.db['assets']['a']['path']).is_file())
   with self.assertRaisesRegex(ValueError,'NEW'):import_project(z,d/'restored')
 def test_traversal_rejected_before_writes(self):
  with tempfile.TemporaryDirectory() as d:
   d=Path(d);z=d/'bad.zip'
   with zipfile.ZipFile(z,'w') as f:
    f.writestr('project.json',json.dumps({'format':'Pixeloid private portable project v1','project':{'id':'a'*16}}));f.writestr('../evil','x')
   with self.assertRaisesRegex(ValueError,'Unsafe'):import_project(z,d/'out')
   self.assertFalse((d/'out').exists())

if __name__=='__main__':unittest.main()
