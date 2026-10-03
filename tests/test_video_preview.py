"""Mac adapter/API/output checks using synthetic data and fake transport only."""
import json,hashlib,unittest
from pathlib import Path
from unittest.mock import Mock
import av,numpy as np
import test_remote_video as client_fixture
import test_studio as http_fixture
from video_workflow import PREVIEW,NATIVE,provenance
from worker_protocol import contract
from video_checks import inspect
import project_storage

class PreviewClientTests(unittest.TestCase):
    setUp=client_fixture.VideoClientTests.setUp
    tearDown=client_fixture.VideoClientTests.tearDown
    def configure(self):self.j.update(video_preset=PREVIEW,duration=2,motion='still')
    def clip(self,name='clip.mp4',size=(768,432),frames=48,fps=24):
        path=self.root/name
        with av.open(str(path),'w') as c:
            stream=c.add_stream('libx264',rate=fps);stream.width,stream.height=size;stream.pix_fmt='yuv420p';stream.options={'preset':'ultrafast','crf':'30'}
            pixels=np.full((size[1],size[0],3),255,dtype=np.uint8)
            for _ in range(frames):
                for packet in stream.encode(av.VideoFrame.from_ndarray(pixels,format='rgb24')):c.mux(packet)
            for packet in stream.encode():c.mux(packet)
        return path
    def test_build_source_identity_and_output_provenance(self):
        self.configure();before=Path(self.a['path']).read_bytes();g,_=self.e.build_video(self.j,self.root)
        self.assertEqual(before,Path(self.a['path']).read_bytes());self.assertEqual(g['9']['inputs']['image'],['37',0])
        self.assertTrue(self.j['scene_manifest']['preservation']['source_resize'])
        self.assertEqual(self.j['seed'],2909202661)
        self.j['output_node']='32';raw=self.clip().read_bytes();aid=hashlib.sha256(raw).hexdigest();self.e.remote.request.return_value=Mock(content=raw)
        history={'outputs':{'32':{'images':[{'worker_asset':aid}]}}}
        self.e.finish_render(self.j,history,self.root);first=self.j['result_asset_id'];self.e.finish_render(self.j,history,self.root)
        a=self.st.asset(first);self.assertEqual(self.r['videos'],[first]);self.assertEqual(a['status'],'review');self.assertFalse(self.r.get('approved_video_id'))
        self.assertEqual(a['native_sampling'],[768,448]);self.assertEqual([a['width'],a['height']],[768,432]);self.assertFalse(a['output_upscaled'])
        self.assertEqual(a['source_image_id'],self.a['id']);self.assertEqual(a['video_preset'],PREVIEW)
        p=json.loads((self.root/'resolution-provenance.json').read_text());self.assertEqual(p['retained_frame_indices'],[0,47]);self.assertFalse(p['native_1080p']);self.assertFalse(p['protected_composite'])
        self.assertEqual(self.j['video_check']['frames_decoded'],48);self.assertTrue(self.j['video_check']['edge_comparison_source']['resized'])
    def test_wrong_geometry_rate_count_and_native_mislabelling_rejected(self):
        for name,size,frames,fps in [('count.mp4',(768,432),49,24),('fps.mp4',(768,432),48,12),('size.mp4',(768,448),48,24)]:
            path=self.clip(name,size,frames,fps)
            with self.assertRaises(ValueError):inspect(path,self.a['path'],2,PREVIEW)
        with self.assertRaises(ValueError):inspect(self.clip(),self.a['path'],5,NATIVE)
    def test_preview_adapter_negotiation_and_saved_request(self):
        self.configure();self.e.remote.get.return_value={**contract(self.e.app_root),'video_workflow':'v1-old','prepared':True}
        with self.assertRaisesRegex(ValueError,'not deployed'):self.e.run_render(self.j)
        self.e.upload.assert_not_called();self.e.remote.post.assert_not_called()
        from remote_processing import WorkerResponseError
        self.e.remote.get.side_effect=[{**contract(self.e.app_root),'prepared':True},WorkerResponseError('Worker job not found. No generation was started.',400)]
        self.e.remote.post.return_value={'status':'cancelled','stage':'Fixture stops without processing'}
        self.e.run_render(self.j)
        request=json.loads((project_storage.job_folder(self.st,self.j)/'remote-request.json').read_text())
        self.assertEqual(request['video_settings'],{'duration':2,'motion':'still','preset':PREVIEW});self.assertEqual(request['video_workflow_revision'],2)
    def test_paused_or_unapproved_preview_never_transfers(self):
        self.configure();self.a['status']='review'
        with self.assertRaises(ValueError):self.e.build_video(self.j,self.root)
        self.e.upload.assert_not_called()
        self.p['generation_phase']={'status':'paused'}
        with self.assertRaisesRegex(ValueError,'Generation paused'):self.e.run_render(self.j)
        self.assertEqual(self.e.remote.mock_calls,[])

class PreviewAPITests(unittest.TestCase):
    setUp=http_fixture.StudioTests.setUp
    tearDown=http_fixture.StudioTests.tearDown
    call=http_fixture.StudioTests.call
    asset=http_fixture.StudioTests.asset
    approve=http_fixture.StudioTests.approve
    def test_preset_route_validation_and_phase_guard(self):
        self.approve();j=self.call(self.route+'/generate-video',{'video_preset':PREVIEW,'duration':2,'motion':'still'})
        self.assertEqual(j['video_preset'],PREVIEW);self.assertEqual(j['duration'],2)
        before=len(self.st.db['jobs'])
        for data in ({'video_preset':PREVIEW,'duration':5},{'video_preset':PREVIEW,'motion':'slide'},{'duration':2},{'video_preset':'unknown'}):
            self.call(self.route+'/generate-video',data,status=400)
        self.assertEqual(len(self.st.db['jobs']),before)
        self.st.project(self.pid)['generation_phase']={'status':'paused'}
        self.call(self.route+'/generate-video',{'video_preset':PREVIEW,'duration':2},status=400)
        self.assertEqual(len(self.st.db['jobs']),before)

if __name__=='__main__':unittest.main()
