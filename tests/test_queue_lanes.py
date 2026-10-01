import tempfile,threading,time,unittest
from pathlib import Path
from unittest.mock import patch
from engine import Engine
from store import Store

class QueueLanes(unittest.TestCase):
    def test_blocked_model_does_not_block_cpu_and_each_lane_is_serial(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            st=Store(directory);p=st.create_project('Queue test');engine=Engine(st,Path(__file__).parents[1])
            model=st.new_job(p['id'],'image');second=st.new_job(p['id'],'video')
            gpu_started=threading.Event();release=threading.Event();cpu_done=threading.Event();counts={'gpu':0,'cpu':0};peaks=counts.copy()
            def work(job,lane):
                counts[lane]+=1;peaks[lane]=max(peaks[lane],counts[lane])
                if lane=='gpu':gpu_started.set();release.wait(5)
                else:time.sleep(.01)
                st.update_job(job['id'],status='completed');counts[lane]-=1
                if lane=='cpu':cpu_done.set()
            engine.run_render=lambda job:work(job,'gpu');st.db['settings']['auto_release']=False
            with patch('raster_reconstruction.run',side_effect=lambda e,j:work(j,'cpu')),patch('engine.memory_headroom',return_value=(10,10)):
                t=threading.Thread(target=engine.worker);t.start()
                try:
                    self.assertTrue(gpu_started.wait(2));engine.worker() # duplicate startup is harmless
                    cpu=st.new_job(p['id'],'raster_reconstruction',plan_id='a')
                    st.new_job(p['id'],'raster_reconstruction',plan_id='b')
                    self.assertTrue(cpu_done.wait(2));self.assertEqual(model['status'],'running')
                    self.assertEqual(cpu['lane'],'cpu');self.assertLess(cpu['queue_wait_seconds'],2)
                finally:release.set();engine.stop.set();t.join(3);engine.session.close()
                self.assertLessEqual(peaks['cpu'],1);self.assertLessEqual(peaks['gpu'],1)
    def test_snapshot_is_detached_and_readonly(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            st=Store(directory);p=st.create_project('Original');view=st.review_snapshot()
            view.project(p['id'])['name']='Modified'
            self.assertEqual(st.project(p['id'])['name'],'Original')
            with self.assertRaises(RuntimeError):view.save()
