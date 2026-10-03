"""Four fixed pass-through capture nodes. No model or encoder mathematics change.
Large artifacts stay in output/Pixeloid_Worker/<job>/capture-v1 on the PC.
"""
import hashlib,json,os,re,shutil,sys,time
from pathlib import Path
import folder_paths

PROFILE='ltx-preview-capture-v1'

def extension_fingerprint():
    here=Path(__file__).resolve().parent
    hashes={name:sha(here/name) for name in ('__init__.py','runtime_sources.json')}
    return hashlib.sha256(json.dumps(hashes,sort_keys=True,separators=(',',':')).encode()).hexdigest(),hashes

def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()

def directory(job_id):
    if not re.fullmatch('[a-f0-9]{16,64}',str(job_id)):raise ValueError('Invalid capture job identity.')
    output=Path(folder_paths.get_output_directory()).resolve()
    p=output/'Pixeloid_Worker'/job_id/'capture-v1'
    if not p.resolve().is_relative_to(output):raise ValueError('Capture directory escapes renderer output.')
    return p

def write_json(path,value):
    temporary=path.with_suffix(path.suffix+'.part')
    temporary.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    os.replace(temporary,path)

def measure():
    result={'measured_at_unix':time.time(),'scope':'Instantaneous Comfy process readings; not per-render peaks; no counters reset.'}
    try:
        import psutil
        result['process_rss_gib']=psutil.Process().memory_info().rss/2**30
    except Exception as exc:
        result['process_rss_gib']=None;result['rss_unavailable']=type(exc).__name__
    import torch
    try:
        if torch.cuda.is_initialized():
            device=torch.cuda.current_device()
            result.update(cuda_device=device,cuda_allocated_gib=torch.cuda.memory_allocated(device)/2**30,cuda_reserved_gib=torch.cuda.memory_reserved(device)/2**30)
        else:result['cuda']='not initialized; no CUDA initialization requested'
    except Exception as exc:result['cuda_unavailable']=type(exc).__name__
    return result

def record(p,stage,started,files):
    m=json.loads((p/'manifest.json').read_text())
    m['stages'][stage]={'elapsed_seconds':time.perf_counter()-started,'measurement':measure(),'files':files}
    write_json(p/'manifest.json',m)
    return m

def file_record(p):return {'name':p.name,'sha256':sha(p),'bytes':p.stat().st_size}

def tensor_file(p,name,tensors,metadata):
    # Copy to host once, without a GPU clone or dtype conversion. Contiguity is
    # established on CPU. Serialization uses Comfy's existing safetensors writer.
    import comfy.utils
    host={key:value.detach().cpu().contiguous() for key,value in tensors.items()}
    spec={key:{'shape':list(value.shape),'dtype':str(value.dtype),'source_device':str(value.device)} for key,value in tensors.items()}
    target=p/name;temporary=p/(name+'.part')
    comfy.utils.save_torch_file(host,str(temporary),metadata={'pixeloid_capture':json.dumps(metadata)})
    os.replace(temporary,target)
    return {**file_record(target),'tensors':spec}

def cpu_images(images,shape):
    if tuple(images.shape)!=shape or images.device.type!='cpu':
        raise ValueError('Capture expects the pinned CPU image tensor shape; refusing extra GPU frame copies or changed preparation.')

def schemas(kind):return {'required':{kind[0]:(kind[1],),'job_id':('STRING',)},'hidden':{'prompt':'PROMPT'}}

class PixeloidCaptureConditioning:
    @classmethod
    def INPUT_TYPES(cls):
        s=schemas(('image','IMAGE'));s['required']['fingerprint']=([extension_fingerprint()[0]],);return s
    RETURN_TYPES=('IMAGE',);FUNCTION='capture';CATEGORY='Pixeloid/private capture'
    @classmethod
    def IS_CHANGED(cls,**kwargs):return float('nan')
    def capture(self,image,job_id,fingerprint,prompt=None):
        started=time.perf_counter();cpu_images(image,(1,448,768,3))
        here=Path(__file__).resolve().parent
        actual,hashes=extension_fingerprint()
        if fingerprint!=actual:raise ValueError('Capture extension fingerprint differs; no sampling started.')
        root=Path(folder_paths.__file__).resolve().parent
        expected=json.loads((here/'runtime_sources.json').read_text())
        runtime={name:sha(root/name) for name in expected}
        if runtime!=expected:raise ValueError('Pinned renderer source changed; inspect before sampling, do not silently update pins.')
        p=directory(job_id)
        if shutil.disk_usage(Path(folder_paths.get_output_directory())).free<2**30:raise ValueError('Capture requires 1 GiB free output disk space.')
        # Never overwrite evidence, including partial evidence from a failed run.
        p.mkdir(parents=True,exist_ok=False)
        import torch,av
        m={'profile':PROFILE,'job_id':job_id,'state':'capturing','created_at_unix':time.time(),'start_monotonic':started,
           'runtime_source_sha256':runtime,'extension_sha256':hashes,'versions':{'python':sys.version,'torch':torch.__version__,'pyav':av.__version__,'ffmpeg':{k:list(v) for k,v in av.library_versions.items()}},
           'stages':{},'pc_relative_directory':str(p.relative_to(Path(folder_paths.get_output_directory()).resolve())),
           'notes':['Only 48 cropped encoder-input RGB PNGs are saved; no second float/49-frame set.',
                    'Timing includes synchronous host transfers, hashing and disk writes; node aliases may extend tensor lifetime.',
                    'No GPU peak counters reset; boundary samples are not measured render peaks.']}
        write_json(p/'manifest.json',m);write_json(p/'workflow.api.json',prompt)
        saved=tensor_file(p,'conditioning.safetensors',{'conditioning':image},{'layout':'BHWC','stage':'after node10 preprocess, before VAE encoding','workflow':'workflow.api.json'})
        record(p,'conditioning',started,[saved,file_record(p/'workflow.api.json')])
        return (image,)

class PixeloidCaptureLatent:
    @classmethod
    def INPUT_TYPES(cls):return schemas(('samples','LATENT'))
    RETURN_TYPES=('LATENT',);FUNCTION='capture';CATEGORY='Pixeloid/private capture'
    @classmethod
    def IS_CHANGED(cls,**kwargs):return float('nan')
    def capture(self,samples,job_id,prompt=None):
        import torch
        started=time.perf_counter();p=directory(job_id)
        if tuple(samples['samples'].shape)!=(1,128,7,14,24):raise ValueError('Unexpected post-guide video latent shape; retain partial evidence.')
        tensors={'latent_tensor':samples['samples'],'latent_format_version_0':torch.tensor([],device='cpu')}
        extras={}
        for key,value in samples.items():
            if key=='samples':continue
            if isinstance(value,torch.Tensor):tensors['aux_'+key]=value
            else:extras[key]=value
        # Ensure no unsaved opaque metadata is silently dropped.
        json.dumps(extras,allow_nan=False)
        saved=tensor_file(p,'video.latent',tensors,{'stage':'node36 output2, after guide removal, before VAE decode','layout':'BCTHW','aux_prefix':'aux_','extras':extras,'restore':'Read safetensors preserving dtype; latent_tensor -> samples; aux_* -> original keys. Native LoadLatent casts float32 and omits aux fields.','workflow':'workflow.api.json'})
        record(p,'latent',started,[saved]);return (samples,)

class PixeloidCaptureRGB:
    @classmethod
    def INPUT_TYPES(cls):return schemas(('images','IMAGE'))
    RETURN_TYPES=('IMAGE',);FUNCTION='capture';CATEGORY='Pixeloid/private capture'
    @classmethod
    def IS_CHANGED(cls,**kwargs):return float('nan')
    def capture(self,images,job_id,prompt=None):
        from PIL import Image
        started=time.perf_counter();cpu_images(images,(48,432,768,3));p=directory(job_id);frames=p/'rgb';frames.mkdir(exist_ok=False)
        files=[]
        for i,frame in enumerate(images):
            # Exact pinned VideoFromComponents 8-bit quantisation, on the same CPU
            # tensor/dtype. Return the original tensor; encoder repeats unchanged.
            rgb=(frame*255).clamp(0,255).byte().cpu().numpy()
            path=frames/f'{i:03}.png';temporary=frames/f'{i:03}.png.part'
            Image.fromarray(rgb,'RGB').save(temporary,format='PNG',compress_level=4)
            os.replace(temporary,path)
            files.append({**file_record(path),'name':'rgb/'+path.name,'frame_index':i,'rgb_sha256':hashlib.sha256(rgb.tobytes()).hexdigest()})
        record(p,'encoder_rgb',started,files);return (images,)

class PixeloidCaptureFinish:
    @classmethod
    def INPUT_TYPES(cls):return schemas(('video','VIDEO'))
    RETURN_TYPES=();FUNCTION='capture';OUTPUT_NODE=True;CATEGORY='Pixeloid/private capture'
    @classmethod
    def IS_CHANGED(cls,**kwargs):return float('nan')
    def capture(self,video,job_id,prompt=None):
        started=time.perf_counter();p=directory(job_id)
        manifest=json.loads((p/'manifest.json').read_text())
        stages=manifest.get('stages',{})
        if not all(key in stages for key in ('conditioning','latent','encoder_rgb')) or not all((p/name).is_file() for name in ('conditioning.safetensors','video.latent')):
            raise ValueError('Capture intermediates incomplete; retain evidence, do not rerender.')
        if [f.get('frame_index') for f in stages['encoder_rgb']['files']]!=list(range(48)) or not all((p/'rgb'/f'{i:03}.png').is_file() for i in range(48)):
            raise ValueError('Capture RGB sequence incomplete; retain evidence, do not rerender.')
        files=list(p.parent.glob('node_32_*.mp4'))
        if len(files)!=1:raise ValueError('Expected exactly one matching MP4; no automatic rerender.')
        path=files[0];import av
        with av.open(str(path)) as container:
            stream=container.streams.video[0]
            settings={'codec':stream.codec_context.name,'profile':stream.codec_context.profile,'pixel_format':stream.codec_context.pix_fmt,'dimensions':[stream.width,stream.height],'frame_count':stream.frames,'fps':str(stream.average_rate),'time_base':str(stream.time_base),'container_metadata':dict(container.metadata)}
        raw=path.read_bytes();start=raw.find(b'x264 - core')
        settings['x264_SEI']=raw[start:].split(b'\0',1)[0].decode('ascii',errors='replace') if start>=0 else None
        if settings['dimensions']!=[768,432] or settings['frame_count']!=48 or settings['fps']!='24' or settings['pixel_format']!='yuv420p' or not re.search(r'\bcrf=23\.0\b',settings['x264_SEI'] or ''):raise ValueError('Encoded output differs from fixed preview/recorded CRF23; evidence retained.')
        m=record(p,'after_encoding',started,[])
        m.update(state='complete',finished_at_unix=time.time(),capture_to_finish_seconds=time.perf_counter()-m['start_monotonic'],mp4={**file_record(path),'name':'../'+path.name,'settings':settings})
        write_json(p/'manifest.json',m)
        return {'ui':{'pixeloid_capture':[m]},'result':()}

NODE_CLASS_MAPPINGS={cls.__name__:cls for cls in (PixeloidCaptureConditioning,PixeloidCaptureLatent,PixeloidCaptureRGB,PixeloidCaptureFinish)}
NODE_DISPLAY_NAME_MAPPINGS={key:key for key in NODE_CLASS_MAPPINGS}
