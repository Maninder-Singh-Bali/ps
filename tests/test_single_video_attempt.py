import copy,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock
import requests
from store import Store
from generation_phase import assert_dispatch
from job_control import recover
from remote_processing import WorkerResponseError
from worker_protocol import contract
from test_remote_video import VideoClientTests,ROOT

class BoundedPhase(unittest.TestCase):
 def test_atomic_allowance_and_scope_survive_restart(self):
  with tempfile.TemporaryDirectory() as tmp:
   s=Store(tmp);p=s.create_project('Fixture');r=s.add_room(p['id'])
   spec=dict(kind='video',room_id=r['id'],source_image_id='source',view_id='view',video_preset='ltx-preview-768x432-2s-v1',duration=2,motion='still')
   p['generation_phase']={'id':'one','status':'active','allowed_job':spec,'allowances':{'video_test':{'used':0,'limit':1}}};s.save();before=copy.deepcopy(s.db)
   for kind in ('image','reference'):
    with self.assertRaises(ValueError):s.new_job(p['id'],kind,r['id'])
   kw={k:v for k,v in spec.items() if k not in ('kind','room_id')}
   with self.assertRaises(ValueError):s.new_job(p['id'],'video',r['id'],**{**kw,'duration':8})
   self.assertEqual(s.db,before)
   j=s.new_job(p['id'],'video',r['id'],**kw);assert_dispatch(s,j)
   self.assertEqual(p['generation_phase']['status'],'paused');self.assertEqual(p['generation_phase']['allowances']['video_test']['used'],1)
   again=Store(tmp);assert_dispatch(again,again.db['jobs'][j['id']])
   with self.assertRaises(ValueError):again.new_job(p['id'],'video',r['id'],**kw)
   with self.assertRaises(ValueError):assert_dispatch(again,{**j,'source_image_id':'other'})
   with self.assertRaises(ValueError):recover(Mock(store=again),{**j,'status':'failed'})

class SinglePost(unittest.TestCase):
 def setUp(self):
  self.f=VideoClientTests();self.f.setUp();self.f.j['single_submission']=True;self.f.e.stop=Mock();self.f.e.stop.is_set.return_value=False
 def tearDown(self):self.f.tearDown()
 def test_lost_response_and_missing_job_never_posts_twice(self):
  f=self.f;missing=WorkerResponseError('Worker job not found. No generation was started.',400)
  f.e.remote.get.side_effect=[{**contract(ROOT),'prepared':True},missing,missing]
  f.e.remote.post.side_effect=requests.ConnectionError('unknown result')
  with self.assertRaisesRegex(ValueError,'No second submission'):f.e.run_render(f.j)
  f.e.remote.post.assert_called_once();self.assertTrue(f.j['remote_submission_intent'])
 def test_lost_response_reconnects_existing_job_without_resubmit(self):
  f=self.f;complete={'id':f.j['id'],'status':'completed'};history={'outputs':{}}
  f.e.remote.get.side_effect=[{**contract(ROOT),'prepared':True},WorkerResponseError('Worker job not found.',400),complete,history]
  f.e.remote.post.side_effect=requests.ConnectionError('accepted, reply lost');f.e.finish_render=Mock()
  f.e.run_render(f.j);f.e.remote.post.assert_called_once();f.e.finish_render.assert_called_once()
if __name__=='__main__':unittest.main()
