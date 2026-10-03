"""Mac-only capture adapter tests; synthetic store and fake transport."""
import json,unittest,tempfile
from unittest.mock import Mock,patch
import test_remote_video as client_fixture
from remote_processing import WorkerResponseError
from video_capture import PROFILE
from video_workflow import PREVIEW
from worker_protocol import contract
from test_video_capture import ROOT,node_specs
from store import Store
from generation_phase import assert_dispatch
import project_storage

class CaptureAdapter(unittest.TestCase):
 def setUp(self):
  self.f=client_fixture.VideoClientTests();self.f.setUp();f=self.f;f.j.update(video_preset=PREVIEW,duration=2,motion='still',video_capture=PROFILE,generation_phase_id='fixture',single_submission=True)
  f.p['generation_phase']={'id':'fixture','status':'paused','allowed_job':{'kind':'video','video_capture':PROFILE},'continuing_job_ids':[f.j['id']]}
 def tearDown(self):self.f.tearDown()
 def test_old_worker_and_missing_loaded_extension_refused_before_upload(self):
  f=self.f;status={**contract(ROOT),'prepared':True};status.pop('video_capture');f.e.remote.get.return_value=status
  with self.assertRaisesRegex(ValueError,'capture support'):f.e.run_render(f.j)
  f.e.upload.assert_not_called();f.e.remote.post.assert_not_called()
  f.e.remote.get.side_effect=[{**contract(ROOT),'prepared':True},{}]
  with self.assertRaisesRegex(ValueError,'nodes unavailable'):f.e.run_render(f.j)
  f.e.upload.assert_not_called();f.e.remote.post.assert_not_called()
 def test_saved_request_and_reconnect_download_no_large_capture_files(self):
  f=self.f;f.e.stop=Mock();f.e.stop.is_set.return_value=False;f.e.finish_render=Mock()
  manifest={'profile':PROFILE,'job_id':f.j['id'],'state':'complete','mp4':{'sha256':'e'*64}}
  result={'id':f.j['id'],'status':'completed','outputs':{'e'*64:{'extension':'.mp4'}}};history={'outputs':{'42':{'pixeloid_capture':[manifest]}}}
  f.e.remote.get.side_effect=[{**contract(ROOT),'prepared':True},node_specs(),WorkerResponseError('Worker job not found.',400)]
  f.e.remote.post.return_value=result
  # Completion consumes the subsequent GET result.
  f.e.remote.get.side_effect=[{**contract(ROOT),'prepared':True},node_specs(),WorkerResponseError('Worker job not found.',400),history]
  f.e.run_render(f.j);f.e.remote.post.assert_called_once();f.e.finish_render.assert_called_once()
  folder=project_storage.job_folder(f.st,f.j);body=json.loads((folder/'remote-request.json').read_text());self.assertEqual(body['video_settings']['capture'],PROFILE)
  self.assertEqual(json.loads((folder/'capture-manifest.json').read_text()),manifest);self.assertIn('42',body['graph'])
  f.e.remote.reset_mock();f.e.remote.get.side_effect=[result,history];f.e.run_render(f.j);f.e.remote.post.assert_not_called();f.e.remote.request.assert_not_called()
 def test_normal_backend_route_records_capture_only_under_matching_phase(self):
  from server import Handler
  from types import SimpleNamespace
  f=self.f;f.j['status']='completed'
  h=Handler.__new__(Handler);h.server=SimpleNamespace(store=f.st,engine=Mock())
  route=['api','projects',f.p['id'],'rooms',f.r['id'],'generate-video']
  request={'video_preset':PREVIEW,'duration':2,'motion':'still','video_capture':PROFILE}
  with self.assertRaisesRegex(ValueError,'Generation paused'):h.route('POST',route,request)
  f.p['generation_phase']={'id':'new-fixture-only','status':'active','allowed_job':dict(kind='video',room_id=f.r['id'],source_image_id=f.a['id'],**request),'allowances':{'video_test':{'used':0,'limit':1}}}
  with patch('interior_style.map_ready',return_value=True):j=h.route('POST',route,request)
  self.assertEqual(j['video_capture'],PROFILE);self.assertTrue(j['single_submission']);self.assertEqual(f.p['generation_phase']['status'],'paused')
  h.server.engine.assert_not_called()
 def test_captured_video_installs_once_unapproved_with_verified_provenance(self):
  import hashlib
  from pathlib import Path
  from types import SimpleNamespace
  import test_video_preview as fixture
  from video_capture import capability
  f=self.f;f.e.build_video(f.j,f.root);f.j['output_node']='32'
  raw=fixture.PreviewClientTests.clip(SimpleNamespace(root=f.root)).read_bytes();sha=hashlib.sha256(raw).hexdigest()
  extension=ROOT/'capture_extension/pixeloid_preview_capture'
  hashes={name:hashlib.sha256((extension/name).read_bytes()).hexdigest() for name in ('__init__.py','runtime_sources.json')}
  manifest={'profile':PROFILE,'job_id':f.j['id'],'state':'complete','extension_sha256':hashes,'mp4':{'sha256':sha}}
  history={'outputs':{'32':{'images':[{'worker_asset':sha}]},'42':{'pixeloid_capture':[manifest]}}}
  f.e.remote.request.return_value=Mock(content=raw)
  f.e.finish_render(f.j,history,f.root);aid=f.j['result_asset_id'];f.e.finish_render(f.j,history,f.root)
  self.assertEqual(f.r['videos'],[aid]);a=f.st.asset(aid);self.assertEqual(a['status'],'review');self.assertEqual(a['video_provenance']['capture'],capability(ROOT))
  manifest['extension_sha256']['__init__.py']='wrong'
  with self.assertRaisesRegex(ValueError,'provenance differs'):f.e.finish_render(f.j,history,f.root)
class CapturePhase(unittest.TestCase):
 def test_one_attempt_capture_requires_new_matching_phase_without_reset(self):
  with tempfile.TemporaryDirectory() as tmp:
   s=Store(tmp);p=s.create_project('Fixture');r=s.add_room(p['id']);kw=dict(source_image_id='source',view_id='view',video_preset=PREVIEW,duration=2,motion='still',video_capture=PROFILE)
   with self.assertRaisesRegex(ValueError,'explicitly authorised'):s.new_job(p['id'],'video',r['id'],**kw)
   spec=dict(kind='video',room_id=r['id'],**kw);p['generation_phase']={'id':'fixture-capture','status':'active','allowed_job':spec,'allowances':{'video_test':{'used':0,'limit':1}}}
   with self.assertRaises(ValueError):s.new_job(p['id'],'video',r['id'],**{k:v for k,v in kw.items() if k!='video_capture'})
   j=s.new_job(p['id'],'video',r['id'],**kw);assert_dispatch(s,j);self.assertTrue(j['single_submission']);self.assertEqual(p['generation_phase']['allowances']['video_test']['used'],1)
   self.assertEqual(p['generation_phase']['status'],'paused')
   with self.assertRaises(ValueError):s.new_job(p['id'],'video',r['id'],**kw)
   with self.assertRaises(ValueError):assert_dispatch(s,{**j,'video_capture':'changed'})

if __name__=='__main__':unittest.main()
