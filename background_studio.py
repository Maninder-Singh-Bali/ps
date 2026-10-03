"""Run with pythonw at login. No renderer/model auto-start, browser or console."""
from pathlib import Path
import json, os, sys
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT));os.chdir(ROOT)

def main():
    from background_runtime import InstanceLock,logs
    configuration=Path(sys.argv[1]) if len(sys.argv)>1 else ROOT/'lan.local.json'
    c=json.loads(configuration.read_text(encoding='utf-8-sig'))
    private=Path(c['private_dir']);private.mkdir(parents=True,exist_ok=True)
    sys.stdout=sys.stderr=logs(private/'logs')
    lock=InstanceLock(private/'dashboard.lock')
    data=Path(c['data']).resolve();data.mkdir(parents=True,exist_ok=True)
    data_lock=InstanceLock(data/'dashboard.lock')
    if c.get('node'):os.environ['PIXELOID_NODE']=c['node'];os.environ['NODE_PATH']=str(Path(c['node']).parent/'node_modules')
    from server import make_server
    http=make_server(data,c.get('port',8790),access_config=c)
    (private/'dashboard.pid').write_text(str(os.getpid()),encoding='utf-8')
    print('Studio background dashboard started. Processing requires Prepare Studio.',flush=True)
    try:http.serve_forever()
    finally:http.engine.stop.set();http.server_close()

if __name__=='__main__':
    try:main()
    except Exception:
        import traceback
        traceback.print_exc()
