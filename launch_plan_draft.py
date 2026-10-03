"""Isolated, loopback drawing review using the existing dashboard/editor.

No Engine instance, worker thread, pairing, model lookup or generation route.
The live project database is never opened. Only drawing saves and sun previews
are permitted; all other mutations are refused.
"""
import argparse,re,json
from pathlib import Path
from urllib.parse import urlparse
from server import Handler, StudioHTTPServer, ROOT
from store import Store

class DraftEngine:
    def health(self,*args,**kwargs):return {'connected':False,'running':0,'pending':0,'draft_only':True}

class DraftHandler(Handler):
    def do_GET(self):
        path=urlparse(self.path).path
        if path=='/api/local-setup':
            try:self.origin_check()
            except PermissionError as e:return self.reply({'error':str(e)},403)
            return self.reply({'error':'Drawing draft only. No renderer or model setup is available.'},403)
        return super().do_GET()
    def mutate(self,method):
        path=urlparse(self.path).path
        if method!='POST' or not re.fullmatch(r'/api/projects/[a-zA-Z0-9]+/plans/[a-zA-Z0-9]+/(drawing|sun-preview)',path):
            return self.reply({'error':'Separate drawing draft only. Generation, approvals, phases and service changes are disabled.'},403)
        return super().mutate(method)
    def send_file(self,path):
        if Path(path)==ROOT/'static'/'index.html':
            # Reuse the real dashboard and plan editor, opening the isolated plan.
            script='''<script>window.addEventListener('load',async()=>{await refresh(true);tab='plan';const p=P();if(p?.floor_plans?.length)await openDrawingEditor({planId:p.floor_plans[0]});});</script>'''
            raw=Path(path).read_text().replace('</body>',script+'</body>').encode()
            self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw);return
        return super().send_file(path)

def make_draft_server(data,port=8778):
    path=Path(data).resolve()
    # Refuse active databases even if invoked with the wrong path.
    db=json.loads((path/'studio.json').read_text())
    if not db['projects'] or not all(p.get('draft_only') is True for p in db['projects'].values()) or db.get('jobs'):
        raise ValueError('Use a separate drawing-only draft database with no jobs.')
    http=StudioHTTPServer(('127.0.0.1',port),DraftHandler)
    http.store=Store(path);http.engine=DraftEngine();http.access=None;http.services=None
    return http

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--data',required=True);parser.add_argument('--port',type=int,default=8778);args=parser.parse_args()
    http=make_draft_server(args.data,args.port)
    print(f'Separate editable drawing draft: http://127.0.0.1:{http.server_port}/',flush=True)
    try:http.serve_forever()
    finally:http.server_close()
