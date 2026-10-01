"""Legibility previews for small floor plans; original geometry stays untouched."""
from pathlib import Path
import hashlib
from PIL import Image, ImageOps, ImageEnhance, ImageFilter
from store import uid, now
from plan_vector import trace_plan


def ensure_vector(store,asset):
    existing=store.db['assets'].get(asset.get('vector_preview_id'))
    if existing and existing.get('vector_trace_version')==2 and Path(existing['path']).is_file():return existing
    if max(asset.get('width',0),asset.get('height',0))>2400:return None
    path=Path(asset['path']).with_name(Path(asset['path']).stem+'_vector_plan_v2.svg')
    width,height=trace_plan(asset['path'],path)
    a={'id':uid(),'project_id':asset['project_id'],'room_id':None,'kind':'plan_vector','name':path.name,'path':str(path.resolve()),
       'created':now(),'width':width,'height':height,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
       'source_asset_id':asset['id'],'format':'svg','vector_trace_version':2,'enhancement':'Vector stroke centre lines traced from original scan; not a surveyed CAD plan'}
    store.db['assets'][a['id']]=a;asset['vector_preview_id']=a['id'];store.save();return a


def ensure_preview(store,asset):
    if asset.get('kind')!='plan':raise ValueError('Choose a floor-plan page.')
    ensure_vector(store,asset)
    existing=store.db['assets'].get(asset.get('clear_preview_id'))
    if existing and Path(existing['path']).is_file():return existing
    with Image.open(asset['path']) as source:
        if max(source.size)>=2000:return asset
        factor=min(4,max(2,round(2200/max(source.size))))
        image=ImageOps.autocontrast(source.convert('RGB'),cutoff=.1)
        image=ImageEnhance.Contrast(image).enhance(1.08)
        image=image.resize((source.width*factor,source.height*factor),Image.Resampling.LANCZOS)
        image=image.filter(ImageFilter.UnsharpMask(radius=1.1,percent=110,threshold=3))
    # Beside its original asset, inside this project's own supporting files.
    path=Path(asset['path']).with_name(Path(asset['path']).stem+'_clear_plan.png');image.save(path)
    a={'id':uid(),'project_id':asset['project_id'],'room_id':None,'kind':'plan_preview','name':path.name,'path':str(path.resolve()),
       'created':now(),'width':image.width,'height':image.height,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
       'source_asset_id':asset['id'],'output_upscaled':True,'enhancement':'Enlarged and contrast enhanced; no reconstructed geometry'}
    store.db['assets'][a['id']]=a;asset['clear_preview_id']=a['id'];store.save();return a
