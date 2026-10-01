"""Trace scanned plan ink into scalable SVG paths, without guessing architecture."""
from pathlib import Path
import numpy as np
from PIL import Image, ImageOps, ImageFilter


def thin_ink(mask):
    """Topology-preserving thinning of scan strokes to single-pixel centres."""
    a=np.pad(mask,1).astype(np.uint8)
    for _ in range(80):
        changed=False
        for phase in (0,1):
            p=[a[:-2,1:-1],a[:-2,2:],a[1:-1,2:],a[2:,2:],a[2:,1:-1],a[2:,:-2],a[1:-1,:-2],a[:-2,:-2]]
            neighbors=sum(p)
            transitions=sum((p[i]==0)&(p[(i+1)%8]==1) for i in range(8))
            remove=(a[1:-1,1:-1]==1)&(neighbors>=2)&(neighbors<=6)&(transitions==1)
            if phase==0:remove&=(p[0]*p[2]*p[4]==0)&(p[2]*p[4]*p[6]==0)
            else:remove&=(p[0]*p[2]*p[6]==0)&(p[0]*p[4]*p[6]==0)
            if remove.any():a[1:-1,1:-1][remove]=0;changed=True
        if not changed:break
    return a[1:-1,1:-1]


def simplify(points,tolerance=.55):
    if len(points)<=2:return points
    start=np.array(points[0],float);end=np.array(points[-1],float);delta=end-start
    data=np.array(points,float);length=float(np.linalg.norm(delta))
    if length<1e-6:dist=np.linalg.norm(data-start,axis=1)
    else:dist=np.abs(delta[0]*(data[:,1]-start[1])-delta[1]*(data[:,0]-start[0]))/length
    index=int(np.argmax(dist))
    if dist[index]<=tolerance:return [points[0],points[-1]]
    return simplify(points[:index+1],tolerance)[:-1]+simplify(points[index:],tolerance)


def centerline_paths(gray,threshold):
    skel=thin_ink(gray<threshold)
    pixels=set(zip(*np.where(skel)))
    edges={}
    for y,x in pixels:
        linked=[]
        for dy,dx in [(-1,0),(1,0),(0,-1),(0,1),(-1,-1),(-1,1),(1,-1),(1,1)]:
            q=(y+dy,x+dx)
            if q not in pixels:continue
            # Avoid triangular branches around a right-angle corner.
            if dy and dx and ((y+dy,x) in pixels or (y,x+dx) in pixels):continue
            linked.append(q)
        edges[(y,x)]=linked
    visited=set();paths=[]
    def walk(start,following):
        line=[start];last=start;current=following
        while True:
            edge=tuple(sorted((last,current)))
            if edge in visited:break
            visited.add(edge);line.append(current)
            if current==start or len(edges[current])!=2:break
            choices=[p for p in edges[current] if p!=last]
            if not choices:break
            last,current=current,choices[0]
        if len(line)<3:return
        points=[(float(x)+.5,float(y)+.5) for y,x in line]
        points=simplify(points)
        paths.append('M'+' L'.join(f'{x:.2f},{y:.2f}' for x,y in points))
    for p in edges:
        if len(edges[p])!=2:
            for q in edges[p]:walk(p,q)
    for p in edges:
        for q in edges[p]:
            if tuple(sorted((p,q))) not in visited:walk(p,q)
    return ' '.join(paths)


def contour_paths(gray, threshold):
    # Marching squares interpolates the ink boundary between pixel centres.
    # White padding makes every contour closed, including page-edge strokes.
    a=np.pad(gray,1,constant_values=255).astype(float)
    inside=a<threshold
    cases=inside[:-1,:-1].astype(np.uint8)+2*inside[:-1,1:]+4*inside[1:,1:]+8*inside[1:,:-1]
    pairs={1:[(0,3)],2:[(0,1)],3:[(3,1)],4:[(1,2)],5:[(0,3),(1,2)],6:[(0,2)],
           7:[(3,2)],8:[(2,3)],9:[(0,2)],10:[(0,1),(2,3)],11:[(1,2)],12:[(1,3)],
           13:[(0,1)],14:[(0,3)]}
    neighbors={};points={}
    for y,x in zip(*np.where((cases>0)&(cases<15))):
        edges=[(0,int(y),int(x)),(1,int(y),int(x+1)),(0,int(y+1),int(x)),(1,int(y),int(x))]
        links=pairs[int(cases[y,x])]
        if cases[y,x] in (5,10) and a[y:y+2,x:x+2].mean()<threshold:
            links=[(0,1),(2,3)] if cases[y,x]==5 else [(0,3),(1,2)]
        for first,second in links:
            keys=[edges[first],edges[second]]
            for key in keys:
                if key not in points:
                    direction,yy,xx=key;v=a[yy,xx];other=a[yy+direction,xx+1-direction]
                    t=(threshold-v)/(other-v) if other!=v else .5
                    points[key]=(xx-.5+(1-direction)*t,yy-.5+direction*t)
            neighbors.setdefault(keys[0],[]).append(keys[1]);neighbors.setdefault(keys[1],[]).append(keys[0])
    paths=[];seen=set()
    for start in neighbors:
        if start in seen:continue
        loop=[];previous=None;current=start
        while current not in seen:
            seen.add(current);loop.append(points[current])
            onward=[p for p in neighbors[current] if p!=previous]
            if not onward:break
            previous,current=current,onward[0]
        if len(loop)<3:continue
        # Preserve tiny openings; only remove virtually collinear vertices.
        clean=[]
        for point in loop:
            if len(clean)>1:
                p,q=clean[-2:]
                cross=abs((q[0]-p[0])*(point[1]-q[1])-(q[1]-p[1])*(point[0]-q[0]))
                if cross<.002:clean.pop()
            clean.append(point)
        paths.append('M'+' L'.join(f'{x:.2f},{y:.2f}' for x,y in clean)+' Z')
    return ' '.join(paths)


def trace_plan(source_path,output_path):
    with Image.open(source_path) as source:
        width,height=source.size
        # A slight subpixel blur regularizes noisy scan edges before tracing;
        # all walls, furniture and lettering come from the original pixels.
        im=ImageOps.grayscale(source).filter(ImageFilter.GaussianBlur(.35))
        gray=np.asarray(im)
    layers=[]
    for threshold,color,weight in [(225,'#7b8175',.52),(125,'#313b2b',.9)]:
        d=centerline_paths(gray,threshold)
        layers.append(f'<path fill="none" stroke="{color}" stroke-width="{weight}" stroke-linecap="round" stroke-linejoin="round" d="{d}"/>')
    svg=f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}"><title>Vector trace of uploaded floor plan</title><desc>Outlines traced from scan pixels. Original geometry has not been reconstructed or dimensionally verified.</desc><rect width="100%" height="100%" fill="white"/>'+''.join(layers)+'</svg>'
    Path(output_path).write_text(svg,encoding='utf8')
    return width,height
