"""Project-owned media folders and copy-before-switch relocation."""
from pathlib import Path
import copy, json, os, re, shutil, subprocess, threading

ACTIVE = ('queued', 'waiting', 'running')
FOLDERS = ('Floor_Plans', 'Rooms', 'Supporting_Files', 'Exports')


def slug(value):
    value = re.sub(r'[^\w -]', '', value, flags=re.UNICODE).strip(' .')[:55]
    return re.sub(r'\s+', '_', value) or 'Project'


def parent_path(value):
    path = Path(str(value).strip().strip('"')).expanduser()
    if not path.is_absolute() or str(path).startswith(('\\\\', '//')):
        raise ValueError('Choose an absolute folder on this PC, for example C:\\PixeloidProjects.')
    if os.name == 'nt' and (not re.match(r'^[A-Za-z]:[\\/]', str(path)) or any(':' in part for part in path.parts[1:])):
        raise ValueError('Choose a regular local drive folder.')
    path = path.resolve()
    if path.exists() and not path.is_dir():
        raise ValueError('The save location must be a folder.')
    return path


def allocate(parent, name, pid):
    parent = parent_path(parent)
    parent.mkdir(parents=True, exist_ok=True)
    base = parent / (slug(name) + '_' + pid[:8])
    target = base
    for number in range(10000):
        target = base if number == 0 else base.with_name(base.name + '_' + str(number+1))
        try:
            target.mkdir()
            break
        except FileExistsError:
            continue
    else:
        raise ValueError('Could not create a unique project folder.')
    for name in FOLDERS:
        (target / name).mkdir()
    return target


def project_root(store, pid):
    return Path(store.project(pid).get('storage_path') or store.root/'projects'/pid).resolve()


def room_path(store, pid, rid):
    # Use immutable IDs so renaming a room never strands its files.
    room=store.room(pid,rid)
    folder=room.setdefault('storage_folder',slug(room['name'])+'_'+rid[:8])
    return project_root(store, pid)/'Rooms'/folder


def upload_folder(store, pid, kind, rid, aid):
    p = store.project(pid)
    if p.get('storage_version') != 2:
        return project_root(store,pid)/'uploads'/aid
    return (project_root(store,pid)/'Floor_Plans' if kind=='plan' else room_path(store,pid,rid)/('Room_References' if kind=='anchor' else 'Furniture_References'))/aid


def job_folder(store, job):
    if job.get('work_dir'):
        return Path(job['work_dir'])
    p = store.project(job['project_id'])
    parent = project_root(store,p['id'])/('Supporting_Files/Jobs' if p.get('storage_version')==2 else 'jobs')
    path = parent/job['id']
    job['work_dir'] = str(path)
    return path


def analysis_folder(store, pid, jid, aid):
    p=store.project(pid)
    return project_root(store,pid)/('Supporting_Files/Analysis' if p.get('storage_version')==2 else 'analysis')/jid/aid


def output_folder(store, job, fallback):
    p=store.project(job['project_id'])
    if p.get('storage_version')!=2:return fallback
    category={'image':'Images','video':'Videos','reference':'Generated_References'}[job['kind']]
    target=room_path(store,p['id'],job['room_id'])/category/job['id']
    target.mkdir(parents=True,exist_ok=True)
    return target


def manifest(store,pid):
    p=copy.deepcopy(store.project(pid));root=project_root(store,pid)
    assets={k:copy.deepcopy(v) for k,v in store.db['assets'].items() if v['project_id']==pid}
    for asset in assets.values():
        path=Path(asset['path']).resolve()
        asset['path']=str(path.relative_to(root)) if path.is_relative_to(root) else str(path)
    jobs={k:copy.deepcopy(v) for k,v in store.db['jobs'].items() if v['project_id']==pid}
    for job in jobs.values():
        if job.get('work_dir'):
            path=Path(job['work_dir']).resolve()
            if path.is_relative_to(root):job['work_dir']=str(path.relative_to(root))
    return {'format':'Pixeloid Studio project','version':1,'project':p,'assets':assets,'jobs':jobs}


def save_manifest(store,pid):
    root=project_root(store,pid);root.mkdir(parents=True,exist_ok=True)
    temp=root/'project.json.tmp'
    temp.write_text(json.dumps(manifest(store,pid),indent=2),encoding='utf8')
    os.replace(temp,root/'project.json')


def describe(store,pid):
    with store.lock:
        p=store.project(pid)
        return {'path':str(project_root(store,pid)), 'organized':p.get('storage_version')==2,
                'default_parent':str((store.root/'projects').resolve()),
                'operation':copy.deepcopy(store.storage_operations.get(pid)),
                'folders':list(FOLDERS),
                'room_folders':['Room_References','Furniture_References','Generated_References','Images','Videos']}


def relocate(store,pid,parent):
    with store.lock:
        p=store.project(pid)
        if pid in store.moving_projects:raise ValueError('This project is already being copied.')
        if any(j['project_id']==pid and j['status'] in ACTIVE for j in store.db['jobs'].values()):
            raise ValueError('Finish or cancel this project’s activities before changing its location.')
        source=project_root(store,pid);parent=parent_path(parent)
        if parent==source or parent.is_relative_to(source):raise ValueError('Choose a location outside the current project folder.')
        store.moving_projects.add(pid)
        snapshot=copy.deepcopy(store.db)
        store.storage_operations[pid]={'status':'copying','progress':0,'stage':'Preparing project files'}
    target=None
    try:
        target=allocate(parent,p['name'],pid)
        marker=target/'COPY_INCOMPLETE.txt';marker.write_text('Original files remain unchanged. This copy is not active until completion.',encoding='utf8')
        previous=target/'Supporting_Files'/'Previous_Location'
        sources=[]
        if source.exists():
            for directory,dirs,files in os.walk(source,followlinks=False):
                for name in dirs:
                    candidate=Path(directory)/name
                    if candidate.is_symlink() or (hasattr(candidate,'is_junction') and candidate.is_junction()):
                        raise ValueError('Project contains a linked folder. Copy it manually before changing location.')
                for name in files:
                    item=Path(directory)/name
                    if item.is_symlink():raise ValueError('Project contains a linked file. Copy it manually first.')
                    sources.append((item,previous/item.relative_to(source)))
        updates={}
        room_folders={r['id']:r.get('storage_folder') or slug(r['name'])+'_'+r['id'][:8] for r in snapshot['projects'][pid]['rooms']}
        category={'plan':'Floor_Plans','anchor':'Room_References','reference':'Furniture_References','reference_candidate':'Generated_References','image':'Images','video':'Videos','music':'Music','film':'Exports'}
        for aid,a in snapshot['assets'].items():
            if a['project_id']!=pid:continue
            original=Path(a['path'])
            if not original.is_file():raise ValueError('A project file is missing: '+a.get('name',aid))
            folder=category.get(a['kind'],'Other_References')
            dest=(target/'Rooms'/room_folders[a['room_id']]/folder if a.get('room_id') else target/folder)/aid/original.name
            sources.append((original,dest));updates[aid]=str(dest)
        total=sum(src.stat().st_size for src,_ in sources);done=0
        if shutil.disk_usage(target).free < total + 16*1024*1024:raise ValueError('Not enough free disk space to copy this project.')
        for src,dst in sources:
            dst.parent.mkdir(parents=True,exist_ok=True)
            with src.open('rb') as reader,dst.open('xb') as writer:
                while chunk:=reader.read(4*1024*1024):
                    writer.write(chunk);done+=len(chunk)
                    with store.lock:store.storage_operations[pid].update(progress=round(done/max(total,1)*95),stage='Copying project files',copied_bytes=done,total_bytes=total)
            shutil.copystat(src,dst)
            if dst.stat().st_size!=src.stat().st_size:raise IOError('A file copy could not be verified.')
        with store.lock:
            store.storage_operations[pid].update(progress=97,stage='Saving project index')
            p['storage_path']=str(target);p['storage_version']=2
            for room in p['rooms']:room['storage_folder']=room_folders[room['id']]
            for aid,path in updates.items():store.db['assets'][aid]['path']=path
            for job in store.db['jobs'].values():
                if job['project_id']!=pid:continue
                old=Path(job['work_dir']) if job.get('work_dir') else source/'jobs'/job['id']
                if old.is_relative_to(source) and old.exists():job['work_dir']=str(previous/old.relative_to(source))
            try:
                save_manifest(store,pid);store.save()
            except Exception:
                store.db=snapshot
                raise
            try:marker.unlink()
            except OSError:pass
            store.storage_operations[pid].update(status='completed',progress=100,stage='Project folder ready',path=str(target))
        return describe(store,pid)
    except Exception as exc:
        with store.lock:store.storage_operations[pid]={'status':'failed','progress':None,'stage':'Original location preserved','error':str(exc),'partial_copy':str(target) if target else None}
        raise
    finally:
        with store.lock:store.moving_projects.discard(pid)


_picker_lock=threading.Lock()
def choose_folder(initial=''):
    if not _picker_lock.acquire(blocking=False):raise ValueError('A folder picker is already open.')
    try:
        if os.name!='nt':raise ValueError('Enter a local folder path in the save location field.')
        proc=subprocess.run(['powershell.exe','-NoProfile','-STA','-ExecutionPolicy','Bypass','-File',str(Path(__file__).with_name('choose_folder.ps1')),'-InitialPath',str(initial)],capture_output=True,timeout=180,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        if proc.returncode:raise ValueError('The folder picker could not open. You can enter the path directly.')
        return json.loads(proc.stdout.decode('utf-8-sig'))
    except subprocess.TimeoutExpired:raise ValueError('The folder picker timed out. Enter the path or browse again.')
    finally:_picker_lock.release()
