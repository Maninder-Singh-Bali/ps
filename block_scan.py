"""Fast CPU-only rough symbol bounds from original plan pixels, never exact geometry."""
from collections import deque
import uuid
import numpy as np
from PIL import Image,ImageOps

def components(mask):
    h,w=mask.shape;seen=~mask.copy()
    for y,x in zip(*np.where(mask)):
        if seen[y,x]:continue
        seen[y,x]=True;q=deque([(int(x),int(y))]);points=[]
        while q:
            xx,yy=q.popleft();points.append((xx,yy))
            for dx,dy in ((1,0),(-1,0),(0,1),(0,-1)):
                nx,ny=xx+dx,yy+dy
                if 0<=nx<w and 0<=ny<h and not seen[ny,nx]:seen[ny,nx]=True;q.append((nx,ny))
        xs,ys=zip(*points);yield [min(xs),min(ys),max(xs)-min(xs)+1,max(ys)-min(ys)+1],len(points)

def scan(plan,room):
    b=room['bbox']
    with Image.open(plan['path']) as image:
        im=ImageOps.exif_transpose(image).convert('L');W,H=im.size
        left,top=int(b[0]*W),int(b[1]*H);right,bottom=int((b[0]+b[2])*W),int((b[1]+b[3])*H)
        crop=im.crop((left,top,right,bottom));native=crop.size;crop.thumbnail((500,500));gray=np.asarray(crop)
    h,w=gray.shape
    if min(h,w)<8:return []
    background=float(np.percentile(gray,70));candidates=[]
    # Multiple native tonal levels recover faint symbols without sharpening or inventing detail.
    for threshold in sorted(set(int(max(40,min(240,background-d))) for d in (12,20,30,45,65))):
        for box,n in components(gray<threshold):
            x,y,bw,bh=box;area=bw*bh
            if min(bw,bh)<max(3,min(w,h)*.045) or max(bw,bh)>max(w,h)*.72:continue
            if area<w*h*.006 or area>w*h*.32 or max(bw/bh,bh/bw)>6:continue
            if x<=1 or y<=1 or x+bw>=w-1 or y+bh>=h-1:continue
            density=n/area
            if not .1<density<.82:continue
            # Edge evidence favours closed furniture outlines over text fragments.
            patch=(gray[y:y+bh,x:x+bw]<threshold)
            edge=float(np.mean([patch[0].mean(),patch[-1].mean(),patch[:,0].mean(),patch[:,-1].mean()]))
            if edge<.32:continue
            candidates.append((edge+3*(area/(w*h))**.5,box))
    chosen=[]
    for score,box in sorted(candidates,reverse=True):
        x,y,bw,bh=box
        def duplicate(other):
            xx,yy,ww,hh=other
            intersection=max(0,min(x+bw,xx+ww)-max(x,xx))*max(0,min(y+bh,yy+hh)-max(y,yy))
            return intersection/max(1,min(bw*bh,ww*hh))>.55
        if any(duplicate(other) for other in chosen):continue
        chosen.append(box)
        if len(chosen)>=30:break
    out=[]
    for i,(x,y,bw,bh) in enumerate(sorted(chosen,key=lambda r:(r[1],r[0]))):
        out.append({'id':uuid.uuid4().hex[:16],'kind':'unknown','label':f'Detected block {i+1}','seat_count':None,
                    'x':(left+(x+bw/2)*native[0]/w)/W,'y':(top+(y+bh/2)*native[1]/h)/H,
                    'width':bw*native[0]/w/W,'depth':bh*native[1]/h/H,'angle':0,
                    'source':'scan-outline','confidence':'low','prompt':'','asset_id':None})
    return out
