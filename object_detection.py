"""Local open-vocabulary proposals in bounded crops, mapped to source coordinates."""
import base64
import hashlib
import io
import json
import math
import time
from pathlib import Path
import requests
from PIL import Image, ImageOps
from object_knowledge import RULES, annotate, catalog, normalize_kind, quality_flags


def map_box(box,region):
    x,y,w,h=region
    return [x+box[0]*w,y+box[1]*h,box[2]*w,box[3]*h]


def merge_features(rows):
    """Suppress same-type overlap from adjacent tiles, never merge separate chairs."""
    out=[]
    for row in rows:
        b=row['bbox'];duplicate=False
        for other in out:
            from detection_review import category
            if row['kind']!=other['kind'] or category(row)!=category(other):continue
            if row.get('source_agreement')=='disagrees' or other.get('source_agreement')=='disagrees':continue
            a=other['bbox'];inter=max(0,min(a[0]+a[2],b[0]+b[2])-max(a[0],b[0]))*max(0,min(a[1]+a[3],b[1]+b[3])-max(a[1],b[1]))
            union=a[2]*a[3]+b[2]*b[3]-inter
            if union and inter/union>.5:duplicate=True;break
        if not duplicate:out.append(annotate(row))
    return out


def encode_crop(image,region):
    x,y,w,h=region
    crop=image.crop((round(x*image.width),round(y*image.height),round((x+w)*image.width),round((y+h)*image.height)))
    crop.thumbnail((1400,1400),Image.Resampling.LANCZOS)
    buf=io.BytesIO();crop.save(buf,format='PNG')
    return base64.b64encode(buf.getvalue()).decode()


def parse_objects(raw,mode):
    """Translate simple visual grounding output to the review schema."""
    from vision_study import clean_result
    if not isinstance(raw,dict):raise ValueError('Expected an object report.')
    rows=raw.get('rooms' if mode=='sections' else 'objects',[])
    if not isinstance(rows,list):raise ValueError('Expected a list of detections.')
    features=[]
    for row in rows:
        if not isinstance(row,dict):continue
        box=row.get('bbox_2d')
        if not isinstance(box,list) or len(box)!=4 or any(type(v) not in (int,float) or not math.isfinite(v) for v in box):continue
        x,y,right,bottom=box
        if not (0<=x<right<=1000 and 0<=y<bottom<=1000):continue
        name=str(row.get('name','Unknown'))[:120]
        features.append({'kind':'space' if mode=='sections' else normalize_kind(row.get('kind','unknown'),name),
                         'label':name,'object_type':name if mode!='sections' else '',
                         'bbox':[x/1000,y/1000,(right-x)/1000,(bottom-y)/1000],
                         'floor':'','seat_count':row.get('seat_count'),
                         'confidence':row.get('confidence','low'),
                         'evidence':row.get('evidence','Visual shape estimate; verify against original.')})
    return clean_result({'features':features,'uncertainties':raw.get('uncertainties',[])})


def read(path,enhanced,settings,sections,progress,cache_dir=None,cancelled=None):
    from detection_pipeline import read as run_pipeline
    return run_pipeline(path,enhanced,settings,sections,progress,cache_dir,cancelled)
