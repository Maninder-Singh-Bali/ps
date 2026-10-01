"""Import public image URLs from an intentional browser drop. No cookies or credentials."""
import http.client, ipaddress, socket, ssl, time
from urllib.parse import urlsplit, urljoin, unquote
from pathlib import PurePosixPath

LIMIT=32*1024*1024

def public_target(url):
    if not isinstance(url,str) or len(url)>8192:raise ValueError('The image link is invalid.')
    try:
        p=urlsplit(url)
        if p.scheme not in ('http','https') or not p.hostname or p.username or p.password:raise ValueError()
        host=p.hostname.encode('idna').decode('ascii');port=p.port or (443 if p.scheme=='https' else 80)
        if port not in (80,443) or any(c in url for c in '\r\n\x00'):raise ValueError()
    except (ValueError,UnicodeError):raise ValueError('Drop a public HTTP or HTTPS image link without login credentials.')
    try:addresses=list(dict.fromkeys(row[4][0] for row in socket.getaddrinfo(host,port,type=socket.SOCK_STREAM)))
    except OSError:raise ValueError('The image website could not be reached. Try saving the image and uploading the file.')
    if not addresses or any(not ipaddress.ip_address(ip).is_global for ip in addresses):raise ValueError('Only public website images can be imported by link. For local images, drag the file itself.')
    return p,host,port,addresses[0]

class PinnedHTTP(http.client.HTTPConnection):
    def __init__(self,host,port,ip,timeout):super().__init__(host,port,timeout=timeout);self.target_ip=ip
    def connect(self):self.sock=socket.create_connection((self.target_ip,self.port),self.timeout)

class PinnedHTTPS(http.client.HTTPSConnection):
    def __init__(self,host,port,ip,timeout):super().__init__(host,port,timeout=timeout,context=ssl.create_default_context());self.target_ip=ip
    def connect(self):
        sock=socket.create_connection((self.target_ip,self.port),self.timeout)
        try:self.sock=self._context.wrap_socket(sock,server_hostname=self.host)
        except BaseException:sock.close();raise

def open_image_response(parsed,host,port,ip,timeout):
    conn=(PinnedHTTPS if parsed.scheme=='https' else PinnedHTTP)(host,port,ip,timeout)
    try:
        path=parsed.path or '/'
        if parsed.query:path+='?'+parsed.query
        conn.request('GET',path,headers={'Accept':'image/avif,image/webp,image/png,image/jpeg,image/*;q=0.8','User-Agent':'Mozilla/5.0 (compatible; PixeloidStudio/1.0)','Connection':'close'})
        return conn,conn.getresponse()
    except BaseException:conn.close();raise

def fetch_public_image(url):
    deadline=time.monotonic()+45
    try:
        for redirect in range(5):
            parsed,host,port,ip=public_target(url)
            remaining=deadline-time.monotonic()
            if remaining<=0:raise TimeoutError()
            conn,response=open_image_response(parsed,host,port,ip,min(15,remaining))
            try:
                if response.status in (301,302,303,307,308):
                    target=response.getheader('Location')
                    if not target:raise ValueError('The website returned an incomplete image link.')
                    url=urljoin(url,target);continue
                if response.status!=200:raise ValueError('This website blocked the image download. Save the image to your PC and drop that file instead.')
                content_type=response.getheader('Content-Type','').split(';')[0].strip().lower()
                if content_type and not content_type.startswith('image/') and content_type!='application/octet-stream':raise ValueError('This is a webpage link. Drag the actual photo, or save the photo and upload it.')
                try:declared=int(response.getheader('Content-Length','0'))
                except ValueError:declared=0
                if declared>LIMIT:raise ValueError('Images must be smaller than 32 MB.')
                chunks=[];size=0
                while True:
                    remaining=deadline-time.monotonic()
                    if remaining<=0:raise TimeoutError()
                    if conn.sock:conn.sock.settimeout(min(15,remaining))
                    chunk=response.read(min(65536,LIMIT+1-size))
                    if not chunk:break
                    size+=len(chunk)
                    if size>LIMIT:raise ValueError('Images must be smaller than 32 MB.')
                    chunks.append(chunk)
                if not size:raise ValueError('The website returned an empty image.')
                name=PurePosixPath(unquote(parsed.path)).name or 'web-reference'
                return b''.join(chunks),name[:180]
            finally:response.close();conn.close()
        raise ValueError('The image link redirected too many times. Save the image and upload it instead.')
    except (OSError,http.client.HTTPException):raise ValueError('The image website could not complete the download. Save the image to your PC and drop that file instead.')
