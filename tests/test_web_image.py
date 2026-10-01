import io,unittest
from unittest.mock import patch,Mock
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from web_image import fetch_public_image,public_target,LIMIT
from PIL import Image
import test_studio

def address(host,port,**kw):return [(2,1,6,'',('93.184.216.34',port))]

class WebImageTests(unittest.TestCase):
    def test_private_and_credential_links_blocked(self):
        with patch('web_image.socket.getaddrinfo',return_value=[(2,1,6,'',('127.0.0.1',80))]):
            with self.assertRaises(ValueError):public_target('http://local.test/image.png')
        with self.assertRaises(ValueError):public_target('https://user:secret@example.com/image.png')
        with self.assertRaises(ValueError):public_target('file:///C:/private.png')
    def response(self,body=b'image',status=200,**headers):
        r=Mock();r.status=status;r.getheader=lambda key,default=None:headers.get(key,default);stream=io.BytesIO(body);r.read=stream.read
        return r
    def test_download_limit_and_webpage_rejection(self):
        for headers in [{'Content-Length':str(LIMIT+1)},{'Content-Type':'text/html'}]:
            with patch('web_image.socket.getaddrinfo',side_effect=address),patch('web_image.open_image_response',return_value=(Mock(sock=None),self.response(**headers))):
                with self.assertRaises(ValueError):fetch_public_image('https://example.com/image.png')
    def test_redirect_cannot_enter_local_network(self):
        def resolve(host,port,**kw):return [(2,1,6,'',('127.0.0.1' if host=='internal.test' else '93.184.216.34',port))]
        with patch('web_image.socket.getaddrinfo',side_effect=resolve),patch('web_image.open_image_response',return_value=(Mock(sock=None),self.response(status=302,Location='http://internal.test/private'))) as opened:
            with self.assertRaises(ValueError):fetch_public_image('https://example.com/image.png')
            self.assertEqual(opened.call_count,1)
    def test_success_preserves_downloaded_bytes(self):
        with patch('web_image.socket.getaddrinfo',side_effect=address),patch('web_image.open_image_response',return_value=(Mock(sock=None),self.response(b'png bytes',**{'Content-Type':'image/png'}))):
            raw,name=fetch_public_image('https://example.com/furniture/chair.png?size=large');self.assertEqual(raw,b'png bytes');self.assertEqual(name,'chair.png')

class WebImageEndpointTests(unittest.TestCase):
    setUp=test_studio.StudioTests.setUp
    tearDown=test_studio.StudioTests.tearDown
    call=test_studio.StudioTests.call
    def test_import_stays_in_selected_room_and_project(self):
        b=io.BytesIO();Image.new('RGB',(60,40),'beige').save(b,format='PNG')
        with patch('server.fetch_public_image',return_value=(b.getvalue(),'website-chair.png')):
            result=self.call(f'/api/projects/{self.pid}/import-image',{'url':'https://example.com/chair.png','kind':'reference','room_id':self.rid})
        aid=result['assets'][0]['id'];a=self.st.asset(aid)
        self.assertIn(aid,self.st.room(self.pid,self.rid)['references']);self.assertTrue(Path(a['path']).is_file());self.assertEqual(a['width'],60)
        self.assertEqual(a['project_id'],self.pid);self.assertEqual(a['room_id'],self.rid)
    def test_bad_download_does_not_create_reference(self):
        with patch('server.fetch_public_image',return_value=(b'<html>not an image</html>','photo.png')):
            self.call(f'/api/projects/{self.pid}/import-image',{'url':'https://example.com/photo.png','kind':'reference','room_id':self.rid},status=400)
        self.assertEqual(self.st.room(self.pid,self.rid)['references'],[])

if __name__=='__main__':unittest.main()
