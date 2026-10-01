"""Versioned evidence scope shared by every plan reader. Crops are never geometry."""
import copy
import hashlib
import json
from pathlib import Path
from PIL import Image, ImageOps

VERSION = 1


def capture(plan, approved=True):
    from source_panels import valid
    native = bool(plan.get('plan_source', {}).get('vector'))
    review = plan.get('source_review') or {}
    native_whole = native and not review
    allowed = native_whole or valid(plan)
    if approved and not allowed:
        raise ValueError('Review and approve top-down plan panels before analysis.')
    panels = ([{'id': 'native', 'bbox': [0, 0, 1, 1]}] if native_whole else review.get('panels', []))
    width, height = plan['width'], plan['height']
    rows = []
    for panel in panels:
        x, y, w, h = panel['bbox']
        box = [round(x*width), round(y*height), round((x+w)*width), round((y+h)*height)]
        if box[2] <= box[0] or box[3] <= box[1]:
            raise ValueError('Plan panel has no source pixels.')
        rows.append({'id': panel['id'], 'floor': panel.get('floor', ''), 'bbox': list(panel['bbox']),
                     'pixel_box': box, 'crop_to_sheet': [1, 0, 0, 1, box[0], box[1]],
                     'normalized_to_sheet': [box[0]/width, box[1]/height,
                                            (box[2]-box[0])/width, (box[3]-box[1])/height]})
    result = {'version': VERSION, 'source_sha256': plan.get('sha256'), 'source_size': [width, height],
              'revision': review.get('revision', -1), 'approved': allowed, 'panels': rows}
    result['key'] = hashlib.sha256(json.dumps(result, sort_keys=True).encode()).hexdigest()
    return result


def current(plan, scope):
    return isinstance(scope,dict) and bool(scope.get('key')) and capture(plan, approved=False)['key'] == scope['key']


def prepare(st, job):
    """Check queued identity before classification and bind the approved snapshot."""
    from source_panels import ensure
    from store import now
    aid = job['plan_id']
    with st.lock:
        if job.get('status') == 'cancelled': return None
        if job.get('source_scope') and not current(st.asset(aid), job['source_scope']):
            st.update_job(job['id'], status='cancelled', stage='Source scope changed; result discarded', finished=now())
            return None
    if not ensure(st, job['project_id'], aid):
        st.update_job(job['id'], status='completed', blocked_on='source_review',
                      stage='Approve source panels to resume processing', finished=now())
        return None
    with st.lock:
        # A user edit during classification wins. Only automatic first classification
        # may replace an unclassified queued scope.
        scope = capture(st.asset(aid))
        old = job.get('source_scope')
        if old and old['revision'] != -1 and old['key'] != scope['key']:
            st.update_job(job['id'], status='cancelled', stage='Source scope changed; result discarded', finished=now())
            return None
        if old and old['revision'] == -1 and scope['revision'] > 0:
            st.update_job(job['id'], status='cancelled', stage='Source reviewed while preparing; newer job retained', finished=now())
            return None
        st.update_job(job['id'], source_scope=scope, blocked_on=None)
        return scope


def materialize(plan, scope, folder):
    """Write original-pixel crops only; callers cannot accidentally read margins."""
    if not current(plan, scope): raise ValueError('Source scope changed.')
    raw = Path(plan['path']).read_bytes()
    if hashlib.sha256(raw).hexdigest() != scope['source_sha256']:
        raise ValueError('Original file changed; reimport it before analysis.')
    folder = Path(folder)/scope['key']; folder.mkdir(parents=True, exist_ok=True)
    with Image.open(plan['path']) as source:
        source = ImageOps.exif_transpose(source).convert('RGB')
        if list(source.size) != scope['source_size']: raise ValueError('Source dimensions changed.')
        result = []
        for index, panel in enumerate(scope['panels']):
            path = folder/f'panel-{index}.png'
            if not path.exists(): source.crop(panel['pixel_box']).save(path)
            result.append({**copy.deepcopy(panel), 'path': str(path)})
        # The raster worker retains sheet coordinates, but receives no excluded pixels.
        masked = folder/'approved-pixels.png'
        if not masked.exists():
            image = Image.new('RGB', source.size, 'white')
            for panel in scope['panels']:
                box = panel['pixel_box']; image.paste(source.crop(box), box[:2])
            image.save(masked)
    return result, masked


def map_row(row, panel, scope):
    result = copy.deepcopy(row)
    x, y, w, h = panel['normalized_to_sheet']
    if result.get('bbox'):
        a, b, c, d = result['bbox']; result['bbox'] = [x+a*w, y+b*h, c*w, d*h]
    if result.get('polygon'):
        result['polygon'] = [[x+a*w, y+b*h] for a, b in result['polygon']]
    result.update(panel_id=panel['id'], source_scope_key=scope['key'])
    if panel.get('floor'): result['floor'] = panel['floor']
    return result


def local_sections(sections, panel):
    x, y, w, h = panel['normalized_to_sheet']; result = []
    for row in sections:
        if not row.get('bbox'): continue
        a, b, c, d = row['bbox']; left, top = max(a, x), max(b, y)
        right, bottom = min(a+c, x+w), min(b+d, y+h)
        if right > left and bottom > top:
            result.append({**row, 'bbox': [(left-x)/w, (top-y)/h, (right-left)/w, (bottom-top)/h]})
    return result
