"""Explicit review of native filled rectangles; no semantic inference from boxes."""
import json, math, re
from xml.etree import ElementTree as ET

def rectangle(svg):
    from drawing_scene import segments
    node=ET.fromstring(svg)
    if node.tag!='path' or node.get('transform'):return None
    try:edges=segments(node.get('d',''))
    except (ValueError,IndexError):return None
    if len(edges)!=4 or any(math.dist(edges[i][1],edges[(i+1)%4][0])>.001 for i in range(4)):return None
    pts=[a for a,b in edges]
    if any(abs(a[0]-b[0])>.001 and abs(a[1]-b[1])>.001 for a,b in edges):return None
    xs=sorted({p[0] for p in pts});ys=sorted({p[1] for p in pts})
    if len(xs)!=2 or len(ys)!=2 or set(map(tuple,pts))!={(x,y) for x in xs for y in ys}:return None
    return [xs[0],ys[0],xs[1]-xs[0],ys[1]-ys[0]]

def annotate(element,plan):
    match=re.fullmatch(r'pdfpage\d+path(\d+)',element.get('native_source_id') or '')
    paths=plan.get('plan_source',{}).get('native_paths',[])
    if not match or int(match[1])>=len(paths):return
    source=paths[int(match[1])];fill=source.get('fill')
    if not fill or min(fill)>.98 or source.get('fill_opacity',1)<.99:return
    rect=rectangle(element['svg'])
    if rect is None:return
    element['native_rectangle']=rect
    element['native_original_svg']=element['svg']
    element['native_fill_group']=json.dumps([fill,source.get('fill_opacity',1)],separators=(',',':'))

def classified(element,edit):
    kind=edit.get('kind')
    if kind is None:return element
    if kind not in ('wall','detail') or not element.get('native_rectangle'):
        raise ValueError('Only reviewed native filled rectangles can be classified as walls.')
    result={**element,'kind':kind}
    if kind=='wall':
        x,y,w,h=element['native_rectangle']
        result['svg']=f'<rect class="wall" x="{x}" y="{y}" width="{w}" height="{h}"/>'
    else:
        result['svg']=element['native_original_svg']
    return result
