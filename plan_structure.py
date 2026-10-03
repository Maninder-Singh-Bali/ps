"""Reviewed PDF faces → editable structure. No semantic guessing from colour.

A caller must nominate the two source faces. Unequal spans are intersected,
never extended across a doorway. Points use the same rotated-page mapping as
PDF import; all source identifiers remain evidence, not structural labels.
"""
import math


def page_point(page, point, width, height):
    q = point * page.rotation_matrix
    return [q.x / page.rect.width * width, q.y / page.rect.height * height]


def face_pair(a, b, feature_id, source_ids=()):
    """Pair two reviewed axis-aligned faces, retaining only their overlap."""
    axis = 0 if abs(a[0][1] - a[1][1]) < .01 else 1
    cross = 1 - axis
    if any(abs(p[0][cross] - p[1][cross]) > .01 for p in (a, b)):
        raise ValueError('Choose two parallel straight wall faces.')
    lo = max(min(p[0][axis], p[1][axis]) for p in (a, b))
    hi = min(max(p[0][axis], p[1][axis]) for p in (a, b))
    thickness = abs(a[0][cross] - b[0][cross])
    if hi - lo < .2 or not .1 <= thickness <= 50:
        raise ValueError('Wall faces need a shared span and a valid thickness.')
    centre = (a[0][cross] + b[0][cross]) / 2
    points = [[lo, centre], [hi, centre]] if axis == 0 else [[centre, lo], [centre, hi]]
    return dict(id=feature_id, kind='wall', points=points, thickness=thickness, flip=False,
                evidence={'method':'reviewed PDF face pair', 'source_ids':list(source_ids),
                          'source_points':points, 'source_thickness':thickness})


def dimension_scale(a, b, metres):
    span = math.dist(a, b)
    if span <= 0 or not math.isfinite(metres) or metres <= 0:
        raise ValueError('Use actual dimension witness endpoints and a positive stated length.')
    return metres / span
