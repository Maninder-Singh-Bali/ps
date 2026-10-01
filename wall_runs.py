"""Review groups share endpoints and tangents; never bridge an opening."""
import math

def groups(plan):
    from raster_reconstruction import paths
    walls=paths(plan);adj={w['id']:set() for w in walls}
    for i,a in enumerate(walls):
        aa=a['geometry']['points']
        for b in walls[i+1:]:
            bb=b['geometry']['points'];joined=False
            for p,q in ((aa[0],aa[1]),(aa[-1],aa[-2])):
                for r,s in ((bb[0],bb[1]),(bb[-1],bb[-2])):
                    # Skeleton junctions share exact pixels. Larger distances
                    # can be genuine doorways and must remain separate.
                    if math.dist(p,r)>1.5:continue
                    u=[q[k]-p[k] for k in (0,1)];v=[s[k]-r[k] for k in (0,1)]
                    den=math.hypot(*u)*math.hypot(*v)
                    if den and sum(u[k]*v[k] for k in (0,1))/den<-.94:joined=True
            if joined:adj[a['id']].add(b['id']);adj[b['id']].add(a['id'])
    result=[];seen=set()
    for key in adj:
        if key in seen:continue
        todo=[key];run=[]
        while todo:
            k=todo.pop()
            if k in seen:continue
            seen.add(k);run.append(k);todo.extend(adj[k]-seen)
        result.append(sorted(run))
    return result
