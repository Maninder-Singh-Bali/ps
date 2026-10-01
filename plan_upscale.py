"""Cached reading copy, never replacement geometry or a change of drawing scale."""
import hashlib
import json
import subprocess
import time
from pathlib import Path
from PIL import Image, ImageOps

MODEL='realesr-general-x4v3'
MODEL_SHA='8dc7edb9ac80ccdc30c3a5dca6616509367f05fbc184ad95b731f05bece96292'


def enlarge(path,folder,info,progress):
    """Deterministic reading aid when AI weights are absent; no invented detail."""
    folder.mkdir(parents=True,exist_ok=True)
    size=info['source_size'];scale=min(2,1600/max(size))
    if scale<=1:return path,info
    target=folder/(info['source_sha256'][:24]+'-lanczos-v1.png')
    output=tuple(max(1,round(v*scale)) for v in size);cached=False
    if target.exists():
        try:
            with Image.open(target) as im:cached=im.size==output;im.verify()
        except (OSError,ValueError):cached=False
    if not cached:
        progress('Preparing enlarged reading copy',None)
        with Image.open(path) as im:ImageOps.exif_transpose(im).convert('RGB').resize(output,Image.Resampling.LANCZOS).save(target)
    info.update(method='Lanczos interpolation',scale=scale,output_size=list(output),cached=cached,
                source_to_reading=[output[0]/size[0],0,0,output[1]/size[1],0,0],
                warning='AI upscaler unavailable. Interpolation enlarges existing pixels; it does not recover missing detail.')
    return target,info


def enhance(path,root,folder,progress=lambda *a:None):
    path=Path(path);root=Path(root);folder=Path(folder)
    sha=hashlib.sha256(path.read_bytes()).hexdigest()
    with Image.open(path) as im:size=ImageOps.exif_transpose(im).size
    info={'source_sha256':sha,'source_size':list(size),'scale':1,'method':'native',
          'geometry_reconstructed':False,'warning':'Enhancement does not recover verified dimensions or missing detail.'}
    if max(size)>1600 or size[0]*size[1]>2_000_000:return path,info
    weights=root/'models'/'upscale'/(MODEL+'.pth')
    if not weights.exists():return enlarge(path,folder,info,progress)
    if hashlib.sha256(weights.read_bytes()).hexdigest()!=MODEL_SHA:raise ValueError('Upscaler weights failed the integrity check.')
    config=json.loads((root/'studio.local.json').read_text(encoding='utf-8-sig'))
    python=Path(config['comfy_python'])
    folder.mkdir(parents=True,exist_ok=True)
    target=folder/(sha[:24]+'-'+MODEL_SHA[:12]+'-v1.png')
    started=time.monotonic();cached=False
    if target.exists():
        try:
            with Image.open(target) as out:out.verify()
            with Image.open(target) as out:cached=out.size==(size[0]*4,size[1]*4)
        except (OSError,ValueError):pass
    if not cached:
        progress('Enhancing low-resolution plan locally',None)
        proc=subprocess.run([str(python),str(root/'upscale_worker.py'),str(path),str(target),str(weights)],
                            capture_output=True,text=True,timeout=240,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        if proc.returncode:raise ValueError('Local upscaler failed: '+proc.stderr[-500:])
    with Image.open(target) as out:
        if out.size!=(size[0]*4,size[1]*4):raise ValueError('Upscaler returned invalid dimensions.')
    info.update(method=MODEL,model_sha256=MODEL_SHA,scale=4,output_size=[size[0]*4,size[1]*4],
                cached=cached,elapsed_seconds=round(time.monotonic()-started,2))
    return target,info
