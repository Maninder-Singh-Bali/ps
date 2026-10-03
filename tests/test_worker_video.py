"""Worker-only simulated lifecycle tests; no network, renderer or model loading."""
import copy,hashlib,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock,patch
from worker_service import Worker
from worker_protocol import contract,validate,video_missing
from video_workflow import build
import render_progress
ROOT=Path(__file__).resolve().parents[1]

def body(jid='a'*16,motion='still',seconds=5):
    return {**contract(ROOT),'id':jid,'kind':'video','output_node':'32',
        'video_settings':{'duration':seconds,'motion':motion},
        'graph':build(ROOT,'asset:'+'f'*64,seconds,motion,1,'Synthetic fixture only','untrusted/prefix')}

def specs():
    g=body()['graph'];result={n['class_type']:{'input':{'required':{}}} for n in g.values()}
    result['ImageScale']={'input':{'required':{}}}
    for n in g.values():
        for k in ('unet_name','clip_name','vae_name'):
            if k in n['inputs']:result[n['class_type']]['input']['required'].setdefault(k,[[]])[0].append(n['inputs'][k])
    return result

class VideoWorkerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.w=Worker(ROOT,self.tmp.name,'http://127.0.0.1:8191')
        self.w.store.db['transfers']['f'*64]={'comfy_name':'input.png','dimensions':[1920,1080]}
        self.w.engine.validate_graph=Mock();self.w.engine.get=Mock(side_effect=lambda route:specs() if route=='/object_info' else {} if route.startswith('/history/') else {'queue_running':[],'queue_pending':[]})
        self.w.engine.post=Mock(side_effect=lambda route,data:{'prompt_id':data.get('prompt_id')} if route=='/prompt' else {})
        self.w.watch=Mock();self.w.services.prepared=True
        self.guard=patch('worker_service.memory_headroom',return_value=(32,40));self.guard.start();self.addCleanup(self.guard.stop)
    def tearDown(self):self.tmp.cleanup()
    def test_bounded_video_variants_and_rejections(self):
        for motion in ('still','push','slide'):
            for seconds in (5,8):
                g=validate(ROOT,body(motion=motion,seconds=seconds),self.w.store.db['transfers'])
                self.assertEqual(g['8']['inputs']['image'],'input.png');self.assertIn('Pixeloid_Worker/',g['32']['inputs']['filename_prefix'])
                self.assertEqual('35' in g,motion=='still')
        for node,key,value in [('11','width',4096),('11','length',999),('11','batch_size',2),('18','sigmas','1,0'),('1','unet_name','other'),('32','format','auto'),('8','image','C:/private.png')]:
            b=body();b['graph'][node]['inputs'][key]=value
            with self.assertRaises(ValueError):validate(ROOT,b,self.w.store.db['transfers'])
        b=body();b['video_workflow']='wrong'
        with self.assertRaisesRegex(ValueError,'version'):validate(ROOT,b,self.w.store.db['transfers'])
        self.w.store.db['transfers']['f'*64]['dimensions']=[512,512]
        with self.assertRaisesRegex(ValueError,'native'):validate(ROOT,body(),self.w.store.db['transfers'])
    def test_image_v1_compatibility_and_missing_video_models(self):
        b={**contract(ROOT),'id':'b'*16,'kind':'image','output_node':'1','graph':{'1':{'class_type':'SaveImage','inputs':{'images':['2',0],'filename_prefix':'image'}}}}
        b.pop('video_workflow');b.update(video=False,kinds=['image','reference'])
        self.w.submit(b)
        self.assertEqual(video_missing(ROOT,specs()),[])
        s=specs();s['UNETLoader']['input']['required']['unet_name']=[[]]
        self.w.engine.get=Mock(return_value=s)
        with self.assertRaisesRegex(ValueError,'components'):self.w.submit(body())
        self.assertEqual(len(self.w.store.db['jobs']),1)
    def test_single_lane_waits_for_images_and_external_jobs(self):
        first={**contract(ROOT),'id':'a'*16,'kind':'image','output_node':'1','graph':{'1':{'class_type':'SaveImage','inputs':{'images':['2',0],'filename_prefix':'image'}}}}
        self.w.submit(first);self.w.tick();self.w.submit(body('b'*16))
        j=self.w.store.db['jobs'][first['id']]
        self.w.engine.get=Mock(side_effect=lambda route:{} if route.startswith('/history/') else {'queue_running':[[0,j['prompt_id'],{},{}]],'queue_pending':[]})
        self.w.tick();self.assertEqual(self.w.engine.post.call_count,1)
        self.assertEqual(self.w.job('b'*16)['attempts'],0)
        j['status']='completed'
        self.w.engine.get=Mock(return_value={'queue_running':[[0,'another-user',{},{}]],'queue_pending':[]})
        self.w.tick();self.assertEqual(self.w.engine.post.call_count,1)
    def test_owned_release_and_external_respect(self):
        self.w.submit(body());self.w.tick()
        self.assertEqual([c.args[0] for c in self.w.engine.post.call_args_list],['/prompt'])
        self.w.store.db['jobs']['a'*16]['status']='completed'
        self.w.services.process=Mock();self.w.services.process.poll.return_value=None;self.w.services.last_model_kind='image'
        self.w.submit(body('b'*16));self.w.tick()
        self.assertEqual([c.args[0] for c in self.w.engine.post.call_args_list],['/prompt','/free','/prompt'])
    def test_native_input_transfer_and_memory_wait(self):
        from PIL import Image
        import io
        raw=io.BytesIO();Image.new('RGB',(1920,1080),'white').save(raw,format='PNG')
        self.w.engine.upload=Mock(return_value='native.png');aid=self.w.upload(raw.getvalue())['id']
        b=body();b['graph']['8']['inputs']['image']='asset:'+aid
        self.w.submit(b);self.assertEqual(self.w.job(b['id'])['attempts'],0)
        with patch('worker_service.memory_headroom',return_value=(8,10)):self.w.tick()
        self.w.engine.post.assert_not_called();self.assertEqual(self.w.job(b['id'])['stage'],'Waiting for shared PC memory')

    def test_video_restart_unknown_post_and_targeted_cancel(self):
        self.w.submit(body());self.w.tick();self.w.store.save()
        w=Worker(ROOT,self.tmp.name,'http://127.0.0.1:8191');w.engine.post=Mock();w.watch=Mock();j=w.store.db['jobs']['a'*16]
        w.engine.get=Mock(side_effect=lambda route:{} if route.startswith('/history/') else {'queue_running':[[0,j['prompt_id'],{},{}]],'queue_pending':[]})
        w.tick();w.submit(body());w.engine.post.assert_not_called();self.assertEqual(j['attempts'],1)
        w.cancel(j['id']);w.engine.post.assert_any_call('/interrupt',{'prompt_id':j['prompt_id']});w.engine.post.assert_any_call('/queue',{'delete':[j['prompt_id']]})
        j['submission_intent']=1;w.engine.get=Mock(side_effect=lambda route:{} if route.startswith('/history/') else {'queue_running':[],'queue_pending':[]})
        w.tick();self.assertEqual(j['status'],'cancelled');self.assertEqual(w.engine.post.call_count,2)
    def test_cancel_before_first_request_is_a_persistent_tombstone(self):
        self.w.cancel('a'*16);w=Worker(ROOT,self.tmp.name,'http://127.0.0.1:8191')
        w.engine.post=Mock();w.engine.validate_graph=Mock()
        self.assertEqual(w.submit(body())['status'],'cancelled');self.assertEqual(w.job('a'*16)['attempts'],0)
        w.engine.post.assert_not_called();w.engine.validate_graph.assert_not_called()

    def test_video_progress_is_prompt_scoped(self):
        self.w.submit(body());self.w.tick();j=self.w.store.db['jobs']['a'*16]
        event={'type':'progress','data':{'prompt_id':j['prompt_id'],'node':'19','value':3,'max':8}}
        fields=render_progress.event_fields(j,event,j['graph'],1);self.assertEqual(fields['steps'],[3,8]);self.assertEqual(fields['progress'],37.5)
        event['data']['prompt_id']='other';self.assertEqual(render_progress.event_fields(j,event,j['graph'],2),{})
    def test_container_retrieval_hash_and_legacy_png(self):
        # Only a protocol envelope, not a decodable render or evidence of LTX output.
        raw=b'\x00\x00\x00\x18ftypisom'+b'fixture';self.w.engine.session.get=Mock(return_value=Mock(content=raw))
        self.w.submit(body());j=self.w.store.db['jobs']['a'*16]
        for key in ('images','videos','gifs'):
            self.w.collect(j,{'outputs':{'32':{key:[{'filename':'clip.mp4','subfolder':'Pixeloid_Worker','type':'output'}]}}})
            aid=hashlib.sha256(raw).hexdigest();self.assertEqual(self.w.output(aid),(raw,'video/mp4'))
        self.w.store.save();w=Worker(ROOT,self.tmp.name,'http://127.0.0.1:8191');self.assertEqual(w.output(aid),(raw,'video/mp4'))
        (w.outputs/(aid+'.mp4')).write_bytes(b'corrupt')
        with self.assertRaisesRegex(ValueError,'checksum'):w.output(aid)
        png=b'legacy fixture';aid=hashlib.sha256(png).hexdigest();(w.outputs/(aid+'.png')).write_bytes(png)
        w.store.db['jobs']['legacy']={'outputs':{aid:{'sha256':aid,'bytes':len(png)}}}
        self.assertEqual(w.output(aid),(png,'image/png'))

if __name__=='__main__':unittest.main()
