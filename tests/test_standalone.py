import sys,json,tempfile,time,unittest
from pathlib import Path
from unittest.mock import Mock,patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import standalone

class StandaloneTests(unittest.TestCase):
    def test_reuses_running_renderer_without_launch(self):
        engine=Mock();engine.health.return_value={'connected':True}
        with patch.object(standalone.subprocess,'Popen') as launch:
            self.assertEqual(standalone.start_renderer(engine)['state'],'connected');launch.assert_not_called()
    def test_nonlocal_address_rejected(self):
        for value in ('https://localhost:8190','http://example.com','http://user:pass@127.0.0.1:8190','http://127.0.0.1:8190/path'):
            with self.assertRaises(ValueError):standalone.renderer_address(value)
    def test_no_false_stall_while_recent_or_waiting(self):
        stamp=time.time();job={'id':'a','status':'running','prompt_id':'p','started':stamp-20}
        self.assertEqual(standalone.job_findings({'a':job},{'queue_running':[],'queue_pending':[]},stamp),[])
        job['started']=stamp-650
        messages=standalone.job_findings({'a':job},{'queue_running':[[1,'p']],'queue_pending':[]},stamp)
        self.assertIn('may be loading',messages[0]['detail']);self.assertEqual(job['status'],'running')
    def test_requirements_include_protected_edits_and_both_models(self):
        types,models=standalone.workflow_requirements(Path(__file__).resolve().parents[1])
        self.assertIn('ImageCompositeMasked',types);self.assertTrue(any('ltx' in m[2] for m in models));self.assertTrue(any('flux' in m[2].lower() for m in models))
