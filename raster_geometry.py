"""Conservative CPU raster geometry proposals from original pixels.

No VLM boxes are accepted as geometry. SciPy supplies distance transforms and
component labelling; the masks, skeleton graph and curve fitting are inspectable.
This is a stroke-width heuristic, not a trained semantic segmentation model.
"""
import hashlib
import json
import math
import time
from pathlib import Path
import numpy as np
from PIL import Image,ImageOps,ImageDraw
from scipy import ndimage as ndi
from scipy.interpolate import splprep,splev
from scipy.spatial import cKDTree

VERSION=2


def simplify(points,tolerance=.8):
    p=np.asarray(points,float)
    if len(p)<=2:return p.tolist()
    delta=p[-1]-p[0];length=np.linalg.norm(delta)
    distances=np.abs(delta[0]*(p[:,1]-p[0,1])-delta[1]*(p[:,0]-p[0,0]))/length if length else np.linalg.norm(p-p[0],axis=1)
    i=int(distances.argmax())
    if distances[i]<=tolerance:return p[[0,-1]].tolist()
    return simplify(p[:i+1],tolerance)[:-1]+simplify(p[i:],tolerance)


def skeletonize(mask):
    a=np.pad(mask.astype(np.uint8),1)
    for _ in range(100):
        changed=False
        for stage in (0,1):
            c=a[1:-1,1:-1]
            p=[a[:-2,1:-1],a[:-2,2:],a[1:-1,2:],a[2:,2:],a[2:,1:-1],a[2:,:-2],a[1:-1,:-2],a[:-2,:-2]]
            count=sum(p);trans=sum((v==0)&(p[(i+1)%8]==1) for i,v in enumerate(p))
            if stage==0:limit=(p[0]*p[2]*p[4]==0)&(p[2]*p[4]*p[6]==0)
            else:limit=(p[0]*p[2]*p[6]==0)&(p[0]*p[4]*p[6]==0)
            remove=(c==1)&(count>=2)&(count<=6)&(trans==1)&limit
            if remove.any():c[remove]=0;changed=True
        if not changed:break
    return a[1:-1,1:-1].astype(bool)


def graph_paths(mask):
    pixels={tuple(v) for v in np.argwhere(mask)}
    def neighbors(p):
        y,x=p;out=[]
        for dy,dx in ((-1,0),(0,-1),(0,1),(1,0),(-1,-1),(-1,1),(1,-1),(1,1)):
            q=(y+dy,x+dx)
            # Diagonal is redundant if either orthogonal bridge exists.
            if q in pixels and not (dy and dx and ((y+dy,x) in pixels or (y,x+dx) in pixels)):out.append(q)
        return out
    links={p:neighbors(p) for p in pixels};visited=set();paths=[]
    starts=sorted(p for p,n in links.items() if len(n)!=2)+sorted(pixels)
    for start in starts:
        for neighbor in links[start]:
            edge=frozenset((start,neighbor))
            if edge in visited:continue
            visited.add(edge);path=[start,neighbor];previous,current=start,neighbor
            while len(links[current])==2:
                nxt=next(p for p in links[current] if p!=previous);edge=frozenset((current,nxt))
                if edge in visited:break
                visited.add(edge);path.append(nxt);previous,current=current,nxt
            if len(path)>=8:paths.append([[float(x),float(y)] for y,x in path])
    junctions=[[float(x),float(y)] for (y,x),v in links.items() if len(v)>=3]
    return paths,junctions


def contour(mask):
    """Trace directed pixel-cell edges; preserve holes as separate loops."""
    yy,xx=np.where(mask);edges={}
    for y,x in zip(yy.tolist(),xx.tolist()):
        if y==0 or not mask[y-1,x]:edges.setdefault((x,y),[]).append((x+1,y))
        if x==mask.shape[1]-1 or not mask[y,x+1]:edges.setdefault((x+1,y),[]).append((x+1,y+1))
        if y==mask.shape[0]-1 or not mask[y+1,x]:edges.setdefault((x+1,y+1),[]).append((x,y+1))
        if x==0 or not mask[y,x-1]:edges.setdefault((x,y+1),[]).append((x,y))
    loops=[]
    while edges:
        start=next(iter(edges));p=start;path=[p]
        while p in edges:
            q=edges[p].pop()
            if not edges[p]:del edges[p]
            path.append(q);p=q
            if p==start:break
        if len(path)>20 and path[-1]==start:loops.append(simplify(path,1))
    return sorted(loops,key=lambda p:abs(sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(p,p[1:]))),reverse=True)


def fit_path(points):
    p=np.asarray(points,float);simple=simplify(p,.8)
    if len(simple)==2:return {'type':'line','points':simple,'max_error_px':.8}
    # Least-squares circle accepted only with a small radial residual and a
    # monotone sweep. Otherwise retain the measured polyline rather than force an arc.
    centre=np.linalg.lstsq(np.c_[2*p[:,0],2*p[:,1],np.ones(len(p))],np.sum(p*p,axis=1),rcond=None)[0]
    c=centre[:2];radius=math.sqrt(max(0,centre[2]+np.dot(c,c)));radii=np.linalg.norm(p-c,axis=1)
    angle=np.unwrap(np.arctan2(p[:,1]-c[1],p[:,0]-c[0]));sweep=angle[-1]-angle[0]
    steps=np.diff(angle);monotone=max(np.mean(steps>=-.005),np.mean(steps<=.005))>.95
    error=float(np.max(np.abs(radii-radius)))
    if radius>3 and radius<1e5 and .12<abs(sweep)<6.3 and monotone and error<=1.2:
        return {'type':'arc','points':simple,'center':c.tolist(),'radius':radius,'start_angle':float(angle[0]),'sweep':float(sweep),'max_error_px':error}
    if len(p)>20:
        try:
            tck,u=splprep(p.T,s=len(p)*.12,k=3)
            fitted=np.array(splev(u,tck)).T
            if np.max(np.linalg.norm(fitted-p,axis=1))<=1.25:
                samples=np.array(splev(np.linspace(0,1,min(3000,len(p)*2)),tck)).T
                error=float(cKDTree(p).query(samples)[0].max())
                if error<=1.6:
                    return {'type':'spline','points':simplify(samples,.5),'knots':list(tck[0]),'controls':np.array(tck[1]).T.tolist(),'degree':3,'max_error_px':error}
        except (ValueError,TypeError):pass
    return {'type':'polyline','points':simple,'max_error_px':.8,'note':'Curve retained as a tolerance-bounded pixel trace; no reliable single-circle fit.'}


def run(source,folder,enhanced=None,panels=None):
    started=time.monotonic();folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    source=Path(source);source_hash=hashlib.sha256(source.read_bytes()).hexdigest()
    with Image.open(source) as im:image=ImageOps.exif_transpose(im).convert('RGB')
    original_size=image.size;ratio=min(1,1600/max(image.size))
    if ratio<1:image=image.resize(tuple(round(v*ratio) for v in image.size),Image.Resampling.LANCZOS)
    gray=np.asarray(image.convert('L')).copy();height,width=gray.shape
    if panels is not None:
        from source_panels import mask_for
        gray[~mask_for(image.size,panels)]=255
    ink=gray<180;distance=ndi.distance_transform_edt(ink)
    # Core width excludes most single-pixel furniture, text and dimension strokes.
    core=distance>=2.25;mask=ndi.binary_dilation(core,iterations=3)&ink
    components,count=ndi.label(mask);sizes=np.bincount(components.ravel());keep=np.zeros(count+1,bool)
    for label,sl in enumerate(ndi.find_objects(components),1):
        if sl and sizes[label]>=100 and max(s.stop-s.start for s in sl)>=30:keep[label]=True
    mask=keep[components];skeleton=skeletonize(mask);paths,junctions=graph_paths(skeleton)
    enhanced_ink=None
    if enhanced and Path(enhanced).exists():
        with Image.open(enhanced) as im:enhanced_ink=np.asarray(ImageOps.exif_transpose(im).convert('L').resize((width,height),Image.Resampling.LANCZOS))<180
    walls=[]
    for path in paths:
        length=sum(math.dist(a,b) for a,b in zip(path,path[1:]))
        if length<18:continue
        p=np.asarray(path,dtype=int);r=distance[p[:,1],p[:,0]]
        if np.percentile(r,50)<2:continue
        geometry=fit_path(path);key='raster'+hashlib.sha256(json.dumps([source_hash,geometry['points']]).encode()).hexdigest()[:16]
        agreement=float(ndi.binary_dilation(enhanced_ink,iterations=1)[p[:,1],p[:,0]].mean()) if enhanced_ink is not None else None
        walls.append({'id':key,'category':'wall_candidate','geometry':geometry,'width_px':float(np.median(r)*2),
                      'width_range_px':[float(np.percentile(r,10)*2),float(np.percentile(r,90)*2)],
                      'endpoint_uncertainty_px':2,'length_px':length,'source_support':1.0,'enhanced_agreement':agreement,
                      'status':'supported_stroke' if agreement is None or agreement>=.85 else 'source_disagreement',
                      'semantic_state':'unverified wall; thick stroke evidence','review_state':'pending'})
    # Exterior region is a separate hypothesis. Its contour is never automatically
    # a wall: glazing, floor finishes and furniture can contribute to a silhouette.
    occupied=gray<247
    joined=ndi.binary_closing(occupied,iterations=1)
    labels,n=ndi.label(joined);counts=np.bincount(labels.ravel());counts[0]=0
    footprint=ndi.binary_fill_holes(labels==int(counts.argmax())) if n else np.zeros_like(mask)
    if footprint.sum()<gray.size*.02:footprint[:]=False
    outer=contour(ndi.binary_opening(footprint,iterations=1))
    uncertain_spans=[]
    if outer:
        # Divide unsupported exterior stretches into short selectable proposals.
        distance_to_wall=ndi.distance_transform_edt(~mask);pending=[]
        def finish_span():
            if len(pending)>1:
                geometry=fit_path(pending)
                uncertain_spans.append({'id':'boundary'+hashlib.sha256(json.dumps(geometry['points']).encode()).hexdigest()[:16],
                    'geometry':geometry,'status':'uncertain exterior boundary; glazing versus wall unresolved','review_state':'pending'})
            pending.clear()
        for a,b in zip(outer[0],outer[0][1:]):
            points=np.linspace(a,b,max(2,round(math.dist(a,b))))
            for point in points:
                x,y=np.round(point).astype(int);x=min(width-1,max(0,x));y=min(height-1,max(0,y))
                if distance_to_wall[y,x]>10:
                    if not pending or np.linalg.norm(point-pending[-1])>.5:pending.append(point.tolist())
                    if len(pending)>65:finish_span()
                else:finish_span()
        finish_span()
    regions=[]
    free=footprint&~ndi.binary_dilation(mask,iterations=1)
    labels,n=ndi.label(free);counts=np.bincount(labels.ravel())
    for label in range(1,n+1):
        if counts[label]<max(500,gray.size*.003):continue
        outlines=contour(labels==label)
        if outlines:regions.append({'id':'region'+str(label),'polygon':outlines[0],'holes':outlines[1:],
                                    'kind':'connected_free_space','area_px':int(counts[label]),
                                    'status':'candidate; openings are not closed to manufacture rooms'})
    endpoints=[]
    for wall in walls:
        points=wall['geometry']['points']
        for end,near in ((points[0],points[1]),(points[-1],points[-2])):
            endpoints.append((wall,end,np.asarray(end)-near))
        # An opening can end at an L junction, not only at a graph endpoint.
        for a,b in zip(points,points[1:]):
            if math.dist(a,b)>wall['width_px']*2:
                endpoints.extend([(wall,a,np.asarray(a)-b),(wall,b,np.asarray(b)-a)])
    openings=[];repairs=[]
    for i,(wall,a,direction) in enumerate(endpoints):
        for other,b,other_direction in endpoints[i+1:]:
            if wall['id']==other['id']:continue
            delta=np.asarray(b)-a;length=float(np.linalg.norm(delta));thick=max(wall['width_px'],other['width_px'])
            if not 1<length<max(16,thick*7):continue
            u=delta/length
            if np.dot(direction,u)/max(np.linalg.norm(direction),1e-8)<.85 or np.dot(other_direction,-u)/max(np.linalg.norm(other_direction),1e-8)<.85:continue
            ps=np.round(np.linspace(a,b,max(3,round(length)))).astype(int);support=float((gray[ps[:,1],ps[:,0]]<210).mean())
            entry={'id':'opening'+str(len(openings)+len(repairs)),'points':[a,b],'wall_ids':[wall['id'],other['id']],'width_px':length,'ink_support':support}
            if length<=2.5 and support>.65:repairs.append({**entry,'status':'proposed pixel-supported gap repair; not applied'})
            elif length>thick*1.2 and support<.3:
                if not any(min(math.dist(a,v['points'][0])+math.dist(b,v['points'][1]),math.dist(a,v['points'][1])+math.dist(b,v['points'][0]))<10 for v in openings):
                    openings.append({**entry,'status':'candidate opening; doorway versus open transition unresolved'})
    warnings=['Thick-stroke segmentation is not semantic wall recognition. Thick furniture or counters may be false positives.',
              'Thin and double-line walls/glazing are not automatically extruded. Exterior contour is an unverified boundary hypothesis.',
              'Room regions remain connected through real gaps. Door swing arcs and labels are not enclosure edges.',
              'Furniture/stair classification and door/fixture contradictions require separate shape evidence or trained segmentation.']
    result={'version':VERSION,'method':'Original-pixel threshold + stroke-width distance transform + connected components + Zhang–Suen skeleton + graph tracing + bounded-error line/arc fitting',
            'source_sha256':source_hash,'source_size':list(original_size),'analysis_size':[width,height],
            'analysis_to_source':[original_size[0]/width,0,0,original_size[1]/height,0,0],'walls':walls,'junctions':junctions,
            'candidate_exterior':outer[0] if outer else None,'uncertain_spans':uncertain_spans,'regions':regions,'openings':openings,'gap_repairs':repairs,
            'geometry_validated':False,'verified_model':False,'warnings':warnings,'elapsed_seconds':round(time.monotonic()-started,3)}
    from raster_identity import identified
    if panels is not None:
        from source_panels import digest
        result['source_scope']=digest(panels)
    result=identified(result)
    Image.fromarray(mask.astype(np.uint8)*255).save(folder/'wall-mask.png')
    Image.fromarray((ink&~mask).astype(np.uint8)*255).save(folder/'excluded-thin-strokes.png')
    overlay=image.copy();draw=ImageDraw.Draw(overlay)
    if outer:draw.line([tuple(p) for p in outer[0]],fill='#d18c28',width=2)
    for wall in walls:
        points=wall['geometry']['points'];draw.line([tuple(p) for p in points],fill='#009f83',width=3)
        for x,y in (points[0],points[-1]):draw.ellipse((x-2,y-2,x+2,y+2),fill='#d85948')
    for entry in openings:draw.line([tuple(p) for p in entry['points']],fill='#438dec',width=3)
    overlay.save(folder/'boundary-overlay.png')
    (folder/'raster-geometry.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    return result


if __name__=='__main__':
    import argparse,sys
    # Isolated Windows runtimes do not put the script directory on sys.path.
    sys.path.insert(0,str(Path(__file__).resolve().parent))
    parser=argparse.ArgumentParser();parser.add_argument('source');parser.add_argument('folder');parser.add_argument('--enhanced');parser.add_argument('--panels')
    args=parser.parse_args();r=run(args.source,args.folder,args.enhanced,json.loads(Path(args.panels).read_text()) if args.panels else None)
    print(json.dumps({'wall_candidates':len(r['walls']),'regions':len(r['regions']),'openings':len(r['openings']),'elapsed_seconds':r['elapsed_seconds']}))
