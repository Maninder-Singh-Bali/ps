"""Saved-evidence comparison; no scene, review, or image mutations."""
import math
from scene_control import file_identity


def crop_bounds(control, width, height):
    region = control.get('region')
    polygon = control.get('mask_polygon')
    if polygon and len(polygon) >= 3:
        if any(len(p) != 2 or any(not isinstance(v,(int,float)) or not math.isfinite(v) or not 0 <= v <= 1 for v in p) for p in polygon):
            return None, None
        xs,ys=zip(*polygon);region=[min(xs),min(ys),max(xs)-min(xs),max(ys)-min(ys)]
    if not region or len(region)!=4 or any(not isinstance(v,(int,float)) or not math.isfinite(v) for v in region):
        return None,None
    x,y,w,h=region
    if x<0 or y<0 or w<=0 or h<=0 or x+w>1.000001 or y+h>1.000001:return None,None
    margin=max(24,math.ceil(max(w*width,h*height)*.2),control.get('feather',0))
    left=max(0,math.floor(x*width-margin));top=max(0,math.floor(y*height-margin))
    right=min(width,math.ceil((x+w)*width+margin));bottom=min(height,math.ceil((y+h)*height+margin))
    outline=polygon or [[x,y],[x+w,y],[x+w,y+h],[x,y+h]]
    return [left,top,right-left,bottom-top],[[p[0]*width,p[1]*height] for p in outline]


def review(store, aid):
    a=store.asset(aid);p=store.project(a['project_id']);r=store.room(p['id'],a['room_id'])
    if a['kind']!='image' or aid not in r['images']:raise ValueError('Choose a saved room image.')
    file_identity(store,aid)
    j=store.db['jobs'].get(a.get('job_id'),{});m=j.get('scene_manifest') or {};c=m.get('preservation') or m.get('content',{}).get('control') or {}
    links=[(a.get('source_image_id'),'saved image link'),(j.get('source_image_id'),'saved job link'),((m.get('master_image') or {}).get('id'),'recorded manifest evidence'),(c.get('source_id'),'recorded manifest evidence')]
    parent_id,provenance=next(((i,s) for i,s in links if i),(None,'No saved parent link'))
    parent=None;parent_note=provenance
    try:
        if len({i for i,_ in links if i})>1:raise ValueError('Conflicting parent links; comparison withheld.')
        if parent_id:
            parent=store.asset(parent_id)
            if parent['project_id']!=p['id'] or parent['room_id']!=r['id']:raise ValueError('Parent does not belong to this room.')
            identity=file_identity(store,parent_id);record=m.get('master_image') or {}
            if record.get('id')==parent_id and record.get('sha256') and identity['sha256']!=record['sha256']:raise ValueError('Historical parent hash differs.')
    except (ValueError,KeyError,OSError) as e:parent=None;parent_note=str(e)
    ref=None;ref_note='Exact historical conditioning reference unavailable: no single reference recorded.'
    ref_id=c.get('reference_id')
    if ref_id:
        try:
            record=next(v for v in m.get('content',{}).get('products',[]) if v['id']==ref_id)
            identity=file_identity(store,ref_id)
            if not record.get('sha256') or identity['sha256']!=record['sha256']:raise ValueError('Historical reference hash differs.')
            asset=store.asset(ref_id);rw,rh=asset['width'],asset['height'];box=[0,0,rw,rh]
            saved=j.get('reference_crop') or {}
            if c.get('reference_crop'):
                if saved.get('asset_id')==ref_id and saved.get('source_box'):
                    x,y,right,bottom=saved['source_box'];box=[x,y,right-x,bottom-y]
                else:
                    x,y,w,h=c['reference_crop'];left,top,right,bottom=round(x*rw),round(y*rh),round((x+w)*rw),round((y+h)*rh);box=[left,top,right-left,bottom-top]
            if box[2]<=0 or box[3]<=0:raise ValueError('Historical reference crop is invalid.')
            ref={'id':ref_id,'url':'/media/'+ref_id,'width':rw,'height':rh,'crop':box,'label':record.get('category','Selected reference'),'sha256':record['sha256']}
            ref_note='Historical conditioning source'+(' · saved isolated crop' if c.get('reference_crop') else ' · full reference')+' (before sampler preprocessing)'
        except (ValueError,KeyError,OSError,StopIteration,TypeError):
            ref_note='Exact historical conditioning reference unavailable or unverified. No current reference substituted.'
    crop,outline=crop_bounds(c,a['width'],a['height']) if c.get('mode')=='region' else (None,None)
    reason=''
    if not parent or (parent['width'],parent['height'])!=(a['width'],a['height']):crop=None;reason='Matched close-up unavailable: parent missing or image dimensions differ.'
    elif not crop:reason='No saved mask bounds. Showing full room; no edit region inferred.'
    def image_row(v):
        return {'id':v['id'],'url':'/media/'+v['id'],'width':v['width'],'height':v['height'],'version':r['images'].index(v['id'])+1 if v['id'] in r['images'] else None}
    return {'result':image_row(a),'parent':image_row(parent) if parent else None,'parent_note':parent_note,'reference':ref,'reference_note':ref_note,'crop':crop,'outline':outline,'fallback_reason':reason,'status':a.get('status'),'review_decision':a.get('review_decision'),'phase':p.get('generation_phase')}
