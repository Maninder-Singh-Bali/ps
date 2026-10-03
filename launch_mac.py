"""Start the lightweight local dashboard detached; never starts a Mac model service."""
import argparse, json, os, subprocess, sys, time, webbrowser
from pathlib import Path
import requests

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--data',required=True);ap.add_argument('--remote-config',required=True);ap.add_argument('--port',type=int,default=8777);a=ap.parse_args()
    root=Path(__file__).resolve().parent;data=Path(a.data).resolve();data.mkdir(parents=True,exist_ok=True)
    c=Path(a.remote_config).resolve()
    if not c.is_file():raise ValueError('Configure the private PC pairing file first.')
    url=f'http://127.0.0.1:{a.port}';s=requests.Session();s.trust_env=False
    try:
        existing=s.get(url+'/api/identity',timeout=2)
        if existing.status_code==200:raise ValueError('A dashboard already uses this port. Open it or deliberately stop it before changing data directories.')
    except requests.ConnectionError:pass
    with (data/'dashboard.log').open('ab') as log:
        p=subprocess.Popen([sys.executable,str(root/'server.py'),'--port',str(a.port),'--data',str(data),'--remote-config',str(c)],cwd=root,stdout=log,stderr=log,start_new_session=True)
    (data/'dashboard.pid').write_text(str(p.pid))
    for _ in range(30):
        if p.poll() is not None:raise RuntimeError('Dashboard startup failed; inspect dashboard.log.')
        try:
            if s.get(url+'/api/identity',timeout=1).status_code==200:break
        except requests.RequestException:pass
        time.sleep(.3)
    else:raise RuntimeError('Dashboard startup timed out; inspect dashboard.log.')
    webbrowser.open(url);print('Dashboard ready at '+url+'. Processing stays on the PC.')

if __name__=='__main__':main()
