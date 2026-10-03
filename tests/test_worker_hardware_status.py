"""Worker-only timestamp checks with no hardware/service queries."""
import tempfile,unittest,threading
from pathlib import Path
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import Mock
from hardware_status import sample,describe
from processing_services import Services

class WorkerHardwareTests(unittest.TestCase):
    def test_sample_units_timestamp_and_cached_snapshot(self):
        check=sample(36.7,.9);stamp=check['measured_at']
        self.assertIsNotNone(datetime.fromisoformat(stamp).tzinfo)
        self.assertIn(stamp,check['detail']);self.assertIn('GiB',check['detail']);self.assertNotIn('currently',check['detail'])
        with tempfile.TemporaryDirectory() as d:
            engine=Mock();engine.store=SimpleNamespace(db={'jobs':{}});engine.health.return_value={'connected':True}
            manager=Services(engine,Path(d));manager.checks=[check];manager.prepared=True
            self.assertEqual(manager.snapshot()['checks'][0]['measured_at'],stamp)
            self.assertEqual(manager.snapshot()['checks'][0]['measured_at'],stamp)
            engine.post.assert_not_called()
    def test_old_sample_timestamp_is_not_invented(self):
        c=describe({'name':'Hardware','detail':'36.7 GB RAM and 0.9 GB VRAM currently free.'})
        self.assertNotIn('measured_at',c);self.assertIn('time unavailable',c['detail']);self.assertIn('0.9 GiB',c['detail']);self.assertTrue(c['cached'])

if __name__=='__main__':unittest.main()
