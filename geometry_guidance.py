"""Camera-matched QA buffers. These are not automatically wired to a diffusion model."""
import hashlib
import json
from pathlib import Path
import numpy as np
from PIL import Image


def save(scene, face_ids, depth, folder):
    folder=Path(folder);camera=scene['camera']
    forward=np.asarray(camera['target'],float)-camera['position'];forward/=np.linalg.norm(forward)
    right=np.cross([0,0,1],forward);right/=np.linalg.norm(right)
    basis=np.array([right,np.cross(forward,right),forward])
    normals=np.zeros((len(scene['surfaces'])+1,3),np.float32)
    labels=['background'];surface_labels=[0]
    for i,face in enumerate(scene['surfaces'],1):
        points=np.asarray(face['points'],float);normal=np.cross(points[1]-points[0],points[2]-points[0])
        normal/=max(np.linalg.norm(normal),1e-10)
        if np.dot(normal,points.mean(axis=0)-camera['position'])>0:normal=-normal
        normals[i]=basis@normal
        key=face.get('object_key') or face.get('source_id') or face['kind']
        if key not in labels:labels.append(key)
        surface_labels.append(labels.index(key))
    ids=np.asarray(surface_labels,dtype=np.int32)[face_ids]
    normal_map=normals[face_ids];valid=np.isfinite(depth)
    near=float(depth[valid].min()) if valid.any() else 0
    far=float(depth[valid].max()) if valid.any() else 1
    normalized=np.zeros(depth.shape,np.uint16)
    normalized[valid]=1+np.round((1-(depth[valid]-near)/max(far-near,1e-8))*65534).astype(np.uint16)
    Image.fromarray(normalized).save(folder/'guide-depth.png')
    np.savez_compressed(folder/'guide-depth-metres.npz',depth=depth)
    normal_pixels=np.round((normal_map+1)*127.5).clip(0,255).astype(np.uint8);normal_pixels[~valid]=0
    Image.fromarray(normal_pixels).save(folder/'guide-normals.png')
    palette=np.array([[0,0,0]]+[list(hashlib.sha256(key.encode()).digest()[:3]) for key in labels[1:]],np.uint8)
    Image.fromarray(palette[ids]).save(folder/'guide-segmentation.png')
    np.savez_compressed(folder/'guide-segmentation-ids.npz',ids=ids)
    edges=np.zeros(depth.shape,bool)
    for axis in (0,1):
        previous=np.roll(ids,1,axis);edges|=ids!=previous
        safe_depth=np.where(valid,depth,0);delta=np.abs(safe_depth-np.roll(safe_depth,1,axis))
        edges|=(delta>.05)&valid&np.roll(valid,1,axis)
        edges|=(np.sum(normal_map*np.roll(normal_map,1,axis),axis=2)<.94)&valid&np.roll(valid,1,axis)
    edges[0,:]=False;edges[:,0]=False
    Image.fromarray(edges.astype(np.uint8)*255).save(folder/'guide-edges.png')
    meta={'scene_revision':scene['scene_document']['scene_revision'],'geometry_hash':scene['geometry_hash'],
          'camera':camera,'size':[int(depth.shape[1]),int(depth.shape[0])],
          'depth':{'units':'metres along camera forward axis','near':near,'far':far,'png_encoding':'0 background; 1 far to 65535 near; float NPZ is authoritative'},
          'normals':'Camera right/up/forward, visible faces oriented toward camera; RGB encodes [-1,1]',
          'segmentation':{str(i):key for i,key in enumerate(labels)},
          'conditioning':'QA exports only. Current FLUX workflow uses reference conditioning, not depth/normal/segmentation control.',
          'final_image_crop':'Existing output workflow crops 4 rows from top and bottom; apply the same crop before comparison.'}
    (folder/'geometry-guidance.json').write_text(json.dumps(meta,indent=2),encoding='utf-8')
    return meta
