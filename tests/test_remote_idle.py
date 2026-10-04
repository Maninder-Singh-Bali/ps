"""Mac-only checks: the PC client is a mock, including explicit checks."""
import tempfile,threading,unittest
from pathlib import Path
from unittest.mock import Mock,patch
import requests
from server import make_server
from worker_protocol import contract

ROOT=Path(__file__).resolve().parents[1]

class RemoteIdleTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.remote=Mock()
        self.client_patch=patch('remote_processing.Client',return_value=self.remote);self.client_patch.start()
        self.server=make_server(self.tmp.name,port=0,start_worker=False,remote_config='unused-fixture')
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.http=requests.Session();self.http.trust_env=False
        self.base='http://127.0.0.1:'+str(self.server.server_port)
    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join();self.client_patch.stop();self.tmp.cleanup()
    def get(self,path):
        r=self.http.get(self.base+path,timeout=2);r.raise_for_status();return r.json()
    def test_idle_polling_and_setup_never_contact_pc(self):
        for _ in range(4):
            self.assertIsNone(self.get('/api/state')['engine']['checked'])
            self.assertEqual(self.get('/api/studio/status')['state'],'Local design')
            self.assertIsNone(self.get('/api/health')['checked'])
            self.assertIsNone(self.get('/api/local-setup')['worker']['checked'])
        self.assertEqual(self.remote.mock_calls,[])
    def test_explicit_check_once_then_cached_without_fake_freshness(self):
        self.remote.request.return_value.json.return_value={**contract(ROOT),'video':True,'prepared':True,'checks':[],'state':'Ready','active_jobs':0}
        result=self.get('/api/studio/status?check=1')
        self.remote.request.assert_called_once_with('GET','/v1/status',timeout=5)
        self.assertTrue(result['video_compatible']);self.assertFalse(result['cached']);stamp=result['checked']
        for _ in range(3):
            s=self.get('/api/studio/status');self.assertEqual(s['checked'],stamp);self.assertTrue(s['cached'])
            self.assertEqual(self.get('/api/state')['engine']['checked'],stamp)
        self.remote.request.assert_called_once()
        with patch('remote_processing.time.time',return_value=stamp+31):
            self.assertFalse(self.server.engine.health()['connected'])
            self.assertTrue(self.server.services.snapshot()['stale'])
        self.remote.request.assert_called_once()
    def test_failed_explicit_check_does_not_retry_during_polls(self):
        self.remote.request.side_effect=requests.ConnectionError('fixture offline')
        result=self.get('/api/studio/status?check=1');self.assertFalse(result['reachable'])
        for _ in range(3):self.get('/api/state');self.get('/api/studio/status')
        self.remote.request.assert_called_once();self.remote.post.assert_not_called()
    def test_job_lane_remains_enabled_and_live_health_is_explicit(self):
        self.assertTrue(self.server.services.prepared)
        self.remote.request.side_effect=requests.ConnectionError('fixture offline')
        self.assertFalse(self.server.engine.health(force=True)['connected'])
        self.remote.request.assert_called_once()

if __name__=='__main__':unittest.main()
