"""Local maintenance client; no remote execution capability."""
import argparse,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from remote_processing import Client
ap=argparse.ArgumentParser();ap.add_argument('action',choices=['status','maintenance','resume']);ap.add_argument('--config',required=True)
a=ap.parse_args();c=Client(a.config)
try:
    d=c.get('/v1/status') if a.action=='status' else c.post('/v1/actions/'+a.action,{})
    print('Worker:',d['state'],'active jobs:',d['active_jobs'],'paused:',d['paused'])
except Exception as e:print(str(e));sys.exit(1)
