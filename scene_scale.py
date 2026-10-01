"""Shared metric scale. Estimates never masquerade as surveyed dimensions."""
import math
from statistics import median

HUMAN_HEIGHT = 5.5 * .3048
DEFAULT_WALL_HEIGHT = 3.0


def positive(value):
    return type(value) in (int, float) and math.isfinite(value) and value > 0


def clean_model(value):
    if not isinstance(value, dict):
        raise ValueError('Invalid model scale.')
    def number(key, default, low, high):
        v = value.get(key, default)
        if type(v) not in (int, float) or not math.isfinite(v) or not low <= v <= high:
            raise ValueError('Invalid ' + key.replace('_', ' ') + '.')
        return float(v)
    heights = value.get('wall_heights', {})
    if not isinstance(heights, dict) or len(heights) > 100:
        raise ValueError('Invalid floor heights.')
    for floor, height in heights.items():
        if not isinstance(floor, str) or len(floor) > 120 or type(height) not in (int, float) or not math.isfinite(height) or not 2.4 <= height <= 6:
            raise ValueError('Wall height must be between 2.4 and 6 m.')
    result = dict(wall_heights=heights.copy(), human_height_m=number('human_height_m', HUMAN_HEIGHT, 1, 2.4), vertical_fov=number('vertical_fov', 60, 40, 85))
    if 'metres_per_pixel' in value:
        result['metres_per_pixel'] = number('metres_per_pixel', .1, .00001, 10)
        result['scale_source'] = str(value.get('scale_source', 'Manual scale'))[:160]
    return result


def settings(plan, floor):
    value = plan.get('drawing', {}).get('site', {}).get('model', {})
    return {**value, 'wall_height_m': value.get('wall_heights', {}).get(floor, DEFAULT_WALL_HEIGHT),
            'human_height_m': value.get('human_height_m', HUMAN_HEIGHT),
            'eye_height_m': value.get('human_height_m', HUMAN_HEIGHT) - .11,
            'vertical_fov': value.get('vertical_fov', 60)}


def estimate(store, plan):
    """Use one uniform scale across the drawing, prioritizing reviewed sizes.

    Ignore conflicting retailer variants and incompatible footprint ratios.
    Use stable library dimensions as an explicitly estimated fallback.
    """
    saved = plan.get('drawing', {}).get('site', {}).get('model', {})
    if positive(saved.get('metres_per_pixel')):
        return saved['metres_per_pixel'], saved.get('scale_source', 'Manual scale')
    native = plan.get('plan_source', {}).get('metres_per_pixel')
    if positive(native):
        return native, 'Declared CAD units · verify a known length'
    project = store.project(plan['project_id'])
    confirmed, linked, typical = [], [], []
    typical_sizes = {'chair': (.55, .55), 'armchair': (.85, .85), 'bed-single': (.95, 2),
                     'bed-double': (1.5, 2), 'bed-queen': (1.6, 2), 'bed-king': (1.8, 2),
                     'cooker': (.6, .6), 'washer': (.6, .65), 'dishwasher': (.6, .6)}
    def candidate(item, w, d, into):
        if not all(positive(v) for v in (w,d,item.get('width'),item.get('depth'))):return
        px, py = item['width'] * plan['width'], item['depth'] * plan['height']
        if item.get('chair_modules'):
            module=item['chair_modules']
            if not all(positive(module.get(k)) for k in ('width','depth')):return
            px, py = module['width'] * plan['width'], module['depth'] * plan['height']
        if not positive(px) or not positive(py):return
        ratios = [w / px, d / py]
        if min(ratios) > 0 and max(ratios) / min(ratios) <= 1.3:
            into.append(math.sqrt(ratios[0] * ratios[1]))
    for room in project.get('rooms', []):
        if room.get('plan_id') != plan['id']:
            continue
        for item in room.get('block_layout', {}).get('items', []):
            size = item.get('physical_size')
            if isinstance(size,dict) and positive(size.get('width')) and positive(size.get('depth')):
                factor=.3048 if size.get('unit')=='ft' else 1
                candidate(item, size['width']*factor, size['depth']*factor, confirmed)
                continue
            asset = store.db.get('assets', {}).get(item.get('asset_id'), {})
            product = asset.get('source_product') or {}
            dims = product.get('dimensions_m') or {}
            if dims and not any('discrepancy' in str(n).lower() for n in product.get('dimension_notes', [])):
                def metres(entry):return entry.get('metres') if isinstance(entry,dict) else None
                w = metres(dims.get('length', dims.get('width')))
                d = metres(dims.get('depth', dims.get('width') if 'length' in dims else None))
                if w and d:
                    candidate(item, w, d, linked)
            if item.get('preset_id') in typical_sizes:
                candidate(item, *typical_sizes[item['preset_id']], typical)
    for values, source in [(confirmed, 'Estimated from reviewed furniture'), (linked, 'Estimated from linked products'), (typical, 'Estimated from furniture sizes')]:
        if values:
            return median(values), source
    return 10 / plan['width'], 'Uncalibrated estimate'


def dimensions(store, room):
    plan = store.asset(room['plan_id'])
    mpp, source = estimate(store, plan)
    return {'width_m': room['bbox'][2] * plan['width'] * mpp,
            'depth_m': room['bbox'][3] * plan['height'] * mpp,
            'metres_per_pixel': mpp, 'method': source, 'estimated': True}
