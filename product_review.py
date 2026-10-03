"""Read-only product review. Projection predicts intent, never image recognition."""
import json
import math
from pathlib import Path

import numpy as np

import scene_control
import shared_floor
from interior_style import view_context


def projector(camera):
    eye = np.array(camera['position'], dtype=float)
    forward = np.array(camera['target'], dtype=float) - eye
    forward /= np.linalg.norm(forward)
    right = np.cross([0, 0, 1], forward)
    right /= np.linalg.norm(right)
    up = np.cross(forward, right)
    matrix = np.array([right, up, forward])
    focal = 960 / math.tan(math.radians(camera['horizontal_fov']) / 2)

    def project(point):
        q = matrix @ (np.array(point) - eye)
        if not np.isfinite(q).all() or q[2] <= .05:
            raise ValueError('Review plane crosses or lies behind the camera.')
        # The guide is 1920x1088, cropped by four rows for the saved 1080 image.
        return [float(960 + focal*q[0]/q[2]), float(540 - focal*q[1]/q[2])]
    return project


def plane_inverse(screen, metric):
    """Image-to-plane homography; raw screen aspect ratios are not metric."""
    rows, values = [], []
    for (x, y), (u, v) in zip(screen, metric):
        rows.extend([[x,y,1,0,0,0,-u*x,-u*y], [0,0,0,x,y,1,-v*x,-v*y]])
        values.extend([u, v])
    try:
        h = np.append(np.linalg.solve(rows, values), 1).reshape(3, 3)
    except np.linalg.LinAlgError:
        raise ValueError('The review plane is edge-on; measurements are unavailable.')
    if not np.isfinite(h).all():
        raise ValueError('The review plane is ill-conditioned.')
    return h.tolist()


def confirmed_dimensions(store, item):
    """Field-level review facts are separate from estimated library geometry."""
    path = store.root / 'product-review-facts.json'
    facts = json.loads(path.read_text()) if path.is_file() else {}
    fact = facts.get('references', {}).get(item.get('asset_id'), {})
    if not fact:
        return {}, 'No field-level confirmed dimensions recorded.'
    identity = scene_control.file_identity(store, item['asset_id'])
    if fact.get('sha256') != identity['sha256']:
        raise ValueError('Product dimension evidence refers to a different reference file.')
    dims = fact.get('dimensions', {})
    if any(type(v) not in (int, float) or not math.isfinite(v) or not 0 < v < 20 for v in dims.values()):
        raise ValueError('Invalid confirmed product dimensions.')
    return dims, fact.get('source', 'Recorded product evidence')


def review(store, aid):
    asset = store.asset(aid)
    if asset.get('kind') != 'image' or (asset.get('width'), asset.get('height')) != (1920, 1080):
        raise ValueError('Choose a saved 1920 × 1080 room image.')
    project = store.project(asset['project_id'])
    room = store.room(project['id'], asset['room_id'])
    job = store.db['jobs'].get(asset.get('job_id'), {})
    manifest = job.get('scene_manifest')
    if not manifest:
        raise ValueError('This image has no saved scene evidence for projection.')
    # Fail closed instead of projecting newer geometry onto an older output.
    current = scene_control.assert_scene(store, project, room, manifest)
    identity = scene_control.file_identity(store, aid)
    if asset.get('view_id') and asset.get('view_revision') != room['camera_views'][asset['view_id']]['revision']:
        raise ValueError('The saved camera changed; this overlay cannot use its newer projection.')
    scene = shared_floor.build(store, view_context(room, asset.get('view_id')))
    if not scene.get('camera'):
        raise ValueError('Save a camera before measuring product placement.')
    project_point = projector(scene['camera'])
    b = scene['bounds']

    def xy(x, y):
        return np.array([(x-b[0])/(b[2]-b[0])*scene['width'],
                         (y-b[1])/(b[3]-b[1])*scene['depth']])

    objects = []
    included = {p.get('object_key') for p in scene['products']}
    for item in room.get('block_layout', {}).get('items', []):
        kind = 'artwork' if item.get('preset_id', '').startswith('painting-') else 'pendant' if item.get('preset_id') == 'pendant-light' else None
        if not kind or room['id']+':'+item['id'] not in included:
            continue
        dims, provenance = confirmed_dimensions(store, item)
        row = {'id': item['id'], 'kind': kind, 'label': item['label'],
               'reference_id': item.get('asset_id'), 'dimensions': dims, 'source': provenance,
               'assumptions': [], 'available': False}
        required = ('width_m', 'height_m') if kind == 'artwork' else ('diameter_m',)
        if not all(k in dims for k in required):
            row['reason'] = 'Confirmed '+', '.join(required)+' needed. Proxy dimensions are not product evidence.'
            objects.append(row)
            continue
        center = xy(item['x'], item['y'])
        z = item.get('elevation_m', 0)
        try:
            if kind == 'artwork':
                w, h = dims['width_m'], dims['height_m']
                angle = math.radians(item['angle'])
                axis = np.array([math.cos(angle), math.sin(angle)])
                world = [[*(center+sign*axis*w/2), height] for sign,height in [(-1,z+h),(1,z+h),(1,z),(-1,z)]]
                outline = [project_point(p) for p in world]
                # Label image-left corners consistently, independent of wall orientation.
                if outline[0][0] > outline[1][0]:
                    outline = [outline[i] for i in (1,0,3,2)]
                row.update(outline=outline, image_to_plane=plane_inverse(outline, [[0,0],[w,0],[w,h],[0,h]]))
                row['assumptions'] = [f'Saved bottom elevation {z:g} m and wall orientation are placement assumptions.',
                    'Projection uses the artwork centre plane; mounting depth/frame thickness are unknown.']
            else:
                radius = dims['diameter_m']/2
                metric = [[-radius,-radius],[radius,-radius],[radius,radius],[-radius,radius]]
                screen = [project_point([*(center+q),z]) for q in np.array(metric)]
                ring = [project_point([*(center+radius*np.array([math.cos(t),math.sin(t)])),z]) for t in np.linspace(0,2*math.pi,65)]
                row.update(outline=ring, image_to_plane=plane_inverse(screen, metric))
                row['assumptions'] = [f'Diameter ring uses saved proxy bottom elevation {z:g} m and a horizontal circular rim.',
                    'Shade height: unknown. Suspension length: unknown. Neither is validated.',
                    'A different actual rim height changes the inferred diameter.']
            row['available'] = True
        except ValueError as exc:
            row['reason'] = str(exc)
        objects.append(row)
    # Unoccluded visibility is not assumed. Reviewer chooses recognizable corners.
    anchors, edges = [], []
    for line in scene['lines']:
        if line['kind'] != 'wall':
            continue
        for z in (0, scene['height']):
            points = []
            for v in line['points']:
                try:
                    q = project_point([*xy(*v), z])
                except ValueError:
                    continue
                if 0 <= q[0] <= 1920 and 0 <= q[1] <= 1080:
                    points.append(q)
                    if not any(math.dist(q,a['point']) < 8 for a in anchors):
                        anchors.append({'id':str(len(anchors)+1),'point':q,'label':'Wall '+('top' if z else 'base')+' corner'})
            if len(points) == 2:
                edges.append(points)
    key = scene_control.digest([identity,current['fingerprint'],objects,scene['camera']])
    return {'asset_id':aid,'image_sha256':identity['sha256'],'scene_fingerprint':current['fingerprint'],
            'review_key':key,'image_url':'/media/'+aid,'width':1920,'height':1080,
            'camera':scene['camera'],'calibrated':scene['calibrated'], 'objects':objects,
            'anchors':anchors,'edges':edges,
            'limitations':['Expected outlines describe intended scene placement, not detected products.',
                'The generated image may not follow the saved camera. All metric results are conditional on alignment and plane depth.',
                'Projected model edges may be hidden or differ from the generated architecture. Choose only recognizable matching landmarks.',
                'No automatic product recognition, resizing, approval or inference is performed.']}
