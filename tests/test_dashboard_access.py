import json,tempfile,threading,unittest
from pathlib import Path
from unittest.mock import patch
import requests
from dashboard_access import Access,interrupted
from server import make_server

class AccessTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
  self.http=make_server(self.root/'data',0,start_worker=False,access_config={'private_dir':str(self.root/'private')})
  self.thread=threading.Thread(target=self.http.serve_forever,daemon=True);self.thread.start();self.url=f'http://127.0.0.1:{self.http.server_port}'
  self.s=requests.Session();self.s.trust_env=False;self.s.headers.update({'Origin':self.url,'X-Pixeloid-Client':'1'})
 def tearDown(self):self.http.shutdown();self.http.engine.stop.set();self.http.server_close();self.s.close();self.tmp.cleanup()
 def signin(self):
  r=self.s.post(self.url+'/api/access/setup',json={'user':'reviewer','password':'fixture-only-passphrase'});self.assertEqual(r.status_code,200)
  self.s.headers['X-Pixeloid-CSRF']=self.s.get(self.url+'/api/access/session').json()['csrf'];return r
 def test_protect_pages_api_static_media_and_upload(self):
  for path in ['/api/state','/api/health','/api/identity','/app.js','/media/missing','/api/studio/status']:
   self.assertEqual(self.s.get(self.url+path).status_code,401,path)
  self.assertEqual(self.s.get(self.url+'/',allow_redirects=False).status_code,303)
  self.assertEqual(self.s.post(self.url+'/api/projects/x/upload',data=b'private').status_code,401)
 def test_login_cookie_hash_csrf_logout(self):
  r=self.signin();self.assertIn('HttpOnly',r.headers['Set-Cookie']);self.assertIn('SameSite=Strict',r.headers['Set-Cookie'])
  self.assertNotIn('fixture-only-passphrase',self.http.access.file.read_text())
  self.assertEqual(self.s.get(self.url+'/api/state').status_code,200)
  csrf=self.s.headers.pop('X-Pixeloid-CSRF');self.assertEqual(self.s.post(self.url+'/api/projects',json={'name':'bad'}).status_code,403)
  self.s.headers['X-Pixeloid-CSRF']=csrf;self.assertEqual(self.s.post(self.url+'/api/projects',json={'name':'safe'}).status_code,200)
  self.assertEqual(self.s.post(self.url+'/api/access/logout',json={}).status_code,200);self.assertEqual(self.s.get(self.url+'/api/state').status_code,401)
 def test_cross_origin_and_host_rejected(self):
  self.signin();self.assertEqual(self.s.get(self.url+'/api/state',headers={'Host':'evil.test'}).status_code,403)
  self.assertEqual(self.s.post(self.url+'/api/projects',json={},headers={'Origin':'http://evil.test'}).status_code,403)
 def test_lan_setup_blocked_and_expiry(self):
  a=Access(self.root/'other',8790,'192.168.1.2','192.168.1.0/24')
  with self.assertRaises(PermissionError):a.setup('x','fixture-only-passphrase','192.168.1.3')
  with self.assertRaises(PermissionError):a.origin({'Host':'192.168.1.2:8790'},'192.168.2.3')
  self.signin()
  with patch('dashboard_access.time.time',return_value=99999999999):self.assertIsNone(self.http.access.session({'Cookie':'pixeloid_session='+self.s.cookies.get('pixeloid_session')}))
 def test_password_bruteforce_bound(self):
  self.signin()
  for _ in range(8):self.assertEqual(self.s.post(self.url+'/api/access/login',json={'user':'reviewer','password':'wrong'}).status_code,403)
  self.assertIn('Too many',self.s.post(self.url+'/api/access/login',json={'user':'reviewer','password':'fixture-only-passphrase'}).json()['error'])
 def test_restart_does_not_rerun_jobs(self):
  st=self.http.store;p=st.create_project('temporary');j=st.new_job(p['id'],'image');j.update(status='running',prompt_id='saved-owned-prompt',result_asset_id='saved-output')
  interrupted(st);self.assertEqual(j['status'],'interrupted');self.assertEqual(j['result_asset_id'],'saved-output');self.assertEqual(j['prompt_id'],'saved-owned-prompt')
 def test_remote_folder_dialog_disabled(self):
  self.signin();self.assertEqual(self.s.post(self.url+'/api/choose-folder',json={}).status_code,400)

if __name__=='__main__':unittest.main()
