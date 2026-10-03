"""Capture contract, adapter and phase fixtures; no renderer or model execution."""
import copy,json,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock
from video_capture import PROFILE,capability,instrument,evidence,missing
from worker_protocol import contract,validate,digest
from video_workflow import PREVIEW
from video_workflow import build
ROOT=Path(__file__).resolve().parents[1]
def preview_body():
 return {**contract(ROOT),'id':'c'*16,'kind':'video','output_node':'32','video_settings':{'preset':PREVIEW,'duration':2,'motion':'still'},'graph':build(ROOT,'asset:'+'f'*64,2,'still',2909202661,'Synthetic fixture','fixture',PREVIEW)}
from store import Store
from worker_service import Worker
import project_storage

def node_specs():
 return {name:{'input':{'required':{'fingerprint':[[capability(ROOT)['fingerprint']]]} if name=='PixeloidCaptureConditioning' else {}}} for name in ('PixeloidCaptureConditioning','PixeloidCaptureLatent','PixeloidCaptureRGB','PixeloidCaptureFinish')}
def capture_body():
 b=preview_body();b['video_settings']['capture']=PROFILE;b['graph']=instrument(ROOT,b['graph'],b['id'],PROFILE);return b

class CaptureContract(unittest.TestCase):
 def test_only_pass_through_capture_changes_graph_and_legacy_hashes_stay_fixed(self):
  b=preview_body();g=instrument(ROOT,b['graph'],b['id'],PROFILE);rest=copy.deepcopy(g)
  for k in ('38','39','40','42'):rest.pop(k)
  for node,key,value in [('12','image',['10',0]),('35','image',['10',0]),('29','samples',['36',2]),('31','images',['34',0])]:rest[node]['inputs'][key]=value
  self.assertEqual(rest,b['graph']);self.assertEqual(contract(ROOT)['video_workflow'],'4de90cccbb0827d5cd749b1a71e62cd3e7764c7767a7e8211bbbbbd1e8bda586')
  self.assertEqual(contract(ROOT)['workflow'],'b5d256013ae32397b55dc102ff8d82d4329c33bb4e631271de7a38c1ad17ffde');self.assertEqual(contract(ROOT)['protocol'],1)
 def test_capture_graph_is_narrowly_allowlisted_and_paths_job_bound(self):
  assets={'f'*64:{'comfy_name':'fixture.png','dimensions':[1920,1080]}};b=capture_body();g=validate(ROOT,b,assets)
  self.assertEqual(g['32']['inputs']['filename_prefix'],'Pixeloid_Worker/'+b['id']+'/node_32')
  for node,key,value in [('38','job_id','d'*16),('39','samples',['20',0]),('29','temporal_size',32),('40','images',['33',0]),('42','video',['31',0])]:
   bad=copy.deepcopy(b);bad['graph'][node]['inputs'][key]=value
   with self.assertRaises(ValueError):validate(ROOT,bad,assets)
  for k,v in [('capture','other'),('preset','ltx-native-1080p-v1')]:
   bad=copy.deepcopy(b);bad['video_settings'][k]=v
   with self.assertRaises(ValueError):validate(ROOT,bad,assets)
  bad=copy.deepcopy(b);bad['video_capture']['fingerprint']='old'
  with self.assertRaisesRegex(ValueError,'version mismatch'):validate(ROOT,bad,assets)
  self.assertEqual(missing(ROOT,node_specs()),[]);self.assertTrue(missing(ROOT,{}))
 def test_worker_collects_only_mp4_and_small_manifest_not_tensors(self):
  import hashlib
  with tempfile.TemporaryDirectory() as tmp:
   w=Worker(ROOT,tmp,'http://127.0.0.1:8191');raw=b'\0\0\0\x20ftypisomfixture';h=hashlib.sha256(raw).hexdigest()
   w.engine.session.get=Mock(return_value=Mock(content=raw));j={'id':'c'*16,'kind':'video','output_node':'32','video_settings':{'capture':PROFILE}}
   m={'job_id':j['id'],'profile':PROFILE,'state':'complete','pc_relative_directory':'Pixeloid_Worker/'+j['id']+'/capture-v1','mp4':{'sha256':h},'stages':{'latent':{'files':[{'name':'video.latent'}]}}}
   history={'outputs':{'32':{'images':[{'filename':'node_32_00001_.mp4','type':'output'}]},'42':{'pixeloid_capture':[m]}}}
   w.collect(j,history);self.assertEqual(list(j['outputs']),[h]);self.assertEqual(w.engine.session.get.call_count,1)
   self.assertEqual(evidence(j['history'],j['id']),m);self.assertEqual(j['capture_summary']['state'],'complete')
   m['mp4']['sha256']='wrong'
   with self.assertRaisesRegex(ValueError,'checksum'):w.collect(j,history)

if __name__=='__main__':unittest.main()
