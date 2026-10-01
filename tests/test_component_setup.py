import sys,tempfile,unittest,hashlib,threading
from pathlib import Path
from unittest.mock import Mock,patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import component_setup as setup
from store import Store

class DownloadTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(dir=Path(__file__).parent);self.root=Path(self.tmp.name);self.st=Store(self.root/'data');self.p=self.st.create_project('Setup test')
  self.engine=Mock(store=self.st,app_root=self.root,stop=threading.Event());self.payload=b'verified-model-fixture';self.target=self.root/'models/model.safetensors'
  self.item={'name':'Test','file':'model.safetensors','bytes':len(self.payload),'sha256':hashlib.sha256(self.payload).hexdigest(),'url':'https://huggingface.co/vendor/test/resolve/pin/model','licence':'Test licence'}
  self.catalog=patch.dict(setup.CATALOG,{'test':self.item},clear=True);self.catalog.start();self.dest=patch.object(setup,'destination',return_value=self.target);self.dest.start();self.config=patch.object(setup,'config',return_value={'comfy_root':str(self.root)});self.config.start()
 def tearDown(self):self.config.stop();self.dest.stop();self.catalog.stop();self.tmp.cleanup()
 def queue(self,**kw):return setup.queue(self.engine,self.p['id'],{'component_id':'test','approved':True,'sha256':self.item['sha256'],**kw})
 def response(self,payload=None):
  response=Mock(status_code=200,is_redirect=False);response.iter_content.return_value=[self.payload if payload is None else payload];response.__enter__=Mock(return_value=response);response.__exit__=Mock(return_value=False);return response
 def test_explicit_approval_and_matching_manifest_required(self):
  with self.assertRaises(ValueError):self.queue(approved=False)
  with self.assertRaises(ValueError):self.queue(sha256='changed')
  self.assertEqual(len(self.st.db['jobs']),0)
 def test_verified_download_installed_atomically(self):
  job=self.queue();session=Mock();session.get.return_value=self.response()
  with patch.object(setup.requests,'Session',return_value=session):setup.run(self.engine,job)
  self.assertEqual(self.target.read_bytes(),self.payload);self.assertEqual(job['status'],'completed')
 def test_bad_hash_never_installed(self):
  job=self.queue();session=Mock();session.get.return_value=self.response(b'x'*len(self.payload))
  with patch.object(setup.requests,'Session',return_value=session):
   with self.assertRaisesRegex(ValueError,'checksum'):setup.run(self.engine,job)
  self.assertFalse(self.target.exists());self.assertEqual(len(list(self.target.parent.glob('*.rejected-*'))),1)
 def test_existing_file_not_replaced(self):
  self.target.parent.mkdir();self.target.write_bytes(b'old model')
  with self.assertRaisesRegex(ValueError,'already exists'):self.queue()
  self.assertEqual(self.target.read_bytes(),b'old model')
 def test_cancellation_preserves_partial_download(self):
  job=self.queue();self.engine.stop.set();session=Mock();session.get.return_value=self.response()
  with patch.object(setup.requests,'Session',return_value=session):setup.run(self.engine,job)
  self.assertFalse(self.target.exists());self.assertTrue(self.target.with_suffix('.safetensors.pixeloid-part').exists())
 def test_untrusted_redirect_not_requested(self):
  job=self.queue();session=Mock();response=Mock(is_redirect=True,headers={'Location':'http://127.0.0.1/secrets'});session.get.return_value=response
  with patch.object(setup.requests,'Session',return_value=session):
   with self.assertRaisesRegex(ValueError,'approved model host'):setup.run(self.engine,job)
  self.assertEqual(session.get.call_count,1)
 def test_interrupted_download_not_installed(self):
  job=self.queue();session=Mock();session.get.return_value=self.response(self.payload[:5])
  with patch.object(setup.requests,'Session',return_value=session):
   with self.assertRaisesRegex(ValueError,'interrupted'):setup.run(self.engine,job)
  self.assertFalse(self.target.exists());self.assertEqual(self.target.with_suffix('.safetensors.pixeloid-part').read_bytes(),self.payload[:5])
if __name__=='__main__':unittest.main()
