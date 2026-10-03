import tempfile, threading, unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
from processing_services import Services

class ServiceTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory()
  self.engine=Mock();self.engine.store=SimpleNamespace(db={'jobs':{},'settings':{}})
  self.engine.stop=threading.Event();self.engine.health.return_value={'connected':True}
  self.engine.get.return_value={'queue_running':[],'queue_pending':[]}
  self.services=Services(self.engine,Path(self.tmp.name));self.services.prepared=True
 def tearDown(self):self.tmp.cleanup()
 def test_reused_external_renderer_cannot_be_released_or_stopped(self):
  for action in (self.services.release,self.services.stop_services):
   with self.assertRaisesRegex(ValueError,'[Ee]xternal'):action()
  self.engine.post.assert_not_called()
 def test_owned_idle_service_stop_keeps_dashboard_running(self):
  process=Mock();process.poll.return_value=None;self.services.process=process
  self.services.stop_services();process.terminate.assert_called_once();process.wait.assert_called_once()
  self.assertFalse(self.engine.stop.is_set());self.assertFalse(self.services.prepared)
 def test_active_app_or_external_queue_blocks_stop(self):
  process=Mock();process.poll.return_value=None;self.services.process=process
  self.engine.store.db['jobs']['x']={'status':'running'}
  with self.assertRaisesRegex(ValueError,'active'):self.services.stop_services()
  self.engine.store.db['jobs'].clear();self.engine.get.return_value={'queue_running':[1],'queue_pending':[]}
  with self.assertRaisesRegex(ValueError,'active'):self.services.stop_services()
  process.terminate.assert_not_called()
 def test_readiness_does_not_survive_service_loss(self):
  self.engine.health.return_value={'connected':False}
  self.assertEqual(self.services.snapshot()['state'],'Error');self.assertFalse(self.services.prepared)
 def test_repeated_prepare_does_not_launch_second_thread(self):
  self.services.preparing=True
  with patch('processing_services.threading.Thread') as thread:self.services.prepare();thread.assert_not_called()
 def test_model_switch_releases_only_owned_idle_renderer(self):
  self.services.before_model({'kind':'image'});self.engine.post.assert_not_called()
  process=Mock();process.poll.return_value=None;self.services.process=process
  self.services.before_model({'kind':'video'});self.engine.post.assert_called_once_with('/free',{'unload_models':True,'free_memory':True})
 def test_no_processing_before_prepare_or_after_disconnect(self):
  self.services.prepared=False
  with self.assertRaisesRegex(ValueError,'Prepare Studio'):self.services.before_model({'kind':'image'})
  self.services.prepared=True;self.engine.health.return_value={'connected':False}
  with self.assertRaisesRegex(ValueError,'disconnected'):self.services.before_model({'kind':'image'})

if __name__=='__main__':unittest.main()
