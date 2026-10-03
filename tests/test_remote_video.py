"""Isolated protocol/lifecycle fixtures. Never contacts a renderer or loads models."""
import copy,hashlib,io,json,tempfile,threading,unittest
from pathlib import Path
from unittest.mock import Mock,patch
from PIL import Image
import requests
from engine import Engine,register_asset
from store import Store,approved_image
from remote_processing import RemoteEngine,RemoteServices,WorkerResponseError
from worker_service import Worker,Handler
from worker_protocol import contract,validate,video_missing
from video_workflow import build
import render_progress,project_storage,scene_control

ROOT=Path(__file__).resolve().parents[1]

from test_worker_video import body

class VideoClientTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.st=Store(self.root);self.p=self.st.create_project('Synthetic');self.r=self.st.add_room(self.p['id'])
        path=self.root/'source.png';Image.new('RGB',(1920,1080),'white').save(path)
        self.a=register_asset(self.st,self.p['id'],path,'image',self.r['id'],status='approved',approved_revision=self.r['revision']);self.r['approved_image_id']=self.a['id'];self.r['images'].append(self.a['id'])
        self.e=RemoteEngine.__new__(RemoteEngine);Engine.__init__(self.e,self.st,ROOT);self.e.remote=Mock();self.e.upload=Mock(return_value='asset:'+'f'*64)
        self.j=self.st.new_job(self.p['id'],'video',self.r['id'],duration=5,motion='still',input_revision=self.r['revision'],source_image_id=self.a['id'],source_image_identity=scene_control.file_identity(self.st,self.a['id']),scene_ticket=scene_control.scene_snapshot(self.st,self.p,self.r))
    def tearDown(self):self.tmp.cleanup()
    def test_approval_identity_scene_and_pause_fail_before_upload(self):
        self.a['status']='review'
        with self.assertRaisesRegex(ValueError,'Explicitly'):self.e.build_video(self.j,self.root)
        self.a['status']='approved';self.r['revision']+=1
        with self.assertRaisesRegex(ValueError,'changed'):self.e.build_video(self.j,self.root)
        self.r['revision']-=1;self.a['path']=str(self.root/'changed.png');Image.new('RGB',(1920,1080),'red').save(self.a['path'])
        with self.assertRaises(ValueError):self.e.build_video(self.j,self.root)
        self.e.upload.assert_not_called()
        self.p['generation_phase']={'status':'paused'}
        with self.assertRaisesRegex(ValueError,'Generation paused'):self.e.run_render(self.j)
        self.e.remote.assert_not_called();self.assertEqual(self.e.remote.mock_calls,[])
    def test_old_worker_refused_before_input_transfer(self):
        self.e.remote.get.return_value={**contract(ROOT),'video':False,'prepared':True}
        with self.assertRaisesRegex(ValueError,'not deployed'):self.e.run_render(self.j)
        self.e.upload.assert_not_called();self.e.remote.post.assert_not_called()
    def test_disconnect_reuses_same_request_then_retrieves_without_post(self):
        self.e.stop=Mock();self.e.stop.is_set.return_value=False
        complete={'status':'completed','stage':'Ready','id':self.j['id']}
        history={'outputs':{'32':{'images':[{'worker_asset':'d'*64}]}}}
        sequence=[{**contract(ROOT),'prepared':True},WorkerResponseError('Worker job not found. No generation was started.',400),complete,history]
        self.e.remote.get.side_effect=sequence
        self.e.remote.post.side_effect=requests.ConnectionError('Lost reply after PC accepted')
        self.e.finish_render=Mock();self.e.run_render(self.j)
        self.e.remote.post.assert_called_once();self.e.finish_render.assert_called_once_with(self.j,history,project_storage.job_folder(self.st,self.j))
        self.assertEqual(self.j['remote_job_id'],self.j['id']);self.assertTrue((project_storage.job_folder(self.st,self.j)/'remote-request.json').exists())
        self.e.remote.reset_mock();self.e.remote.get.side_effect=[complete,history];self.e.run_render(self.j);self.e.remote.post.assert_not_called()
    def test_saved_but_unadmitted_request_cannot_bypass_revoked_approval(self):
        folder=project_storage.job_folder(self.st,self.j);folder.mkdir(parents=True,exist_ok=True);(folder/'remote-request.json').write_text(json.dumps(body(self.j['id'])))
        self.j['remote_job_id']=self.j['id'];self.a['status']='review'
        self.e.remote.get.side_effect=WorkerResponseError('Worker job not found. No generation was started.',400)
        with self.assertRaisesRegex(ValueError,'Explicitly'):self.e.run_render(self.j)
        self.e.remote.post.assert_not_called()
    def test_completed_synthetic_video_installed_once_unapproved(self):
        # CPU encoding of a repeated synthetic frame verifies retrieval/decoding only.
        import av,numpy as np
        clip=self.root/'fixture.mp4'
        with av.open(str(clip),'w') as c:
            stream=c.add_stream('libx264',rate=24);stream.width=1920;stream.height=1080;stream.pix_fmt='yuv420p';stream.options={'preset':'ultrafast','crf':'35'}
            pixels=np.full((1080,1920,3),255,dtype=np.uint8)
            for _ in range(120):
                frame=av.VideoFrame.from_ndarray(pixels,format='rgb24')
                for packet in stream.encode(frame):c.mux(packet)
            for packet in stream.encode():c.mux(packet)
        self.e.build_video(self.j,self.root);self.j['output_node']='32'
        raw=clip.read_bytes();aid=hashlib.sha256(raw).hexdigest();self.e.remote.request.return_value=Mock(content=raw)
        h={'outputs':{'32':{'images':[{'worker_asset':aid}]}}}
        self.e.finish_render(self.j,h,self.root);first=self.j['result_asset_id'];self.e.finish_render(self.j,h,self.root)
        self.assertEqual(self.r['videos'],[first]);self.assertEqual(self.st.asset(first)['status'],'review')
        self.assertEqual(self.st.asset(first)['source_image_id'],self.a['id']);self.assertTrue(self.j['video_check']['technical_passed'])
        self.assertEqual(self.j['video_check']['frames_decoded'],120)
        self.assertFalse(self.r.get('approved_video_id'))

    def test_download_rejects_corruption(self):
        raw=b'mp4 fixture';aid=hashlib.sha256(raw).hexdigest();self.e.remote.request.return_value=Mock(content=raw)
        self.assertEqual(self.e.download_output({'worker_asset':aid}),raw)
        with self.assertRaisesRegex(ValueError,'checksum'):self.e.download_output({'worker_asset':'0'*64})

class WorkerHTTPTests(unittest.TestCase):
    def test_auth_origin_and_mp4_download_on_isolated_loopback_server(self):
        from http.server import ThreadingHTTPServer
        from dashboard_access import Access
        with tempfile.TemporaryDirectory() as d:
            w=Worker(ROOT,d,'http://127.0.0.1:8191');raw=b'fixture output';aid=hashlib.sha256(raw).hexdigest()
            (w.outputs/(aid+'.mp4')).write_bytes(raw);w.store.db['jobs']['fixture']={'outputs':{aid:{'extension':'.mp4','content_type':'video/mp4'}}}
            server=ThreadingHTTPServer(('127.0.0.1',0),Handler);server.worker=w;server.token='fixture-token'*5;server.access=Mock();server.access.origin=Mock()
            thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start();client=requests.Session();client.trust_env=False
            url=f'http://127.0.0.1:{server.server_port}/v1/outputs/{aid}'
            try:
                self.assertEqual(client.get(url).status_code,403)
                headers={'Authorization':'Bearer '+server.token}
                self.assertEqual(client.get(url,headers={**headers,'Origin':'http://browser'}).status_code,403)
                r=client.get(url,headers=headers);self.assertEqual(r.status_code,200);self.assertEqual(r.content,raw);self.assertEqual(r.headers['Content-Type'],'video/mp4')
                self.assertEqual(client.post(url.replace('/outputs/'+aid,'/exec'),headers=headers,json={'command':'no'}).status_code,404)
            finally:client.close();server.shutdown();server.server_close()

if __name__=='__main__':unittest.main()
