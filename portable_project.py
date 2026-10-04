"""Private copy, never synchronization. Export one project; import into empty data.

Files are content-addressed; all asset IDs/history are retained. Configuration,
credentials and other projects never enter the archive. No archive extractall.
"""
import argparse, copy, hashlib, json, re, zipfile
from pathlib import Path
from store import Store

FORMAT='Pixeloid private portable project v1'
SAFE={'.png','.jpg','.jpeg','.webp','.pdf','.dxf','.svg','.json','.txt','.glb','.mp4','.csv','.obj','.mtl'}

def export_project(database,pid,destination):
    db=json.loads(Path(database).read_text(encoding='utf-8'));p=db['projects'][pid]
    if any(j['project_id']==pid and j['status'] in ('running','waiting','queued') for j in db['jobs'].values()):raise ValueError('Finish this project’s active jobs before exporting.')
    payload={'format':FORMAT,'project':copy.deepcopy(p),
             'assets':{k:copy.deepcopy(a) for k,a in db['assets'].items() if a['project_id']==pid},
             'jobs':{k:copy.deepcopy(j) for k,j in db['jobs'].items() if j['project_id']==pid}}
    files={};mapping={};omitted=[]
    def include(path):
        path=Path(path)
        if not path.is_file() or path.suffix.lower() not in SAFE or path.name.lower() in ('access.txt','credentials.json'):return None
        raw=path.read_bytes();key='files/'+hashlib.sha256(raw).hexdigest()+path.suffix.lower()
        files[key]=raw;mapping[str(path)]=key;return key
    for a in payload['assets'].values():
        if not include(a['path']):raise ValueError('Missing registered asset: '+a['id'])
        for path in a.get('surface_reference_files',{}).values():
            if not include(path):raise ValueError('Missing original surface reference.')
        for path in a.get('manual_source_files',{}).values():
            if not include(path):raise ValueError('Missing manual plan source.')
    def rewrite(value,key=''):
        if isinstance(value,dict):
            return {k:rewrite(v,k) for k,v in value.items() if k not in ('storage_path','work_dir','remote_job_id','remote_result')}
        if isinstance(value,list):return [rewrite(v,key) for v in value]
        if isinstance(value,str) and re.fullmatch(r'/api/plan-drafts/[a-zA-Z0-9_-]+/files/[a-zA-Z0-9_.-]+',value):return value
        if isinstance(value,str) and (re.match(r'^[A-Za-z]:[\\/]',value) or value.startswith('/')):
            if value in mapping:return {'$file':mapping[value]}
            # Original plans, saved overlays and source evidence linked by metadata.
            if key.endswith(('path','file')) and include(value):return {'$file':mapping[value]}
            omitted.append(key);return '[PC-local path omitted]'
        return value
    payload=rewrite(payload)
    payload['project'].pop('storage_version',None)
    payload['transfer']={'mode':'copy','authority':'Mac after import; Windows copy remains a preserved snapshot. No automatic synchronization.',
                         'omitted_machine_path_fields':sorted(set(omitted))}
    target=Path(destination);target.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(target,'x',zipfile.ZIP_DEFLATED) as z:
        z.writestr('project.json',json.dumps(payload,indent=2))
        for name,raw in files.items():z.writestr(name,raw)
    return {'assets':len(payload['assets']),'jobs':len(payload['jobs']),'files':len(files),'bytes':target.stat().st_size,'omitted_fields':sorted(set(omitted))}

def import_project(archive,data):
    target=Path(data).resolve()
    if (target/'studio.json').exists():raise ValueError('Import into a NEW empty data directory; existing work will not be overwritten.')
    with zipfile.ZipFile(archive) as z:
        if sum(i.file_size for i in z.infolist())>10*1024**3:raise ValueError('Archive exceeds 10 GB limit.')
        payload=json.loads(z.read('project.json'))
        if payload.get('format')!=FORMAT:raise ValueError('Unsupported private project export.')
        pid=payload['project']['id']
        if not re.fullmatch(r'[a-f0-9]{16,64}',pid):raise ValueError('Invalid project ID.')
        files={}
        for info in z.infolist():
            if info.filename=='project.json':continue
            if not re.fullmatch(r'files/[a-f0-9]{64}\.[a-z0-9]+',info.filename):raise ValueError('Unsafe archive path.')
            raw=z.read(info)
            if hashlib.sha256(raw).hexdigest()!=Path(info.filename).stem:raise ValueError('Project file checksum mismatch.')
            files[info.filename]=raw
    base=target/'projects'/pid
    def restore(value):
        if isinstance(value,dict):
            if set(value)=={'$file'}:
                if value['$file'] not in files:raise ValueError('Missing portable project file.')
                return str(base/value['$file'])
            return {k:restore(v) for k,v in value.items()}
        if isinstance(value,list):return [restore(v) for v in value]
        return value
    payload=restore(payload)
    for name,raw in files.items():
        path=base/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw)
    store=Store(target);store.db['projects'][pid]=payload['project'];store.db['assets']=payload['assets'];store.db['jobs']=payload['jobs']
    store.db['settings']['auto_release']=False;store.save()
    return {'project_id':pid,'assets':len(payload['assets']),'jobs':len(payload['jobs'])}

if __name__=='__main__':
    ap=argparse.ArgumentParser();sub=ap.add_subparsers(dest='operation',required=True)
    e=sub.add_parser('export');e.add_argument('database');e.add_argument('project_id');e.add_argument('zip')
    i=sub.add_parser('import');i.add_argument('zip');i.add_argument('data')
    a=ap.parse_args();print(json.dumps(export_project(a.database,a.project_id,a.zip) if a.operation=='export' else import_project(a.zip,a.data),indent=2))
