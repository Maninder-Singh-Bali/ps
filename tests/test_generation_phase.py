import copy, tempfile, unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
from store import Store
from engine import Engine
from remote_processing import RemoteEngine
from job_control import recover
from generation_phase import assert_dispatch, MESSAGE
from server import Handler

class PhaseTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.st=Store(Path(self.tmp.name));self.p=self.st.create_project('Paused');self.r=self.st.add_room(self.p['id']);self.other=self.st.create_project('Other')
  self.active=self.st.new_job(self.p['id'],'image',self.r['id'])
  self.p['generation_phase']={'id':'bounded-test','status':'paused','allowances':{'table':{'used':2,'limit':2}},'continuing_job_ids':[self.active['id']]};self.st.save()
  self.engine=Mock(store=self.st);self.h=Handler.__new__(Handler);self.h.server=SimpleNamespace(store=self.st,engine=self.engine)
 def tearDown(self):self.tmp.cleanup()
 def test_all_http_submission_routes_block_before_any_mutation_or_dispatch(self):
  before=copy.deepcopy(self.st.db)
  for action in ('generate-image','generate-video','generate-reference'):
   with self.assertRaisesRegex(ValueError,'Generation paused'):
    self.h.route('POST',['api','projects',self.p['id'],'rooms',self.r['id'],action],{'prompt':'synthetic reference'})
  self.assertEqual(before,self.st.db);self.assertEqual(self.engine.mock_calls,[])
 def test_store_entrypoints_restart_and_unrelated_projects(self):
  st=Store(self.st.root);before=copy.deepcopy(st.db)
  for kind in ('image','video','reference'):
   with self.assertRaisesRegex(ValueError,'Generation paused'):st.new_job(self.p['id'],kind,self.r['id'])
  self.assertEqual(before,st.db)
  self.assertEqual(st.new_job(self.other['id'],'reference')['status'],'queued')
  self.assertEqual(st.new_job(self.p['id'],'raster_reconstruction')['status'],'queued')
 def test_dispatch_and_retry_cannot_bypass_guard(self):
  job={'id':'not-admitted','kind':'image','project_id':self.p['id'],'status':'failed'}
  for cls in (Engine,RemoteEngine):
   engine=cls.__new__(cls);engine.store=self.st;engine.remote=Mock();engine.ensure_renderer=Mock();engine.build_image=Mock()
   before=copy.deepcopy(self.st.db)
   with self.assertRaisesRegex(ValueError,'Generation paused'):engine.run_render(job)
   with self.assertRaisesRegex(ValueError,'Generation paused'):recover(engine,job)
   self.assertEqual(before,self.st.db);self.assertEqual(engine.remote.mock_calls,[]);engine.ensure_renderer.assert_not_called();engine.build_image.assert_not_called()
 def test_existing_active_jobs_continue_and_no_http_resume(self):
  assert_dispatch(self.st,self.active)
  phase=copy.deepcopy(self.p['generation_phase'])
  self.h.route('PATCH',['api','projects',self.p['id']],{'generation_phase':{'status':'active'}})
  self.assertEqual(self.p['generation_phase'],phase)

class HTTPPhaseTests(unittest.TestCase):
 def test_real_http_endpoints_do_not_create_jobs_or_call_worker(self):
  import threading, requests
  from server import make_server
  with tempfile.TemporaryDirectory() as folder:
   server=make_server(Path(folder),0,False);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
   st=server.store;p=st.create_project('Paused HTTP fixture');r=st.add_room(p['id']);p['generation_phase']={'status':'paused','continuing_job_ids':[]};st.save()
   server.engine.run_render=Mock();server.engine.post=Mock();server.engine.upload=Mock();before=copy.deepcopy(st.db)
   client=requests.Session();client.trust_env=False
   try:
    for action in ('generate-image','generate-reference','generate-video'):
     response=client.post(f'http://127.0.0.1:{server.server_port}/api/projects/{p["id"]}/rooms/{r["id"]}/{action}',json={'prompt':'fixture only'},timeout=5)
     self.assertEqual(response.status_code,400);self.assertEqual(response.json()['error'],MESSAGE)
    self.assertEqual(st.db,before)
    server.engine.run_render.assert_not_called();server.engine.post.assert_not_called();server.engine.upload.assert_not_called()
   finally:client.close();server.shutdown();server.server_close()

if __name__=='__main__':unittest.main()
