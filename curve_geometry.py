"""Preserve SVG source curves and flatten only for bounded-error mesh construction."""
import math
from fontTools.pens.basePen import BasePen
from fontTools.svgLib.path import parse_path

class CurvePen(BasePen):
    def __init__(self,tolerance=.25):
        super().__init__(None);self.tolerance=tolerance;self.parts=[];self.current=None;self.start=None
    def _moveTo(self,p):self.current=tuple(p);self.start=tuple(p)
    def _lineTo(self,p):
        if len(self.parts)>=8192:raise ValueError('Curve exceeds preview segment budget.')
        if not all(math.isfinite(v) for v in p):raise ValueError('Non-finite curve.')
        if self.current!=tuple(p):self.parts.append((self.current,tuple(p)))
        self.current=tuple(p)
    def _closePath(self):self._lineTo(self.start)
    def _endPath(self):pass
    def flatten(self,points,depth=0):
        a,b=points[0],points[-1];length=math.dist(a,b)
        error=max((abs((b[0]-a[0])*(p[1]-a[1])-(b[1]-a[1])*(p[0]-a[0]))/length if length else math.dist(a,p)) for p in points[1:-1])
        # Include excess control polygon length: collinear reversals need splitting.
        excess=sum(math.dist(p,q) for p,q in zip(points,points[1:]))-length
        if error<=self.tolerance and excess<=self.tolerance:self._lineTo(b);return
        if depth>=18:raise ValueError('Curve tolerance could not be met.')
        levels=[points]
        while len(levels[-1])>1:levels.append([tuple((a+b)/2 for a,b in zip(p,q)) for p,q in zip(levels[-1],levels[-1][1:])])
        self.flatten([level[0] for level in levels],depth+1)
        self.flatten([level[-1] for level in reversed(levels)],depth+1)
    def _curveToOne(self,a,b,c):self.flatten([self.current,a,b,c])
    def _qCurveToOne(self,a,b):self.flatten([self.current,a,b])

def segments(path,tolerance=.25):
    if not isinstance(path,str) or len(path)>1000000:raise ValueError('Invalid curve data.')
    pen=CurvePen(tolerance);parse_path(path,pen);return pen.parts

def floor_faces(outline,holes=()):
    """Exact trapezoid decomposition of polygonal floors, including concavity/voids.

    Reuses the existing area editor's scanline geometry; does not fan-triangulate
    concave polygons or bridge holes. Input vertices are normalized page coords.
    """
    from plan_area import polygon,edges,crossing,intervals,subtract,EPS
    outline=polygon(outline);holes=[polygon(h) for h in holes];allp=[outline]+holes
    es=[edge for p in allp for edge in edges(p)];cuts={p[0] for poly in allp for p in poly}
    for i,(a,b) in enumerate(es):
        for c,d in es[i+1:]:
            q=crossing(a,b,c,d)
            if q is not None:cuts.add(q[0])
    result=[];cuts=sorted(cuts)
    for left,right in zip(cuts,cuts[1:]):
        if right-left<EPS:continue
        mid=(left+right)/2
        spans=subtract(intervals(outline,mid),[v for h in holes for v in intervals(h,mid)])
        active=[(a,b) for a,b in es if min(a[0],b[0])<mid<max(a[0],b[0])]
        def y(edge,x):
            a,b=edge;return a[1]+(x-a[0])*(b[1]-a[1])/(b[0]-a[0])
        for lo,hi in spans:
            lower=min(active,key=lambda e:abs(y(e,mid)-lo));upper=min(active,key=lambda e:abs(y(e,mid)-hi))
            result.append([[left,y(lower,left)],[right,y(lower,right)],[right,y(upper,right)],[left,y(upper,left)]])
    return result
