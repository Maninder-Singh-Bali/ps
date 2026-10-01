"""Source-bound identities. A candidate's list position is never its identity."""
import copy
import hashlib
import json


def identity(report, item, category):
    points = item.get('geometry', {}).get('points', item.get('points', []))
    # Reversing a path does not change the physical evidence. Changed sampling,
    # thickness or analysis coordinates conservatively requires renewed review.
    points = [[round(float(v), 5) for v in p] for p in points]
    points = min(points, points[::-1])
    evidence = [report.get('source_sha256'), report.get('analysis_size'), category,
                points, item.get('width_px'), item.get('width_range_px')]
    return hashlib.sha256(json.dumps(evidence, sort_keys=True).encode()).hexdigest()


def identified(report):
    result = copy.deepcopy(report)
    remap = {}
    for category in ('walls', 'uncertain_spans', 'openings', 'gap_repairs'):
        for item in result.get(category, []):
            token = identity(result, item, category)
            key = category + '-' + token[:24]
            remap[item['id']] = key
            item.update(id=key, source_identity=token)
    for category in ('openings', 'gap_repairs'):
        for item in result.get(category, []):
            item['wall_ids'] = [remap.get(key, key) for key in item.get('wall_ids', [])]
    return result


def indexed(report):
    return {item['id']: (item, identity(report, item, category))
            for category in ('walls', 'uncertain_spans', 'openings')
            for item in report.get(category, [])}


def correction_for(plan, key):
    correction = plan.get('raster_corrections', {}).get(key, {})
    if not correction.get('source_identity'):return {}
    report=plan.get('raster_geometry') or {}
    # Review rendering asks once per candidate. Do not rehash the entire report
    # for each path, especially when there are no saved corrections yet.
    for category in ('walls','uncertain_spans','openings'):
        item=next((v for v in report.get(category,[]) if v['id']==key),None)
        if item is not None:
            return correction if correction['source_identity']==identity(report,item,category) else {}
    return {}


def reconcile(plan, report):
    """Transfer only one-to-one exact source evidence; archive changed evidence."""
    previous = plan.get('raster_geometry') or {}
    old, new = indexed(previous), indexed(report)
    reverse = {}
    old_counts = {}
    for _, token in old.values():
        old_counts[token] = old_counts.get(token, 0) + 1
    for key, (_, token) in new.items():
        reverse.setdefault(token, []).append(key)
    kept, orphaned = {}, copy.deepcopy(plan.get('raster_orphaned_corrections', []))
    for key, correction in plan.get('raster_corrections', {}).items():
        token = old.get(key, (None, None))[1]
        matches = reverse.get(token, [])
        bound = correction.get('source_identity')
        if token and (bound is None or bound == token) and len(matches) == 1 and old_counts[token] == 1:
            kept[matches[0]] = {**copy.deepcopy(correction), 'source_identity': token}
        else:
            orphaned.append({'id': key, 'correction': copy.deepcopy(correction),
                             'source_sha256': previous.get('source_sha256'),
                             'reason': 'Source geometry changed; classification was not transferred.'})
    return kept, orphaned
