"""Versioned, non-destructive edits to detected SVG drawing elements."""
import copy, hashlib, json, math, re, os, shutil, subprocess
from pathlib import Path
from xml.etree import ElementTree as ET
from html import escape
from store import editing_busy, uid, now
from scene_sun import clean_site, solar_summary, number
import project_storage

STYLE='path,line,polyline,polygon,rect,circle,ellipse{fill:none;stroke:#37443e;stroke-width:.8;vector-effect:non-scaling-stroke;stroke-linejoin:miter}.wall{stroke:#24342c;stroke-width:1.1}.window{stroke:#4e716a}.opening{stroke:#8a6b36}.furniture{stroke:#67756b}text{font:7px Arial;fill:#37443e;stroke:none}'
TAGS={'g','path','line','polyline','polygon','rect','circle','ellipse','text'}
ATTRS={'class','d','points','x','y','width','height','rx','ry','cx','cy','r','x1','y1','x2','y2','transform','font-size','stroke-width'}

def combine_wall_edges(elements,edits,width,height):
    """Pair matching straight boundary strokes; never join unequal spans/openings."""
    candidates=[]
    number_pattern=r'(-?\d+(?:\.\d+)?)'
    for e in elements:
        if e['kind']!='wall':continue
        node=ET.fromstring(e['svg'])
        if node.tag!='path' or node.get('transform'):continue
        match=re.fullmatch(r'M\s*'+number_pattern+r'[ ,]+'+number_pattern+r'\s*([HV])\s*'+number_pattern,node.get('d',''))
        if not match:continue
        x,y,axis,end=match.groups();x,y,end=map(float,(x,y,end))
        start,offset=(x,y) if axis=='H' else (y,x)
        candidates.append((e,axis,min(start,end),max(start,end),offset))
    used=set();limit=max(.5,min(width,height)*.01)
    for i,(a,axis,lo,hi,offset) in enumerate(candidates):
        if a['id'] in used:continue
        for b,other_axis,other_lo,other_hi,other_offset in candidates[i+1:]:
            gap=abs(other_offset-offset)
            if b['id'] in used or axis!=other_axis or abs(lo-other_lo)>.01 or abs(hi-other_hi)>.01 or not .1<=gap<=limit:continue
            # Keep independently corrected second boundaries intact.
            edit=edits.get(b['id'],{})
            if edit.get('hidden') or any(abs(edit.get(k,default)-default)>1e-8 for k,default in [('dx',0),('dy',0),('sx',1),('sy',1),('rotation',0)]):continue
            x,y,w,h=(lo,min(offset,other_offset),hi-lo,gap) if axis=='H' else (min(offset,other_offset),lo,gap,hi-lo)
            a['svg']=f'<rect class="wall" x="{x}" y="{y}" width="{w}" height="{h}"/>'
            b['absorbed_by']=a['id'];used.update([a['id'],b['id']]);break
    return elements
def sanitized(node):
    tag=node.tag.split('}')[-1]
    if tag not in TAGS or tag=='rect' and 'fill:white' in node.get('style','').replace(' ',''):return ''
    attrs={k:v for k,v in node.attrib.items() if k in ATTRS and not re.search(r'url\s*\(|javascript:|[<>]',v,re.I)}
    paint={}
    allowed_paint={'fill','stroke','stroke-width','stroke-opacity','fill-opacity','fill-rule','stroke-dasharray','stroke-dashoffset'}
    for declaration in node.get('style','').split(';'):
        key,sep,value=declaration.partition(':');key=key.strip();value=value.strip()
        if sep and key in allowed_paint and re.fullmatch(r'[a-zA-Z0-9#., +%-]+',value):paint[key]=value
    if paint:attrs['style']=';'.join(k+':'+v for k,v in paint.items())
    return '<'+tag+' '+ ' '.join(k+'="'+escape(v,quote=True)+'"' for k,v in attrs.items())+'>'+ (escape(node.text or '') if tag=='text' else ''.join(sanitized(n) for n in node))+'</'+tag+'>'

def get_document(st,pid,aid):
    p=st.project(pid)
    if aid not in p['floor_plans']:raise ValueError('Choose a plan from this project.')
    a=st.asset(aid);saved=a.get('drawing',{});base=saved['base_asset_id'] if 'base_asset_id' in saved else a.get('cad_redraw_id') or a.get('vector_preview_id')
    elements=[]
    if base:
        b=st.asset(base)
        if b.get('project_id')!=pid:raise ValueError('Drawing belongs to another project.')
        root=ET.fromstring(Path(b['path']).read_text(encoding='utf8'))
        for i,n in enumerate(root):
            markup=sanitized(n)
            if markup:
                cls=n.get('class') or next((v.get('class') for v in n if v.get('class')),'detail')
                element={'id':'base'+str(i),'svg':markup,'kind':cls,'native_source_id':n.get('id')}
                from native_review import annotate,classified
                annotate(element,a)
                elements.append(classified(element,saved.get('edits',{}).get(element['id'],{})))
    from raster_reconstruction import elements as raster_elements
    elements.extend(raster_elements(a))
    elements=combine_wall_edges(elements,saved.get('edits',{}),a['width'],a['height'])
    return {'units':a.get('manual_document',{}).get('units','m'),'manual_draft_id':a.get('manual_draft_id'), 'review':copy.deepcopy(a.get('structure_review')), 'revision':saved.get('revision',0),'base_asset_id':base,'elements':elements,'edits':copy.deepcopy(saved.get('edits',{})),'features':copy.deepcopy(saved.get('features',[])),'surface_design':copy.deepcopy(saved.get('surface_design',{})),'surface_design_floor':saved.get('surface_design_floor'),'site':copy.deepcopy(saved.get('site',{})),'width':a['width'],'height':a['height'],'map_revision':p['map_revision']}

def clean_changes(doc,data):
    edits=data.get('edits',{});features=data.get('features',[])
    if not isinstance(edits,dict) or not isinstance(features,list) or len(features)>400:raise ValueError('Use up to 400 added drawing elements.')
    ids={e['id'] for e in doc['elements']};clean={}
    for key,v in edits.items():
        if key not in ids or not isinstance(v,dict):raise ValueError('Unknown drawing element. Reopen the editor.')
        clean[key]={k:number(v.get(k,default),lo,hi,k) for k,default,lo,hi in [('dx',0,-doc['width'],doc['width']),('dy',0,-doc['height'],doc['height']),('sx',1,.01,100),('sy',1,.01,100),('rotation',0,-360,360),('cx',0,0,doc['width']),('cy',0,0,doc['height'])]}
        clean[key]['hidden']=v.get('hidden') is True
        if 'kind' in v:
            from native_review import classified
            classified(next(e for e in doc['elements'] if e['id']==key),v)
            clean[key]['kind']=v['kind']
    out=[];seen=set()
    for v in features:
        if not isinstance(v,dict) or v.get('kind') not in ('wall','window','door','sliding_door','line','floor_opening'):raise ValueError('Invalid drawing feature.')
        key=v.get('id','')
        if not isinstance(key,str) or not re.fullmatch(r'new[a-zA-Z0-9_-]{1,60}',key) or key in seen:raise ValueError('Invalid feature identifier.')
        seen.add(key);pts=v.get('points')
        if not isinstance(pts,list) or len(pts)!=2:raise ValueError('Draw both ends of the feature.')
        points=[]
        for pt in pts:
            if not isinstance(pt,list) or len(pt)!=2:raise ValueError('Invalid drawing point.')
            points.append([number(pt[0],0,doc['width'],'horizontal position'),number(pt[1],0,doc['height'],'vertical position')])
        if math.dist(*points)<.2:raise ValueError('Draw a longer element.')
        if v['kind']=='floor_opening' and any(abs(points[0][i]-points[1][i])<.2 for i in (0,1)):raise ValueError('A floor opening needs a nonzero width and depth.')
        out.append({'id':key,'kind':v['kind'],'points':points,'thickness':number(v.get('thickness',1.5),.1,50,'line separation'),'flip':v.get('flip') is True})
    previous={f['id']:f for f in doc.get('features',[])}
    for original,feature in zip(features,out):
        note=original.get('review_note','')
        if not isinstance(note,str):raise ValueError('Review note must be text.')
        if note:feature['review_note']=note[:1000]
        evidence=previous.get(feature['id'],{}).get('evidence')
        if evidence:
            feature['evidence']=copy.deepcopy(evidence)
            feature['evidence']['manually_changed']=(feature['points']!=evidence.get('source_points') or feature['thickness']!=evidence.get('source_thickness',feature['thickness']))
    return clean,out

def transform(v):
    cx,cy=v.get('cx',0),v.get('cy',0)
    return f"translate({v.get('dx',0)} {v.get('dy',0)}) translate({cx} {cy}) rotate({v.get('rotation',0)}) scale({v.get('sx',1)} {v.get('sy',1)}) translate({-cx} {-cy})"

def feature_svg(v):
    if v['kind']=='floor_opening':return ''
    (x,y),(x2,y2)=v['points'];length=math.hypot(x2-x,y2-y);a=math.degrees(math.atan2(y2-y,x2-x));t=v['thickness']/2;kind=v['kind']
    if kind=='wall':path=f'M0 {-t} H{length} V{t} H0 Z'
    elif kind=='door':
        sign=-1 if v['flip'] else 1
        path=f'M0 0 V{sign*length} M{length} 0 A{length} {length} 0 0 {1 if sign>0 else 0} 0 {sign*length}'
    elif kind=='sliding_door':path=f'M0 {-t} H{length*.58} M{length*.42} {t} H{length} M0 0 H{length}'
    elif kind=='line':path=f'M0 0 H{length}'
    else:path=f'M0 {-t} H{length} M0 {t} H{length}'+(f' M0 0 H{length} M0 {-t} V{t} M{length} {-t} V{t}' if kind=='window' else '')
    return f'<g transform="translate({x} {y}) rotate({a})"><path class="{ "opening" if kind=="door" else kind}" d="{path}"/></g>'

def export_svg(doc,edits,features):
    parts=[]
    for e in doc['elements']:
        if e.get('absorbed_by'):continue
        v=edits.get(e['id'],{})
        if not v.get('hidden'):
            from native_review import classified
            parts.append(f'<g transform="{transform(v)}">{classified(e,v)["svg"]}</g>')
    parts.extend(feature_svg(f) for f in features)
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{doc["width"]}" height="{doc["height"]}" viewBox="0 0 {doc["width"]} {doc["height"]}"><title>User-corrected floor plan</title><style>{STYLE}</style><rect width="100%" height="100%" style="fill:white;stroke:none"/>'+''.join(parts)+'</svg>'

def rasterize(source,destination):
    bundled=Path(__file__).resolve().parent/'runtime'/'node'
    node=os.environ.get('PIXELOID_NODE') or str(bundled/'node.exe')
    if not Path(node).exists():node=shutil.which('node')
    if not node:raise ValueError('Drawing export is unavailable. Open System check to restore the bundled drawing component.')
    env=os.environ.copy();env['NODE_PATH']=os.pathsep.join(filter(None,[str(bundled/'node_modules'),env.get('NODE_PATH')]))
    result=subprocess.run([node,str(Path(__file__).with_name('render_plan.cjs')),str(source),str(destination)],env=env,capture_output=True,text=True,timeout=40,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    if result.returncode:raise ValueError('Could not export the corrected plan. '+result.stderr[:300])

def save_document(st,pid,aid,data):
    p=st.project(pid);doc=get_document(st,pid,aid);a=st.asset(aid)
    if editing_busy(st,pid):raise ValueError('Finish the active generation before changing this drawing.')
    if data.get('revision')!=doc['revision'] or data.get('map_revision')!=p['map_revision']:raise ValueError('The drawing changed. Reopen it before saving.')
    if a.get('manual_document'):
        # Canonical manual geometry includes junctions, opening hosts and surfaces.
        # The older SVG editor cannot round-trip these records losslessly.
        if any(data.get(k,{ } if k!='features' else [])!=doc[k] for k in ('edits','features','site')):
            raise ValueError('Edit architecture, scale and wall heights in the linked floor plan editor. Furniture and cameras remain editable here.')
        return {'ok':True,'revision':doc['revision']}
    edits,features=clean_changes(doc,data);site=clean_site(data.get('site',{}))
    geometry=edits!=doc['edits'] or features!=doc['features'];site_changed=site!=doc['site']
    if not geometry and not site_changed:return {'ok':True,'revision':doc['revision']}
    rev=doc['revision']+1;folder=project_storage.project_root(st,pid)/'Supporting_Files'/'Drawings';folder.mkdir(parents=True,exist_ok=True)
    token=uid();svg_path=folder/f'Plan_{aid}_v{rev}_{token}.svg';text=export_svg(doc,edits,features);svg_path.write_text(text,encoding='utf8')
    # Export only architectural lines to conditioning. Old drawn furniture must
    # not compete with the user's newly placed product markers.
    arch_doc={**doc,'elements':[{**e,'svg':re.sub(r'<text\b[^>]*>.*?</text>','',e['svg'],flags=re.S)} for e in doc['elements'] if e['kind'] in ('wall','opening','window','detail','line')]}
    arch_path=svg_path.with_name(svg_path.stem+'_architecture.svg');arch_path.write_text(export_svg(arch_doc,edits,features),encoding='utf8')
    png=arch_path.with_suffix('.png');rasterize(arch_path,png)
    record={'revision':rev,'base_asset_id':doc['base_asset_id'],'edits':edits,'features':features,'site':site,'updated':now()}
    svg_id=uid();asset={'id':svg_id,'project_id':pid,'room_id':None,'kind':'plan_vector','name':svg_path.name,'path':str(svg_path),'created':now(),'width':a['width'],'height':a['height'],'sha256':hashlib.sha256(text.encode()).hexdigest(),'source_asset_id':aid}
    (folder/f'Plan_{aid}_v{rev}_{token}.json').write_text(json.dumps(record,indent=2),encoding='utf8')
    st.db['assets'][svg_id]=asset;a['drawing']=record;a['cad_redraw_id']=svg_id
    from PIL import Image
    with Image.open(png) as im:w,h=im.size
    raster_id=uid();st.db['assets'][raster_id]={'id':raster_id,'project_id':pid,'kind':'plan_guidance','name':png.name,'path':str(png),'created':now(),'width':w,'height':h,'source_asset_id':aid}
    a['drawing']['guidance_asset_id']=raster_id
    if geometry or site_changed:
        for r in p['rooms']:
            if r.get('plan_id')==aid:st.invalidate(pid,r)
    if geometry:
        p['map_confirmed']=False;p['map_revision']+=1
        if a.get('plan_reading'):
            a['plan_reading']['reviewed']=False
            a['plan_reading']['checks']={}
            a['plan_reading']['revision']+=1
    st.save();return {'ok':True,'asset_id':svg_id,'revision':rev,'map_changed':geometry,'solar':solar_summary(site)}
