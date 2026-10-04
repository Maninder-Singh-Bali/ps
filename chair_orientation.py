"""Conservative facing inference for NEW axis-aligned chair/table proposals.

The chair recipe's back is local -Y, so its front is +Y: east=270°,
west=90°, north=180°, south=0° in source-image coordinates. This is a
layout inference, not recognition of a backrest in the source image.
Never run this over an existing saved arrangement automatically.
"""
import copy


def orient_proposals(items, plan):
    result = copy.deepcopy(items)
    W, H = plan['width'], plan['height']
    tables = [v for v in items if v.get('kind') == 'table' and not v.get('angle', 0) % 180]
    for chair in result:
        if chair.get('kind') != 'chair' or chair.get('angle', 0) != 0:
            continue
        cw, cd = chair['width'] * W, chair['depth'] * H
        candidates = []
        for table in tables:
            dx, dy = (table['x'] - chair['x']) * W, (table['y'] - chair['y']) * H
            hw, hd = table['width'] * W / 2, table['depth'] * H / 2
            gx, gy = abs(dx) - hw, abs(dy) - hd
            if gx >= 0 and abs(dy) <= hd:
                gap, angle = gx - cw / 2, 270 if dx > 0 else 90
            elif gy >= 0 and abs(dx) <= hw:
                gap, angle = gy - cd / 2, 0 if dy > 0 else 180
            else:
                continue
            if -.15 * max(cw, cd) <= gap <= 1.5 * max(cw, cd):
                candidates.append((max(0, gap), angle, table['id']))
        candidates.sort()
        if not candidates or (len(candidates) > 1 and candidates[1][0] - candidates[0][0] < .5 * max(cw, cd)):
            continue
        chair['angle'] = candidates[0][1]
        # Input boxes are image-axis aligned; retain their physical footprint.
        if chair['angle'] in (90, 270):
            chair['width'], chair['depth'] = cd / W, cw / H
        chair['prompt'] = (chair.get('prompt', '') + ' Facing inferred toward nearby table; verify against source.').strip()
    return result
