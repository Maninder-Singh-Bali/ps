"""Synthetic CPU capture tests. Never import/load a model or contact a renderer.
Mac tests use explicit tensor/writer doubles. An additional real CPU safetensors
roundtrip runs only where torch+safetensors already exist (PC renderer Python).
"""
import ast,hashlib,importlib.util,json,os,sys,tempfile,types,unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
from PIL import Image
import av
ROOT=Path(__file__).resolve().parents[1]
REAL_TORCH=importlib.util.find_spec('torch') is not None
REAL_SAFE=importlib.util.find_spec('safetensors') is not None
class Tensor:
 def __init__(self,a):self.a=np.asarray(a);self.device=types.SimpleNamespace(type='cpu')
 @property
 def shape(self):return self.a.shape
 @property
 def dtype(self):return self.a.dtype
 def detach(self):return self
 def cpu(self):return self
 def contiguous(self):return self
 def numpy(self):return self.a
 def __mul__(self,n):return Tensor(self.a*n)
 def clamp(self,a,b):return Tensor(np.clip(self.a,a,b))
 def byte(self):return Tensor(self.a.astype(np.uint8))
 def __iter__(self):return (Tensor(x) for x in self.a)
class RuntimeTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.folder=types.ModuleType('folder_paths');self.folder.get_output_directory=lambda:str(self.root);self.folder.__file__=str(self.root/'folder_paths.py')
  self.torch=types.SimpleNamespace(Tensor=Tensor,tensor=lambda v,**kwargs:Tensor(v),cuda=types.SimpleNamespace(is_initialized=lambda:False),__version__='fixture-double')
  self.saved=[]
  def save(tensors,path,metadata):
   self.saved.append((tensors,metadata));Path(path).write_bytes(b'fixture-writer-not-safetensors')
  utils=types.ModuleType('comfy.utils');utils.save_torch_file=save;comfy=types.ModuleType('comfy');comfy.utils=utils
  self.patcher=patch.dict(sys.modules,{'folder_paths':self.folder,'torch':self.torch,'comfy':comfy,'comfy.utils':utils});self.patcher.start()
  spec=importlib.util.spec_from_file_location('capture_under_test',ROOT/'capture_extension/pixeloid_preview_capture/__init__.py');self.m=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.m)
  self.job='a'*16;self.p=self.m.directory(self.job)
 def tearDown(self):self.patcher.stop();self.tmp.cleanup()
 def start(self):
  self.p.mkdir(parents=True);self.m.write_json(self.p/'manifest.json',{'profile':self.m.PROFILE,'job_id':self.job,'state':'capturing','start_monotonic':__import__('time').perf_counter(),'stages':{}})
 def test_begin_pins_sources_no_overwrite_and_exact_conditioning_passthrough(self):
  # Copy the expected small source fixtures into a synthetic renderer root.
  pins=json.loads((ROOT/'capture_extension/pixeloid_preview_capture/runtime_sources.json').read_text())
  snapshot=Path(os.environ.get('PIX_CAPTURE_COMFY_ROOT',str(ROOT.parent/'verification/ltx-preview-artifact-audit/installed-code')))
  if not snapshot.exists():self.skipTest('Mac saved-source fixture not in minimal PC package; PC preflight verifies actual hashes.')
  for name in pins:
   target=self.root/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes((snapshot/name).read_bytes())
  im=Tensor(np.full((1,448,768,3),.5,np.float32));fingerprint=self.m.extension_fingerprint()[0]
  self.assertIs(self.m.PixeloidCaptureConditioning().capture(im,self.job,fingerprint,prompt={'fixture':1})[0],im)
  self.assertEqual(self.saved[0][0]['conditioning'].a[0,0,0,0],.5)
  with self.assertRaises(FileExistsError):self.m.PixeloidCaptureConditioning().capture(im,self.job,fingerprint)
  (self.root/'nodes.py').write_text('changed')
  with self.assertRaisesRegex(ValueError,'source changed'):self.m.PixeloidCaptureConditioning().capture(im,'b'*16,fingerprint)
 def test_latent_preserves_dtype_mask_metadata_and_original_object(self):
  self.start();x=Tensor(np.zeros((1,128,7,14,24),np.float16));mask=Tensor(np.ones((1,1,7,1,1),np.float32));sample={'samples':x,'noise_mask':mask,'batch_index':[0]}
  self.assertIs(self.m.PixeloidCaptureLatent().capture(sample,self.job)[0],sample)
  saved,metadata=self.saved[0];self.assertIs(saved['latent_tensor'],x);self.assertIs(saved['aux_noise_mask'],mask)
  self.assertEqual(json.loads(metadata['pixeloid_capture'])['extras'],{'batch_index':[0]});self.assertEqual(x.dtype,np.float16)
 def test_exact_rgb_pngs_then_matching_mp4_manifest_no_duplicate_frame_sets(self):
  self.start();a=np.empty((48,432,768,3),np.float32);a[:]=[.5,.1249,1.1];a[:,1,0]=[-.1,.5001,.9];images=Tensor(a)
  self.assertIs(self.m.PixeloidCaptureRGB().capture(images,self.job)[0],images)
  files=list((self.p/'rgb').glob('*.png'));self.assertEqual(len(files),48)
  for name,stage in [('conditioning.safetensors','conditioning'),('video.latent','latent')]:
   (self.p/name).write_bytes(b'fixture already-saved tensor');self.m.record(self.p,stage,__import__('time').perf_counter(),[])
  expected=(a[0]*255).clip(0,255).astype(np.uint8);self.assertTrue(np.array_equal(np.asarray(Image.open(self.p/'rgb/000.png')),expected));self.assertEqual(expected[0,0,0],127)
  path=self.p.parent/'node_32_00001_.mp4'
  with av.open(str(path),'w') as c:
   s=c.add_stream('libx264',rate=24);s.width=768;s.height=432;s.pix_fmt='yuv420p'
   for i in range(48):
    for packet in s.encode(av.VideoFrame.from_ndarray(expected,format='rgb24')):c.mux(packet)
   for packet in s.encode():c.mux(packet)
  result=self.m.PixeloidCaptureFinish().capture(object(),self.job);m=result['ui']['pixeloid_capture'][0]
  self.assertEqual(m['state'],'complete');self.assertEqual(m['mp4']['sha256'],hashlib.sha256(path.read_bytes()).hexdigest());self.assertIn('crf=23.0',m['mp4']['settings']['x264_SEI']);self.assertEqual(len(m['stages']['encoder_rgb']['files']),48)
  self.assertEqual(sorted(p.name for p in self.p.iterdir()),['conditioning.safetensors','manifest.json','rgb','video.latent'])
 def test_invalid_identity_gpu_frames_and_partial_completion_fail_closed(self):
  with self.assertRaises(ValueError):self.m.directory('../escape')
  x=Tensor(np.zeros((48,432,768,3),np.float32));x.device.type='cuda'
  with self.assertRaisesRegex(ValueError,'GPU frame copies'):self.m.PixeloidCaptureRGB().capture(x,self.job)
  self.start()
  with self.assertRaisesRegex(ValueError,'incomplete'):self.m.PixeloidCaptureFinish().capture(object(),self.job)
  self.assertEqual(json.loads((self.p/'manifest.json').read_text())['state'],'capturing')
 def test_disk_failure_keeps_partial_manifest_and_never_returns_success(self):
  self.start();x=Tensor(np.zeros((48,432,768,3),np.float32))
  with patch.object(Image.Image,'save',side_effect=OSError('fixture disk full')):
   with self.assertRaises(OSError):self.m.PixeloidCaptureRGB().capture(x,self.job)
  self.assertNotIn('encoder_rgb',json.loads((self.p/'manifest.json').read_text())['stages'])

@unittest.skipUnless(REAL_TORCH and REAL_SAFE,'Requires already installed PC torch+safetensors; no Mac model runtime installed.')
class ActualCPUStorage(unittest.TestCase):
 def test_real_cpu_safetensors_bfloat16_mask_roundtrip(self):
  import torch,safetensors.torch
  with tempfile.TemporaryDirectory() as tmp:
   folder=types.ModuleType('folder_paths');folder.get_output_directory=lambda:tmp
   utils=types.ModuleType('comfy.utils');utils.save_torch_file=lambda tensors,path,metadata:safetensors.torch.save_file(tensors,path,metadata=metadata)
   comfy=types.ModuleType('comfy');comfy.utils=utils
   with patch.dict(sys.modules,{'folder_paths':folder,'comfy':comfy,'comfy.utils':utils}):
    spec=importlib.util.spec_from_file_location('actual_cpu_capture',ROOT/'capture_extension/pixeloid_preview_capture/__init__.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    rng_before=torch.get_rng_state().clone()
    source=torch.arange(24,dtype=torch.bfloat16).reshape(2,3,4).transpose(1,2);mask=torch.tensor([0.,1.]);record=m.tensor_file(Path(tmp),'fixture.latent',{'latent_tensor':source,'aux_noise_mask':mask},{'fixture':True})
    self.assertTrue(torch.equal(rng_before,torch.get_rng_state()))
    loaded=safetensors.torch.load_file(str(Path(tmp)/'fixture.latent'),device='cpu')
    self.assertEqual(loaded['latent_tensor'].dtype,source.dtype);self.assertTrue(torch.equal(loaded['latent_tensor'],source));self.assertTrue(torch.equal(loaded['aux_noise_mask'],mask));self.assertEqual(record['sha256'],m.sha(Path(tmp)/'fixture.latent'))
if __name__=='__main__':unittest.main()
