"""One-attempt image transport regression. Mock transport, no renderer contact."""
import json,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock
import requests
from store import Store
from engine import Engine
from remote_processing import RemoteEngine,WorkerResponseError
import project_storage,scene_control

class SingleImage(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.store=Store(self.tmp.name)
  self.project=self.store.create_project('isolated transport fixture');self.room=self.store.add_room(self.project['id'])
  self.job=self.store.new_job(self.project['id'],'image',self.room['id'],input_revision=self.room['revision'],single_submission=True,scene_ticket=scene_control.scene_snapshot(self.store,self.project,self.room),edit_ticket={'mode':'reference'})
  self.folder=project_storage.job_folder(self.store,self.job);self.folder.mkdir(parents=True,exist_ok=True)
  (self.folder/'remote-request.json').write_text(json.dumps({'id':self.job['id'],'kind':'image','graph':{}}));self.job['remote_job_id']=self.job['id']
  self.engine=RemoteEngine.__new__(RemoteEngine);Engine.__init__(self.engine,self.store,Path(__file__).resolve().parents[1]);self.engine.remote=Mock();self.engine.stop=Mock();self.engine.stop.is_set.return_value=False;self.engine.finish_render=Mock()
 def tearDown(self):self.tmp.cleanup()
 def missing(self):return WorkerResponseError('Worker job not found. No generation was started.',400)
 def test_lost_ack_reconciles_with_get_and_never_posts_twice(self):
  history={'outputs':{}};self.engine.remote.get.side_effect=[self.missing(),{'status':'completed'},history]
  self.engine.remote.post.side_effect=requests.ConnectionError('ack lost')
  self.engine.run_render(self.job)
  self.engine.remote.post.assert_called_once();self.engine.finish_render.assert_called_once()
  self.assertIn('remote_submission_intent',json.loads(self.store.path.read_text())['jobs'][self.job['id']])
 def test_missing_after_uncertain_submission_does_not_resubmit(self):
  self.engine.remote.get.side_effect=[self.missing(),self.missing()];self.engine.remote.post.side_effect=requests.ConnectionError('ack lost')
  with self.assertRaisesRegex(ValueError,'No second submission'):self.engine.run_render(self.job)
  self.engine.remote.post.assert_called_once()
 def test_saved_request_checks_current_scene_before_first_submission(self):
  self.room['revision']+=1;self.engine.remote.get.side_effect=self.missing()
  with self.assertRaisesRegex(ValueError,'inputs changed'):self.engine.run_render(self.job)
  self.engine.remote.post.assert_not_called()

if __name__=='__main__':unittest.main()
