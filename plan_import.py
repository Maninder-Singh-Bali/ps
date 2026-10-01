"""Native local DXF / PDF ingestion. Drawing units never imply survey accuracy."""
import math, json, hashlib, re
from pathlib import Path
from html import escape
from collections import Counter
from store import uid, now

UNITS={1:('in',.0254),2:('ft',.3048),4:('mm',.001),5:('cm',.01),6:('m',1),7:('km',1000)}
STYLE='<style>path{fill:none;stroke:#27352f;stroke-width:.8;vector-effect:non-scaling-stroke;stroke-linejoin:round}text{fill:#27352f;font-family:Arial}</style>'

def layer_kind(value):
    v=value.lower();words=set(re.split(r'[^a-z]+',v))
    for key,terms in [('stair',{'stair','stairs','staircase'}),('window',{'window','windows','glazing'}),('door',{'door','doors'}),('wall',{'wall','walls'}),('furniture',{'furn','furniture'})]:
        if words&terms:return key
    return 'detail'

def svg_document(w,h,parts):
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">{STYLE}<rect width="100%" height="100%" style="fill:white;stroke:none"/>'+''.join(parts)+'</svg>'

def dxf(source,folder):
    import ezdxf
    from ezdxf import disassemble, bbox
    from ezdxf.path import make_path
    from ezdxf.path.commands import Command
    doc=ezdxf.readfile(source);raw=list(doc.modelspace())
    if len(raw)>50000:raise ValueError('This DXF is too large for a plan page. Export the floor alone (up to 50,000 entities).')
    entities=[]
    for entity in disassemble.recursive_decompose(raw):
        if len(entities)>=100000:raise ValueError('DXF contains too many nested entities. Export a simplified floor plan.')
        layer=doc.layers.get(entity.dxf.layer)
        if not layer.is_off() and not layer.is_frozen():entities.append(entity)
    box=bbox.extents(entities,fast=False)
    if not box.has_data:raise ValueError('No visible model-space geometry found. Export a 2D model-space DXF.')
    xmin,ymin=box.extmin.x,box.extmin.y;xmax,ymax=box.extmax.x,box.extmax.y
    if not all(math.isfinite(v) for v in (xmin,ymin,xmax,ymax)) or min(xmax-xmin,ymax-ymin)<=0:raise ValueError('DXF has invalid or flat extents.')
    scale=1800/max(xmax-xmin,ymax-ymin);pad=35;w=math.ceil((xmax-xmin)*scale+pad*2);h=math.ceil((ymax-ymin)*scale+pad*2)
    def pt(v):return [(v.x-xmin)*scale+pad,(ymax-v.y)*scale+pad]
    def xy(v):return ' '.join(f'{x:.5f}' for x in pt(v))
    parts=[];unsupported=Counter();layers={};count=0
    from native_source import dxf_manifest
    native=dxf_manifest(doc,raw)
    for ent in entities:
        typ=ent.dxftype();kind=layer_kind(ent.dxf.layer)
        try:
            if typ in ('TEXT','MTEXT'):
                label=ent.dxf.text if typ=='TEXT' else ent.plain_text();pos=pt(ent.dxf.insert)
                size=max(3,(ent.dxf.height if typ=='TEXT' else ent.dxf.char_height)*scale)
                rot=-float(ent.dxf.get('rotation',0));parts.append(f'<text x="{pos[0]}" y="{pos[1]}" font-size="{size}" transform="rotate({rot} {pos[0]} {pos[1]})">{escape(label[:2000])}</text>');continue
            p=make_path(ent);s='M'+xy(p.start)
            for cmd in p:
                if cmd.type==Command.LINE_TO:s+=' L'+xy(cmd.end)
                elif cmd.type==Command.CURVE3_TO:s+=' Q'+xy(cmd.ctrl)+' '+xy(cmd.end)
                elif cmd.type==Command.CURVE4_TO:s+=' C'+xy(cmd.ctrl1)+' '+xy(cmd.ctrl2)+' '+xy(cmd.end)
                elif cmd.type==Command.MOVE_TO:s+=' M'+xy(cmd.end)
            if p.is_closed:s+=' Z'
            cls='opening' if kind=='door' else kind
            parts.append(f'<path id="native{escape(str(ent.dxf.handle or count))}" class="{cls}" d="{s}"/>');count+=1
            if kind!='detail':
                b=bbox.extents([ent]);a=pt(b.extmin);z=pt(b.extmax)
                layers.setdefault((ent.dxf.layer,kind),[]).append([min(a[0],z[0])/w,min(a[1],z[1])/h,abs(z[0]-a[0])/w,abs(z[1]-a[1])/h])
        except (TypeError,ValueError,AttributeError,ZeroDivisionError):unsupported[typ]+=1
    if not count:raise ValueError('No supported 2D linework in this DXF. Export as a vector PDF instead.')
    svg=Path(folder)/'cad_lines.svg';svg.write_text(svg_document(w,h,parts),encoding='utf8')
    from drawing_editor import rasterize
    png=Path(folder)/'cad_plan.png';rasterize(svg,png)
    # rasterize may render at another pixel density; normalize the SVG coordinate
    # system to the raster exactly, so review overlays cannot drift.
    from PIL import Image
    with Image.open(png) as im:rw,rh=im.size
    if (rw,rh)!=(w,h):
        from PIL import Image
        with Image.open(png) as im:im.resize((w,h),Image.Resampling.LANCZOS).save(png)
    unit,factor=UNITS.get(doc.units,('unspecified',None));candidates=[]
    for (name,kind),boxes in layers.items():
        if kind not in ('stair','door','window'):continue
        # Layer evidence is per entity, not a blanket declaration of all geometry.
        for b in boxes[:20]:
            if min(b[2:])<.002:continue
            candidates.append({'kind':kind,'label':name,'bbox':b,'confidence':'medium','evidence':f'Native DXF entity on layer {name}. Layer naming is evidence; review symbol geometry.'})
    metadata={'format':'DXF','vector':True,'units':unit,'units_to_metres':factor,'drawing_extents':[xmin,ymin,xmax,ymax],
              'native_geometry_count':count,'native_source':native,'model_to_page':[scale,0,0,-scale,pad-xmin*scale,pad+ymax*scale],'layers':sorted({e.dxf.layer for e in entities}),
              'symbol_candidates':candidates[:60],'metres_per_pixel':factor/scale if factor else None,
              'warnings':['DXF units are declared by its author; verify a known length before applying scale.','Model space imported; paper layouts and external references are not expanded.']+
              ([f'Some entities were omitted: {dict(unsupported)}. Check the original.'] if unsupported else [])}
    return [{'path':png,'vector_path':svg,'metadata':metadata}]

def pdf(source,folder):
    import pymupdf
    rows=[]
    with pymupdf.open(source) as doc:
        if doc.needs_pass:raise ValueError('Use an unlocked PDF.')
        if len(doc)>20:raise ValueError('Upload a PDF with no more than 20 plan pages.')
        for i,page in enumerate(doc):
            scale=min(3,2800/max(page.rect.width,page.rect.height));pix=page.get_pixmap(matrix=pymupdf.Matrix(scale,scale),alpha=False)
            png=Path(folder)/f'plan_page_{i+1}.png';pix.save(png);w,h=pix.width,pix.height
            paths=page.get_drawings();parts=[];rotation=page.rotation_matrix
            def pt(p):
                q=p*rotation;return [q.x/page.rect.width*w,q.y/page.rect.height*h]
            def xy(p):return ' '.join(f'{v:.4f}' for v in pt(p))
            for draw_index,draw in enumerate(paths):
                commands=[];end=None
                for item in draw['items']:
                    if item[0] in ('l','c'):
                        if end!=item[1]:commands.append('M'+xy(item[1]))
                        commands.append(('L'+xy(item[2])) if item[0]=='l' else 'C'+' '.join(xy(v) for v in item[2:]));end=item[-1]
                    elif item[0]=='re':
                        r=item[1];commands.append('M'+xy(r.tl)+' L'+xy(r.tr)+' L'+xy(r.br)+' L'+xy(r.bl)+' Z');end=None
                    elif item[0]=='qu':
                        q=item[1];commands.append('M'+xy(q.ul)+' L'+xy(q.ur)+' L'+xy(q.lr)+' L'+xy(q.ll)+' Z');end=None
                if draw.get('closePath'):commands.append('Z')
                if commands:parts.append(f'<path id="pdfpage{i+1}path{draw_index}" class="detail" stroke-width="{float(draw.get("width") or .8)*scale}" d="'+ ' '.join(commands)+'"/>')
            for b in page.get_text('dict')['blocks']:
                for line in b.get('lines',[]):
                    for span in line['spans']:
                        pos=pt(pymupdf.Point(span['origin']));parts.append(f'<text x="{pos[0]}" y="{pos[1]}" font-size="{span["size"]*scale}">{escape(span["text"])}</text>')
            svg=None
            if paths:
                svg=Path(folder)/f'plan_page_{i+1}_lines.svg';svg.write_text(svg_document(w,h,parts),encoding='utf8')
            rows.append({'path':png,'vector_path':svg,'metadata':{'format':'PDF','page':i+1,'vector':bool(paths),'native_geometry_count':len(paths),'native_paths':__import__('native_source').safe(paths),'page_transform':list(page.rotation_matrix),'text_blocks':__import__('native_source').safe(page.get_text('dict',flags=0)['blocks']),'embedded_images':len(page.get_images()),'units':'page points, not building units',
                'warnings':['PDF page size is not building scale. Calibrate using a known dimension.', 'Vector line view omits embedded raster images; compare with the original page.'] if paths else ['Scanned PDF: no native vector paths detected. Calibrate the drawing; enlargement adds no missing detail.']}})
    return rows

def import_file(source,folder):
    suffix=Path(source).suffix.lower()
    if suffix=='.dwg':raise ValueError('Native DWG needs conversion. Export a model-space DXF or vector PDF from your CAD application, then upload it here.')
    return dxf(source,folder) if suffix=='.dxf' else pdf(source,folder)

def attach(st,a,item,original):
    a['plan_source']=item['metadata']
    # Register the actual document, not only its rendered page, so relocation and
    # the project manifest keep the CAD/PDF source alongside every derived view.
    source=next((v for v in st.db['assets'].values() if v.get('project_id')==a['project_id'] and v.get('path')==str(original) and v.get('kind')=='plan_document'),None)
    if not source:
        key=uid();source={'id':key,'project_id':a['project_id'],'kind':'plan_document','path':str(original),'name':original.name,
            'created':now(),'sha256':hashlib.sha256(original.read_bytes()).hexdigest()};st.db['assets'][key]=source
    a['original_document_id']=source['id']
    svg=item.get('vector_path')
    if svg:
        key=uid();st.db['assets'][key]={'id':key,'project_id':a['project_id'],'kind':'plan_vector','path':str(svg),'name':svg.name,'width':a['width'],'height':a['height'],
            'created':now(),'source_asset_id':a['id'],'sha256':hashlib.sha256(svg.read_bytes()).hexdigest(),'enhancement':'Native document linework; not an AI redraw'}
        a['cad_redraw_id']=key;a['native_vector_id']=key
