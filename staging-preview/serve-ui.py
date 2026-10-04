from http.server import ThreadingHTTPServer,SimpleHTTPRequestHandler
from pathlib import Path
root=Path(__file__).resolve().parents[1]/'verification/https-staging-ui-20261004/site'
class Handler(SimpleHTTPRequestHandler):
 def __init__(self,*a,**k):super().__init__(*a,directory=str(root),**k)
 def do_GET(self):
  if not self.path.startswith('/ps/'):
   self.send_error(404);return
  self.path=self.path[3:];super().do_GET()
 def end_headers(self):
  self.send_header('Cache-Control','no-store');super().end_headers()
http=ThreadingHTTPServer(('127.0.0.1',0),Handler);print(http.server_port,flush=True);http.serve_forever()
