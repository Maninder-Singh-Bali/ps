"""Room-relative furniture positions and a visual guide for the image renderer."""
import math
from PIL import Image, ImageDraw, ImageFont, ImageOps
from plan_area import summarize, bounds

def active_references(store,room):
    blocks=room.get('block_layout',{}).get('items',[])
    linked={v.get('asset_id') for v in blocks}
    surfaces={aid for v in room.get('surfaces',{}).values() for aid in v.get('image_ids',[])}
    return [store.asset(a) for a in room.get('references',[]) if a not in surfaces and store.asset(a).get('enabled',True) and (not blocks or a in linked)]


def current_layout(room):
    layout=room.get('furniture_layout') or {}
    blocks=room.get('block_layout',{}).get('items',[])
    if blocks and room.get('bbox'):
        b=room['bbox'];linked=[v for v in blocks if v.get('asset_id')]
        previous=layout.get('items',[]) if layout.get('plan_id')==room.get('plan_id') and layout.get('bbox')==b else []
        items=[]  # In block mode the reviewed block list owns the arrangement.
        items += [{'asset_id':v['asset_id'],'x':(v['x']-b[0])/b[2],'y':(v['y']-b[1])/b[3],'angle':v['angle'],'block_id':v['id'],'proportion':[v['width']/b[2],v['depth']/b[3]],'instruction':v.get('prompt',''),**({'size':v['physical_size']} if v.get('physical_size') else {})} for v in linked]
        return {'plan_id':room['plan_id'],'bbox':b,'items':items,'camera_heading':layout.get('camera_heading',0)}
    if layout.get('plan_id')!=room.get('plan_id') or layout.get('bbox')!=room.get('bbox'):
        return {}
    return layout


def validate_layout(room,data):
    if not room.get('plan_id') or not room.get('bbox'):
        raise ValueError('Mark this section on its floor plan before placing furniture.')
    if data.get('revision')!=room['revision']:
        raise ValueError('This room changed while the map was open. Reopen the map to use its latest references.')
    rows=data.get('items')
    if not isinstance(rows,list) or len(rows)>len(room['references']):
        raise ValueError('Choose furniture from this room.')
    heading=data.get('camera_heading',room.get('furniture_layout',{}).get('camera_heading',0))
    if type(heading) not in (int,float) or heading not in (0,90,180,270):raise ValueError('Choose a camera direction on the plan.')
    clean=[];seen=set()
    for row in rows:
        if not isinstance(row,dict):raise ValueError('Invalid furniture position.')
        aid=row.get('asset_id')
        if aid not in room['references'] or aid in seen:raise ValueError('Each reference can have one marker in its own room.')
        values=[row.get(k) for k in ('x','y','angle')]
        if not all(type(v) in (int,float) and math.isfinite(v) for v in values):raise ValueError('Choose a valid position and direction.')
        x,y,angle=values
        if not (0<=x<=1 and 0<=y<=1 and 0<=angle<=360):raise ValueError('Place furniture inside this section.')
        item={'asset_id':aid,'x':round(x,5),'y':round(y,5),'angle':round(angle%360,2)}
        if row.get('size'):
            size=row['size']
            if not isinstance(size,dict) or size.get('unit') not in ('m','ft') or not all(type(size.get(k)) in (int,float) and math.isfinite(size[k]) and 0<size[k]<100 for k in ('width','depth')):raise ValueError('Enter a valid furniture width and depth in metres or feet.')
            item['size']={k:size[k] for k in ('width','depth','unit')}
        clean.append(item);seen.add(aid)
    return {'plan_id':room['plan_id'],'bbox':room['bbox'][:],'items':clean,'camera_heading':heading}


def room_dimensions(store,room):
    """Map room spans to metres using the saved original drawing calibration."""
    p=store.project(store.asset(room['plan_id'])['project_id']);a=store.asset(room['plan_id'])
    if a.get('manual_document',{}).get('calibration') and room.get('bbox'):
        mpp=a['manual_document']['calibration']['metres_per_pixel']
        return {'width_m':room['bbox'][2]*a['width']*mpp,'depth_m':room['bbox'][3]*a['height']*mpp,'method':'manual calibration','estimated':True}
    record=next((m for m in p.get('measurements',[]) if m['plan_id']==room['plan_id'] and m['floor']==room['floor']),None)
    if not record or record['scale']['mode']=='percent':return None
    s=record['scale'];factor=1 if s['unit']=='m' else .3048;b=bounds(record['outline'])
    if s['mode']=='dimensions':mx=s['width']*factor/b[2];my=s['height']*factor/b[3]
    else:
        result=summarize(record['outline'],[],s,a['width'],a['height'],record.get('exclusions',[]))
        mpp=math.sqrt(result['area_m2']['total']/(result['total']*a['width']*a['height']));mx=mpp*a['width'];my=mpp*a['height']
    return {'width_m':room['bbox'][2]*mx,'depth_m':room['bbox'][3]*my,'method':s['mode'],'estimated':True}


def spatial_instructions(store,room,refs,product_board=False,edit_existing=True):
    layout=current_layout(room);items={r['asset_id']:r for r in layout.get('items',[])}
    placed=[(i,a,items[a['id']]) for i,a in enumerate(refs) if a['id'] in items]
    if not placed:return ''
    heading=layout.get('camera_heading',0);theta=math.radians(heading);dims=room_dimensions(store,room)
    facing={0:'away from the camera',90:'toward the photograph right',180:'toward the camera',270:'toward the photograph left'}
    directions={0:'top',90:'right',180:'bottom',270:'left'}
    lines=["FURNITURE RELOCATION IS THE PRIMARY EDIT. The saved placement map overrides the old furniture arrangement in image 1. Retain the architecture and materials, but relocate the selected furniture. Remove each selected object's old instance before placing its replacement. Show exactly one instance of each selected product. Do not keep an object at its old position just to match the reference photograph.",f"Camera orientation: the camera looks toward the {directions[heading]} edge of the floor plan. Interpret the following relations in the FINAL PHOTOGRAPH, not in the source product photos."]
    if not edit_existing:lines[0]='SAVED LAYOUT IS THE COMPOSITION AUTHORITY. Build the room using the corrected plan and furniture markers. Show exactly one instance of each specified product. Product photographs supply object design only; do not copy their backgrounds, labels or additional furnishings.'
    if dims:lines.append(f"Drawing-calibrated room bounding spans: {dims['width_m']:.2f} m across plan and {dims['depth_m']:.2f} m from plan top to bottom. Match furniture scale to these spans.")
    for i,a,row in placed:
        direction=(row['angle']-heading)%360
        desc=facing.get(direction,f'at {direction:g} degrees clockwise from the camera look direction')
        lines.append(f"Product image {i+2} ({a.get('category','furniture')}) must face {desc}. Its plan centre is {row['x']:.1%} from the left and {row['y']:.1%} from the top.")
        if row.get('instruction'):lines.append('Requested change for this block only: '+row['instruction'])
        if dims:lines.append(f"Its centre is {row['x']*dims['width_m']:.2f} m from the room's plan-left bound and {row['y']*dims['depth_m']:.2f} m from its plan-top bound.")
        if row.get('size'):
            z=row['size'];f=1 if z['unit']=='m' else .3048;lines.append(f"This object's physical width is {z['width']*f:.2f} m and depth is {z['depth']*f:.2f} m.")
    for n,(i,a,pa) in enumerate(placed):
        for j,b,pb in placed[n+1:]:
            dx=pa['x']-pb['x'];dy=pa['y']-pb['y'];horizontal=dx*math.cos(theta)+dy*math.sin(theta);depth=dx*math.sin(theta)-dy*math.cos(theta)
            names=f"Product image {i+2} ({a.get('category','furniture')})"
            other=f"product image {j+2} ({b.get('category','furniture')})"
            if abs(horizontal)<.12:lines.append(f"{names} and {other} align on approximately the same left-to-right centreline in the photograph.")
            else:lines.append(f"{names} is to the {'right' if horizontal>0 else 'left'} of {other} in the photograph.")
            if abs(depth)>.12:lines.append(f"{names} is {'farther from the camera, behind' if depth>0 else 'closer to the camera, in front of'} {other}. Preserve this depth ordering.")
    content='\n'.join(lines)
    if product_board:
        for i in range(len(refs)-1,-1,-1):
            content=content.replace(f'Product image {i+2}',f'Product {i+1} in image 2').replace(f'product image {i+2}',f'product {i+1} in image 2')
    return content


def create_product_board(refs,folder):
    """Reference-only contact sheet; never an output image or output upscale."""
    columns=min(3,len(refs));rows=math.ceil(len(refs)/columns);cw,ch=640,720
    board=Image.new('RGB',(columns*cw,rows*ch),'#fff');draw=ImageDraw.Draw(board)
    try:font=ImageFont.truetype('C:/Windows/Fonts/segoeui.ttf',27)
    except OSError:font=ImageFont.load_default()
    for i,a in enumerate(refs):
        x=(i%columns)*cw;y=(i//columns)*ch
        with Image.open(a['path']) as im:
            thumb=ImageOps.contain(ImageOps.exif_transpose(im).convert('RGB'),(cw-32,ch-86))
            board.paste(thumb,(x+(cw-thumb.width)//2,y+60+(ch-76-thumb.height)//2))
        draw.text((x+18,y+16),f"PRODUCT {i+1} - {a.get('category','Furniture')}"[:38],font=font,fill='#202820')
    path=folder/'furniture_product_board.png';board.save(path);return path


def create_guide(store,room,refs,folder,product_board=False):
    layout=current_layout(room)
    rows={r['asset_id']:r for r in layout.get('items',[])}
    placed=[(i,a,rows[a['id']]) for i,a in enumerate(refs) if a['id'] in rows]
    plan=store.asset(room['plan_id']) if room.get('plan_id') else {}
    drawing=plan.get('drawing',{})
    corrected=drawing.get('guidance_asset_id') if drawing.get('edits') or drawing.get('features') else None
    if not placed and not corrected:return None
    if not room.get('bbox'):return None
    plan=store.asset(room['plan_id']);ratio=room['bbox'][2]*plan['width']/(room['bbox'][3]*plan['height'])
    cw=min(740,740*ratio);ch=cw/ratio;ox=55+(740-cw)/2;oy=105+(740-ch)/2
    dims=room_dimensions(store,room)
    canvas=Image.new('RGB',(1200,960),'white');draw=ImageDraw.Draw(canvas)
    try:
        font=ImageFont.truetype('C:/Windows/Fonts/segoeui.ttf',23)
        small=ImageFont.truetype('C:/Windows/Fonts/segoeui.ttf',19)
    except OSError:font=small=ImageFont.load_default()
    draw.text((40,24),'TARGET FURNITURE LAYOUT - '+room['name'],font=font,fill='#252822')
    draw.text((40,60),'Corrected architecture. Use saved furniture markers where shown.',font=small,fill='#515745')
    draw.rectangle((ox,oy,ox+cw,oy+ch),outline='#39483e',width=3)
    guidance=corrected
    if guidance:
        b=room['bbox']
        with Image.open(store.asset(guidance)['path']) as im:
            w,h=im.size
            crop=im.crop((int(b[0]*w),int(b[1]*h),int((b[0]+b[2])*w),int((b[1]+b[3])*h))).convert('RGB')
            canvas.paste(crop.resize((max(1,int(cw)),max(1,int(ch)))),(int(ox),int(oy)))
    draw.text((40,885),f"Camera looks toward plan { {0:'TOP',90:'RIGHT',180:'BOTTOM',270:'LEFT'}[layout.get('camera_heading',0)] }",font=font,fill='#1a5971')
    draw.text((40,925),'Arrows indicate furniture facing. Diagram is a layout guide, not a photograph.',font=small,fill='#515745')
    lines=['The architectural lines are the saved corrected plan: preserve their walls, doors and windows; do not copy furniture from the original drawing.'] if corrected else []
    for i,a,row in placed:
        number=i+1;cx=ox+row['x']*cw;cy=oy+row['y']*ch
        if row.get('size') and dims:
            size=row['size'];f=1 if size['unit']=='m' else .3048;fw=size['width']*f/dims['width_m']*cw;fd=size['depth']*f/dims['depth_m']*ch
            t=math.radians(row['angle']);corners=[(cx+x*math.cos(t)-y*math.sin(t),cy+x*math.sin(t)+y*math.cos(t)) for x,y in [(-fw/2,-fd/2),(fw/2,-fd/2),(fw/2,fd/2),(-fw/2,fd/2)]]
            draw.polygon(corners,fill='#e8ede7',outline='#435e49',width=2)
        theta=math.radians(row['angle']);dx=math.sin(theta);dy=-math.cos(theta)
        ex=cx+43*dx;ey=cy+43*dy
        draw.line((cx,cy,ex,ey),fill='#483512',width=5)
        draw.polygon([(ex,ey),(ex-13*dx-8*dy,ey-13*dy+8*dx),(ex-13*dx+8*dy,ey-13*dy-8*dx)],fill='#483512')
        draw.ellipse((cx-19,cy-19,cx+19,cy+19),fill='#f4c23b',outline='#483512',width=2)
        draw.text((cx,cy),str(number),font=font,anchor='mm',fill='#252822')
        label=f"{number}. {a.get('category','Furniture')} ({'product '+str(number) if product_board else 'image '+str(i+2)})"
        draw.text((855,110+i*105),label[:34],font=small,fill='#252822')
        draw.text((855,141+i*105),f"Facing {row['angle']:g} degrees",font=small,fill='#515745')
        source=f'product {number} on the image 2 reference sheet' if product_board else f'the product in image {i+2}'
        lines.append(f"Marker {number} is {source}, {a.get('category','furniture')}, centered {row['x']:.1%} across and {row['y']:.1%} down this room's plan area; facing {row['angle']:g} degrees clockwise from plan-up.")
    path=folder/'furniture_placement_guide.png';canvas.save(path)
    return path,' '.join(lines)
