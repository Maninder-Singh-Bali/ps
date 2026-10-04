import unittest
from datetime import datetime
from unittest.mock import Mock
from types import SimpleNamespace
from pathlib import Path
from hardware_status import sample,describe
from remote_processing import RemoteServices
from worker_protocol import contract

class HardwareStatusTests(unittest.TestCase):
    def test_new_sample_is_timestamped_and_explicitly_cached(self):
        c=sample(36.7,.9)
        self.assertIsNotNone(datetime.fromisoformat(c['measured_at']).tzinfo)
        self.assertIn(c['measured_at'],c['detail']);self.assertIn('GiB',c['detail'])
        self.assertNotIn('currently',c['detail']);self.assertTrue(c['cached'])
        self.assertEqual(describe(c),c)
    def test_legacy_reading_has_unknown_time_not_poll_time(self):
        c=describe({'name':'Hardware','detail':'36.7 GB RAM and 0.9 GB VRAM currently free.'})
        self.assertNotIn('measured_at',c);self.assertIn('Measurement time unavailable',c['detail'])
        self.assertIn('0.9 GiB',c['detail']);self.assertIn('not live',c['detail'])
    def test_adapter_does_not_refresh_or_mutate_remote_sample(self):
        root=Path(__file__).resolve().parents[1]
        remote=Mock();old={'name':'Hardware','detail':'36.7 GB RAM and 0.9 GB VRAM currently free.'}
        remote.request.return_value.json.return_value={**contract(root),'video':True,'checks':[old]}
        services=RemoteServices(SimpleNamespace(remote=remote,app_root=root))
        self.assertIsNone(services.snapshot()['checked']);remote.request.assert_not_called()
        result=services.snapshot(force=True)
        self.assertTrue(result['video_compatible']);self.assertIn('GiB',result['checks'][0]['detail'])
        self.assertIn('currently',old['detail'])
        cached=services.snapshot();self.assertTrue(cached['cached']);self.assertEqual(cached['checks'],result['checks'])
        result['checks'][0]['detail']='caller mutation'
        self.assertIn('GiB',services.snapshot()['checks'][0]['detail'])
        remote.request.assert_called_once_with('GET','/v1/status',timeout=5);remote.post.assert_not_called()

if __name__=='__main__':unittest.main()
