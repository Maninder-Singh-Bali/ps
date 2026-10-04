"""Manual plan drafts: canonical drawing features, separate from the active Store.

No engine, queue or apply route. Files are atomic and optimistic revision checked.
"""
import copy, hashlib, io, json, math, os, re, threading, uuid
from pathlib import Path
from datetime import datetime, timezone
from contextvars import ContextVar
from contextlib import contextmanager
from PIL import Image, ImageOps

ROOT=Path(__file__).resolve().parent.parent/'working-drafts'
_workspace_root=ContextVar('draft_workspace_root',default=None)
@contextmanager
def use_root(root):
    token=_workspace_root.set(Path(root).resolve())
    try:yield
    finally:_workspace_root.reset(token)
def workspace_root():return _workspace_root.get() or ROOT
LOCK=threading.RLock()
def stamp():return datetime.now(timezone.utc).isoformat()
def folder(key):
    if not re.fullmatch(r'[a-zA-Z0-9_-]{1,64}',key):raise ValueError('Invalid draft identity.')
    return workspace_root()/key

def atomic(path,data):
    path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_suffix('.tmp')
    with tmp.open('w') as f:json.dump(data,f,indent=2,allow_nan=False);f.flush();os.fsync(f.fileno())
    tmp.replace(path)

def get(key):return json.loads((folder(key)/'draft.json').read_text())
def listing():
    return [{'id':d['id'],'name':d['name'],'revision':d['revision'],'updated':d.get('updated'),'count':len(d['features'])} for p in sorted(workspace_root().glob('*/draft.json')) for d in [json.loads(p.read_text())]]
def number(v,lo,hi,label):
    if type(v) not in (int,float) or not math.isfinite(v) or not lo<=v<=hi:raise ValueError('Invalid '+label)
    return float(v)
def validate(data,base):
    d=copy.deepcopy(base);d['name']=str(data.get('name',base['name']))[:120]
    fs=data.get('features',[])
    if not isinstance(fs,list) or len(fs)>1000:raise ValueError('Use at most 1000 elements.')
    seen=set()
    for f in fs:
        if not isinstance(f,dict) or not re.fullmatch(r'[\w:-]{1,100}',f.get('id','')) or f['id'] in seen:raise ValueError('Invalid or repeated element identity.')
        seen.add(f['id'])
        if f.get('kind') not in ('wall','door','window','sliding_door','line','floor_opening'):raise ValueError('Invalid element type.')
        if not isinstance(f.get('points'),list) or len(f['points'])!=2:raise ValueError('Two endpoints required.')
        for p in f['points']:
            if len(p)!=2:raise ValueError('Invalid point.')
            number(p[0],-base['width'],base['width']*2,'x');number(p[1],-base['height'],base['height']*2,'y')
        if math.dist(*f['points'])<.001:raise ValueError('Zero length element.')
        number(f.get('thickness',1.5),.01,500,'thickness')
        for k in ('height_m','head_m','sill_m','base_m'):
            if k in f:number(f[k],0,20,k)
        if 'head_m' in f and f['head_m']<=(f.get('sill_m',.9) if f['kind']=='window' else f.get('base_m',0)):raise ValueError('Head must be above sill.')
        if 'host_wall_id' in f:
            if f['kind'] not in ('door','window','sliding_door'):raise ValueError('Only openings can have a host.')
            number(f.get('normal_offset',0),-100000,100000,'frame offset');number(f.get('frame_thickness',f['thickness']),.001,100000,'frame thickness')
            number(f.get('offset'),-100000,100000,'opening distance');number(f.get('width'),.01,100000,'opening width')
    for f in fs:
        if f.get('host_wall_id') and not any(w['id']==f['host_wall_id'] and w['kind']=='wall' for w in fs):raise ValueError('Opening host is missing.')
    d['features']=copy.deepcopy(fs)
    if 'surface_design' in data:
        import surface_design
        d['surface_design']=surface_design.validate(data['surface_design'])
    c=data.get('calibration')
    if c:
        pts=c.get('points',[])
        if len(pts)!=2 or any(len(p)!=2 for p in pts):raise ValueError('Calibration needs two points.')
        for p in pts:
            for v in p:number(v,-100000,100000,'calibration point')
        m=number(c.get('metres'),.001,10000,'calibration length');px=math.dist(*pts)
        if px<.1:raise ValueError('Calibration points are too close.')
        d['calibration']={**copy.deepcopy(c),'metres_per_pixel':m/px}
    else:d['calibration']=None
    bg=data.get('background',{});d['background']={k:number(bg.get(k,v),lo,hi,k) for k,v,lo,hi in [('x',0,-100000,100000),('y',0,-100000,100000),('rotation',0,-360,360),('opacity',.7,0,1)]}
    d['background'].update(visible=bg.get('visible',True) is True,locked=bg.get('locked',True) is True)
    d['wall_height_m']=number(data.get('wall_height_m',2.5),.2,20,'wall height')
    d['background_alignment_unverified']=data.get('background_alignment_unverified',False) is True
    if data.get('opening_attachment_revision')==1:d['opening_attachment_revision']=1
    d['notes']=str(data.get('notes',''))[:12000];d['units']=data.get('units') if data.get('units') in ('m','ft','in') else 'm'
    d['room_names']={str(k)[:300]:str(v)[:100] for k,v in data.get('room_names',{}).items()}
    return d

def save(key,data):
    with LOCK:
        base=get(key)
        if data.get('revision')!=base['revision']:raise ValueError('This draft changed in another window. Reopen before saving; your changes were not written.')
        d=validate(data,base);reference_files(d);d['revision']+=1;d['updated']=stamp();atomic(folder(key)/'draft.json',d);return d

def upload(raw,name):
    if not raw or len(raw)>32*1024*1024:raise ValueError('Choose a PDF or image up to 32 MB.')
    suffix=Path(name).suffix.lower()
    if suffix not in ('.pdf','.png','.jpg','.jpeg','.webp'):raise ValueError('Choose PDF, PNG, JPEG or WebP.')
    key=uuid.uuid4().hex[:16];root=folder(key);root.mkdir(parents=True)
    (root/('original'+suffix)).write_bytes(raw);pages=[]
    if suffix=='.pdf':
        import fitz
        with fitz.open(stream=raw,filetype='pdf') as pdf:
            if pdf.is_encrypted:raise ValueError('Unlock this PDF before importing.')
            if len(pdf)>20:raise ValueError('Export up to 20 pages before importing.')
            for i,page in enumerate(pdf):
                pix=page.get_pixmap(matrix=fitz.Matrix(2800/max(page.rect.width,page.rect.height),2800/max(page.rect.width,page.rect.height)),alpha=False)
                pix.save(root/f'page-{i+1}.png')
                pages.append({'page':i+1,'width':pix.width,'height':pix.height,'rotation':page.rotation,'vector_paths':len(page.get_drawings()),'raster_images':len(page.get_images()),'url':f'/api/plan-drafts/{key}/files/page-{i+1}.png'})
    else:
        im=ImageOps.exif_transpose(Image.open(io.BytesIO(raw))).convert('RGB');im.thumbnail((2800,2800));im.save(root/'page-1.png');pages=[{'page':1,'width':im.width,'height':im.height,'raster_images':1,'vector_paths':0,'url':f'/api/plan-drafts/{key}/files/page-1.png'}]
    manifest={'id':key,'name':Path(name).name,'original':'original'+suffix,'source_sha256':hashlib.sha256(raw).hexdigest(),'pages':pages};atomic(root/'import.json',manifest);return manifest

def create(key,page):
    with LOCK:
        root=folder(key)
        if (root/'draft.json').exists():raise ValueError('This import already has a draft. Upload again for a separate page.')
        m=json.loads((root/'import.json').read_text());p=next((p for p in m['pages'] if p['page']==page),None)
        if not p:raise ValueError('Choose a page.')
        d={'id':key,'name':m['name']+' · page '+str(page),'revision':1,'width':p['width'],'height':p['height'],'source_url':p['url'],'original_url':f'/api/plan-drafts/{key}/files/'+m['original'],'source_sha256':m['source_sha256'],'source_page':p,'features':[],'calibration':None,'background':{'x':0,'y':0,'rotation':0,'opacity':.7,'visible':True,'locked':True},'wall_height_m':2.5,'units':'m','notes':'','review':{'issues':[]},'room_names':{},'updated':stamp(),'draft_only':True}
        atomic(root/'draft.json',d);return d

def scene_store(data, camera=None):
    """Use the existing shared-floor builder with a read-only in-memory Store facade."""
    d=validate(data,data)
    if not d['calibration']:raise ValueError('Calibrate first for a metric 3D preview. Unscaled tracing is still available.')
    from drawing_scene import resolve
    from shared_floor import build
    points=[p for f in d['features'] for p in f['points']]
    if not points:raise ValueError('Trace a wall first.')
    x,y=min(p[0] for p in points),min(p[1] for p in points);xx,yy=max(p[0] for p in points),max(p[1] for p in points)
    pad=max(10,max(xx-x,yy-y)*.03);bounds=[(x-pad)/d['width'],(y-pad)/d['height'],(xx-x+pad*2)/d['width'],(yy-y+pad*2)/d['height']]
    room={'id':'preview','plan_id':d['id'],'name':'Correction draft','floor':'Draft','bbox':bounds,'block_layout':{'items':[]}}
    plan={'draft_only':True,'id':d['id'],'project_id':'draft','width':d['width'],'height':d['height'],'drawing':{'features':d['features'],'site':{'model':{'metres_per_pixel':d['calibration']['metres_per_pixel'],'scale_source':'User drawing calibration; not surveyed','wall_heights':{'Draft':d['wall_height_m']}}}}}
    plan['surface_reference_files']=reference_files(d)
    project={'id':'draft','rooms':[room],'measurements':[]}
    class Snapshot:
        db={'assets':{d['id']:plan}}
        _review_cache={('architecture',d['id']):resolve({'features':d['features']})}
        def asset(self,key):return self.db['assets'][key]
        def project(self,key):return project
    if d.get('surface_design'):
        plan['drawing'].update(surface_design=copy.deepcopy(d['surface_design']),surface_design_floor='Draft')
    if camera:plan['floor_cameras']={'preview':copy.deepcopy(camera)}
    return Snapshot(),room,d


def preview(data):
    from shared_floor import build
    store,room,d=scene_store(data)
    scene=build(store,room)
    scene['draft_only']=True;return scene

def footprint(data):
    d=validate(data,data)
    import wall_junctions
    return wall_junctions.resolve(d['features'],d['wall_height_m'])

def upload_reference(key,raw,name):
    """Keep original bytes outside JSON; the embedded derivative is display-only."""
    root=folder(key)
    if not (root/'draft.json').exists():raise ValueError('Save/import this draft before adding a reference.')
    if not raw or len(raw)>32*1024*1024:raise ValueError('Choose a reference up to 32 MB.')
    with Image.open(io.BytesIO(raw)) as im:
        ext={'PNG':'png','JPEG':'jpg','WEBP':'webp'}.get(im.format)
        if not ext or im.width*im.height>64_000_000:raise ValueError('Choose PNG, JPEG or WebP up to 64 megapixels.')
        width,height=im.size;im.load();thumb=ImageOps.exif_transpose(im).convert('RGB');display_width,display_height=thumb.size;thumb.thumbnail((512,512));buf=io.BytesIO();thumb.save(buf,'JPEG',quality=85);preview=buf.getvalue()
    sha=hashlib.sha256(raw).hexdigest();target=root/'references'/(sha+'.'+ext);target.parent.mkdir(parents=True,exist_ok=True)
    with LOCK:
        if target.exists() and hashlib.sha256(target.read_bytes()).hexdigest()!=sha:raise ValueError('Reference file failed its hash check.')
        if not target.exists():
            tmp=target.with_suffix('.tmp');tmp.write_bytes(raw);tmp.replace(target)
    import base64
    return {'asset':{'sha256':sha,'bytes':len(raw),'file':target.name,'width':width,'height':height,'source_name':Path(name).name},'image':'data:image/jpeg;base64,'+base64.b64encode(preview).decode(),'image_width':display_width,'image_height':display_height,'preview_only':True,'thumbnail':{'sha256':hashlib.sha256(preview).hexdigest(),'width':thumb.width,'height':thumb.height,'format':'JPEG','quality':85,'purpose':'UI/guide preview; generation uses original asset'}}

def reference_files(d,existing=None):
    files={};design=d.get('surface_design') or {}
    for row in design.get('surfaces',[])+design.get('items',[]):
        for r in (row.get('reference',{}),row.get('finish',{}).get('reference',{})):
            a=r.get('asset')
            if not a:continue
            if not re.fullmatch(r'[0-9a-f]{64}\.(png|jpg|webp)',a.get('file','')) or not a['file'].startswith(a.get('sha256','')+'.'):raise ValueError('Invalid reference asset identity.')
            path=folder(d['id'])/'references'/a['file']
            if not path.exists() and existing and a['sha256'] in existing:path=Path(existing[a['sha256']])
            if not path.is_file() or path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest()!=a['sha256']:raise ValueError('Original reference is missing or changed. Reattach the original file before saving or preparing generation.')
            files[a['sha256']]=str(path.resolve())
    return files
