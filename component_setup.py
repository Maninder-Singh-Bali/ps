"""Pinned, opt-in model downloads. Never called by inference or plan import."""
import hashlib,os,shutil
from pathlib import Path
from urllib.parse import urlparse,urljoin
import requests
from standalone import config
from store import now,uid

CATALOG={
 'flux-klein-4b-fp8':{
  'name':'FLUX.2 Klein 4B FP8 model', 'bytes':4070624520,
  'sha256':'97ed34fe0567e436200f2faee3939b88f2b5d99f8af2a4dc16532c4245c0ccb6',
  'file':'diffusion_models/flux-2-klein-4b-fp8.safetensors',
  'url':'https://huggingface.co/black-forest-labs/FLUX.2-klein-4b-fp8/resolve/c30fa39e0d916333415ae96c66169d8cfdca3e63/flux-2-klein-4b-fp8.safetensors',
  'licence':'Apache 2.0',
  'licence_url':'https://huggingface.co/black-forest-labs/FLUX.2-klein-4b-fp8/blob/c30fa39e0d916333415ae96c66169d8cfdca3e63/LICENSE.md',
  'note':'Diffusion model only. The local Qwen encoder and FLUX VAE are also required. Retain the licence and notices when redistributing.'}}

def destination(engine,item):
 base=Path(config(engine.app_root).get('comfy_root',''))
 if not (base/'main.py').is_file():raise ValueError('Connect the installed local engine in Setup first.')
 models=(base/'models').resolve();target=(models/item['file']).resolve()
 if not target.is_relative_to(models):raise ValueError('Invalid component destination.')
 return target

def catalog(engine):
 rows=[]
 for key,item in CATALOG.items():
  row={**item,'id':key,'installed':False}
  try:
   target=destination(engine,item);row['installed']=target.is_file() and target.stat().st_size==item['bytes']
   row['free_bytes']=shutil.disk_usage(target.parent if target.parent.exists() else Path(config(engine.app_root)['comfy_root'])).free
  except (ValueError,OSError):row['free_bytes']=None
  rows.append(row)
 return rows

def queue(engine,pid,data):
 item=CATALOG.get(data.get('component_id'))
 if not item or data.get('approved') is not True or data.get('sha256')!=item['sha256']:
  raise ValueError('Review the component size and licence, then explicitly approve its download in Setup.')
 target=destination(engine,item)
 if target.exists():raise ValueError('A file already exists at this component location. It was not replaced. Check installed components first.')
 if shutil.disk_usage(Path(config(engine.app_root)['comfy_root'])).free<item['bytes']+512*1024**2:
  raise ValueError('Insufficient local storage for this download and its verification buffer.')
 consent={'sha256':item['sha256'],'bytes':item['bytes'],'licence':item['licence'],'approved_at':now()}
 if pid:return engine.store.new_job(pid,'component_download',component_id=data['component_id'],download_consent=consent)
 with engine.store.lock:
  for job in engine.store.db['jobs'].values():
   if job['kind']=='component_download' and job.get('component_id')==data['component_id'] and job['status'] in ('queued','waiting','running'):return job
  job={'id':uid(),'project_id':None,'room_id':None,'kind':'component_download','component_id':data['component_id'],'download_consent':consent,
       'status':'queued','stage':'Approved download queued','progress':None,'created':now(),'updated':now(),'error':None,'prompt_id':None,'events':[]}
  engine.store.db['jobs'][job['id']]=job;engine.store.save();return job

def trusted_download(url):
 host=urlparse(url).hostname or ''
 return urlparse(url).scheme=='https' and (host=='huggingface.co' or host.endswith(('.huggingface.co','.hf.co')))

def run(engine,job):
 item=CATALOG[job['component_id']]
 if job.get('download_consent',{}).get('sha256')!=item['sha256']:raise ValueError('Component changed since approval. Review its current licence and download size in Setup.')
 target=destination(engine,item);target.parent.mkdir(parents=True,exist_ok=True)
 if target.exists():raise ValueError('Existing model file retained; it was not overwritten.')
 part=target.with_suffix(target.suffix+'.pixeloid-part');offset=part.stat().st_size if part.exists() else 0
 if offset>item['bytes']:raise ValueError('Partial download exceeds the approved size; retained for inspection.')
 st=engine.store;st.update_job(job['id'],status='running',stage='Downloading approved model',started=now(),progress=round(offset/item['bytes']*90))
 session=requests.Session();session.trust_env=False
 try:
  if offset<item['bytes']:
   url=item['url'];response=None
   for _ in range(6):
    if not trusted_download(url):raise ValueError('Download redirected outside the approved model host; stopped.')
    response=session.get(url,headers={'Range':f'bytes={offset}-'} if offset else {},stream=True,allow_redirects=False,timeout=(15,30))
    if response.is_redirect:
     url=urljoin(url,response.headers['Location']);response.close();continue
    break
   if response is None or response.is_redirect:raise ValueError('Too many model-download redirects.')
   response.raise_for_status()
   if offset and response.status_code==206 and not response.headers.get('Content-Range','').startswith(f'bytes {offset}-'):
    raise ValueError('Download resume offset does not match; partial file retained.')
   if offset and response.status_code==200:offset=0
   with response,part.open('ab' if offset else 'wb') as output:
    last=-1
    for block in response.iter_content(4*1024*1024):
     if engine.stop.is_set() or job['status']=='cancelled':return
     offset+=len(block)
     if offset>item['bytes']:raise ValueError('Download exceeds approved size; stopped.')
     output.write(block);percent=round(offset/item['bytes']*90)
     if percent!=last:st.update_job(job['id'],progress=percent,stage=f'Downloading approved model · {offset/1e9:.2f} / {item["bytes"]/1e9:.2f} GB');last=percent
  if offset!=item['bytes']:raise ValueError('Download interrupted. Retry resumes the saved partial file.')
  st.update_job(job['id'],stage='Verifying downloaded model',progress=95);digest=hashlib.sha256()
  with part.open('rb') as source:
   while block:=source.read(8*1024*1024):
    if engine.stop.is_set() or job['status']=='cancelled':return
    digest.update(block)
  if digest.hexdigest()!=item['sha256']:
   os.rename(part,part.with_name(part.name+'.rejected-'+str(int(now()))))
   raise ValueError('Model checksum failed. The file was quarantined and not installed. Retry starts a fresh download.')
  if target.exists():raise ValueError('A model was installed concurrently. Existing file retained.')
  # Windows rename refuses an existing destination, preserving concurrent installs.
  os.rename(part,target)
  st.update_job(job['id'],status='completed',stage='Verified model installed locally',progress=100,finished=now())
 finally:session.close()
