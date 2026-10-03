"""No inference: fixed graphs, geometry and worker contract/lifecycle fixtures."""
import copy,json,hashlib,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock,patch
import numpy as np
from PIL import Image
from video_workflow import build,settings,provenance,NATIVE,PREVIEW,REVISION
from worker_protocol import contract,digest,validate
from worker_service import Worker
from test_worker_video import specs
ROOT=Path(__file__).resolve().parents[1]

def preview_body():
    return {**contract(ROOT),'id':'c'*16,'kind':'video','output_node':'32','video_settings':{'preset':PREVIEW,'duration':2,'motion':'still'},
        'graph':build(ROOT,'asset:'+'f'*64,2,'still',2909202661,'Synthetic fixture','fixture',PREVIEW)}

class PresetTests(unittest.TestCase):
    def test_native_graphs_match_recorded_revision_one(self):
        fixture=json.loads((ROOT/'tests/native_video_v1_hashes.json').read_text())
        for key,expected in fixture.items():
            sec,motion=key.split('-')
            self.assertEqual(digest(build(ROOT,'input-fixture',int(sec),motion,17,'Synthetic fixture','fixture')),expected)
        self.assertEqual(contract(ROOT)['protocol'],1)
        self.assertEqual(contract(ROOT)['workflow'],'b5d256013ae32397b55dc102ff8d82d4329c33bb4e631271de7a38c1ad17ffde')
        self.assertEqual(REVISION,2)
    def test_exact_reviewed_configuration(self):
        c=json.loads((ROOT/'tests/video_preview_configuration.json').read_text());g=preview_body()['graph']
        self.assertEqual([g['11']['inputs'][k] for k in ('width','height')],c['sampling']['dimensions'])
        self.assertEqual(g['11']['inputs']['length'],c['sampling']['requested_sequence_frames'])
        self.assertEqual(g['13']['inputs']['frames_number'],49)
        self.assertEqual(g['34']['inputs'],{'image':['33',0],'batch_index':0,'length':48})
        self.assertEqual(g['33']['inputs'],{'image':['29',0],**c['output']['crop']})
        self.assertEqual(g['37']['inputs'],{'image':['8',0],'upscale_method':'lanczos','width':768,'height':432,'crop':'disabled'})
        self.assertEqual(g['9']['inputs'],{'image':['37',0],'left':0,'right':0,'top':8,'bottom':8,'feathering':0})
        for key,value in c['decoding'].items():
            if key!='node':self.assertEqual(g['29']['inputs'][key],value)
        self.assertEqual(g['15']['inputs']['noise_seed'],c['sampling']['seed'])
        self.assertEqual([float(x) for x in g['18']['inputs']['sigmas'].split(',')],c['sampling']['sigmas'])
        self.assertEqual(g['17']['inputs']['sampler_name'],'euler_ancestral')
        self.assertEqual(g['16']['inputs']['video_cfg'],1);self.assertEqual(g['16']['inputs']['audio_cfg'],1)
        self.assertEqual(g['12']['inputs']['strength'],1);self.assertEqual(g['35']['inputs']['strength'],1)
        self.assertEqual(g['35']['inputs']['frame_idx'],48);self.assertEqual(g['29']['inputs']['samples'],['36',2])
        self.assertEqual(g['31']['inputs'],{'images':['34',0],'fps':24,'bit_depth':8})
    def test_cpu_resize_padding_crop_and_retained_frames(self):
        # Installed Comfy Lanczos uses PIL LANCZOS, pads float32 with .5, and
        # ImageFromBatch slices [batch_index:batch_index+length]. Geometry fixture.
        pixels=np.zeros((1080,1920,3),dtype=np.uint8);pixels[:,:,0]=np.arange(1920,dtype=np.uint16)%256;pixels[:,:,1]=np.arange(1080,dtype=np.uint16)[:,None]%256
        before=hashlib.sha256(pixels.tobytes()).hexdigest()
        small=np.asarray(Image.fromarray(pixels).resize((768,432),Image.Resampling.LANCZOS)).astype(np.float32)/255
        canvas=np.full((448,768,3),.5,dtype=np.float32);canvas[8:440]=small
        self.assertTrue(np.array_equal(canvas[8:440,0:768],small));self.assertTrue(np.all(canvas[:8]==.5));self.assertTrue(np.all(canvas[440:]==.5))
        self.assertEqual(hashlib.sha256(pixels.tobytes()).hexdigest(),before)
        frames=list(range(49));retained=frames[0:48];self.assertEqual(retained,list(range(48)));self.assertNotIn(48,retained)
        p=provenance(PREVIEW,2);self.assertEqual(p['retained_frame_indices'],[0,47]);self.assertFalse(p['guided_endpoint_in_output']);self.assertFalse(p['native_1080p']);self.assertFalse(p['output_upscaler'])
    def test_no_arbitrary_geometry_or_preset_fallback(self):
        assets={'f'*64:{'comfy_name':'fixture.png','dimensions':[1920,1080]}}
        validate(ROOT,preview_body(),assets)
        for node,key,value in [('37','crop','center'),('37','width',640),('9','top',4),('33','y',4),('34','batch_index',1),('34','length',49),('11','length',121),('29','temporal_size',32),('15','noise_seed',1)]:
            b=preview_body();b['graph'][node]['inputs'][key]=value
            with self.assertRaises(ValueError):validate(ROOT,b,assets)
        for key,value in [('preset','invented'),('preset',NATIVE),('duration',5),('motion','push')]:
            b=preview_body();b['video_settings'][key]=value
            with self.assertRaises(ValueError):validate(ROOT,b,assets)
        b=preview_body();b['video_workflow']='9ba70d744675594aba24f796ba044c86f3d4ca57db5bcc96db2e959ef842239f'
        with self.assertRaisesRegex(ValueError,'version'):validate(ROOT,b,assets)
    def test_preview_is_persistent_and_does_not_automatically_release_models(self):
        with tempfile.TemporaryDirectory() as d:
            w=Worker(ROOT,d,'http://127.0.0.1:8191');w.engine.validate_graph=Mock();w.watch=Mock()
            w.store.db['transfers']['f'*64]={'comfy_name':'fixture.png','dimensions':[1920,1080]}
            w.engine.get=Mock(side_effect=lambda route:specs() if route=='/object_info' else {'queue_running':[],'queue_pending':[]})
            w.engine.post=Mock(side_effect=lambda route,b:{'prompt_id':b.get('prompt_id')});w.services.prepared=True
            w.services.process=Mock();w.services.process.poll.return_value=None;w.services.last_model_kind='image'
            b=preview_body();w.submit(b);w.submit(b)
            with patch('worker_service.memory_headroom',return_value=(32,40)):w.tick()
            self.assertEqual([c.args[0] for c in w.engine.post.call_args_list],['/prompt'])
            w2=Worker(ROOT,d,'http://127.0.0.1:8191');j=w2.submit(b)
            self.assertEqual(j['attempts'],1);self.assertEqual(j['video_settings']['preset'],PREVIEW)

if __name__=='__main__':unittest.main()
