"""Measured ComfyUI sampling progress. Time estimates never advance the bar."""
import copy
import hashlib
import json
import math
import statistics


def sampling_plan(graph):
    plan = {}
    for key, node in graph.items():
        if node['class_type'] not in ('SamplerCustomAdvanced', 'SamplerCustom', 'KSampler', 'KSamplerAdvanced'):
            continue
        inputs = node['inputs']
        steps = inputs.get('steps')
        if not isinstance(steps, int):
            link = inputs.get('sigmas', [])
            scheduler = graph.get(str(link[0]), {}) if isinstance(link, list) and link else {}
            values = scheduler.get('inputs', {})
            steps = values.get('steps')
            if scheduler.get('class_type') == 'ManualSigmas':
                steps = len([s for s in values.get('sigmas', '').split(',') if s.strip()]) - 1
            elif scheduler.get('class_type') == 'SplitSigmasDenoise':
                parent=graph.get(str(values.get('sigmas',[None])[0]),{}).get('inputs',{})
                if isinstance(parent.get('steps'),int):steps=round(parent['steps']*values['denoise'])
        if isinstance(steps, int) and steps > 0:
            plan[str(key)] = {'total': steps, 'done': 0, 'observations': []}
    return plan


def initialize(job, graph, previous=()):
    nodes = sampling_plan(graph)
    # Match model, resolution, duration, sampling schedule and reference count;
    # exclude prompts, filenames and seeds from timing comparisons.
    traits = []
    for n in graph.values():
        traits.append([n['class_type'], {k: v for k, v in n['inputs'].items()
            if k in ('width', 'height', 'length', 'steps', 'sigmas', 'ckpt_name',
                     'unet_name', 'vae_name', 'clip_name', 'sampler_name', 'denoise') and not isinstance(v, list)}])
    profile = hashlib.sha256(json.dumps(traits, sort_keys=True).encode()).hexdigest()
    tails = [j['finished'] - j['render_tracking']['sampling_finished_at'] for j in previous
             if j.get('status') == 'completed' and j.get('render_tracking', {}).get('profile') == profile
             and j['render_tracking'].get('sampling_finished_at') and j.get('finished')]
    tails = [x for x in tails[-8:] if x > 0]
    return {'render_tracking': {'nodes': nodes, 'profile': profile, 'phase': 'preparing',
                               'tail_estimate': statistics.median(tails) if tails else None},
            'progress': 0 if nodes else None, 'progress_scope': 'sampling', 'eta': None}


def measured_fields(tracking, at):
    nodes = tracking['nodes']
    total = sum(n['total'] for n in nodes.values())
    done = sum(n['done'] for n in nodes.values())
    fields = {'render_tracking': tracking, 'progress': round(100 * done / total, 1) if total else None,
              'progress_scope': 'sampling', 'steps': [done, total], 'eta': None}
    if total and done == total and not tracking.get('sampling_finished_at'):
        tracking['sampling_finished_at'] = at
    tail = tracking.get('tail_estimate')
    if total and done == total:
        if tail is not None:
            seconds = tail - (at - tracking['sampling_finished_at'])
            if seconds > 0:
                fields['eta'] = {'seconds': seconds, 'at': at, 'scope': 'total', 'basis': 'recent matching renders'}
        return fields
    current = nodes.get(tracking.get('node'))
    if current and tracking['phase'] == 'sampling':
        observations = current['observations']
        rates = [(b[1] - a[1]) / (b[0] - a[0]) for a, b in zip(observations, observations[1:])
                 if b[0] > a[0] and b[1] > a[1]]
        # Two measured steps avoid counting model loading as sampling speed.
        if rates:
            rate = statistics.median(rates[-6:])
            seconds = rate * (total - done)
            fields['eta'] = {'seconds': seconds + (tail or 0), 'at': at,
                             'scope': 'total' if tail is not None else 'sampling',
                             'basis': 'measured step speed' + (' + recent finishing time' if tail is not None else '')}
    return fields


def event_fields(job, event, graph, at):
    data = event.get('data', {})
    if job.get('status') in ('completed', 'failed', 'cancelled'):
        return {}
    if data.get('prompt_id') != job.get('prompt_id') or not job.get('prompt_id'):
        return {}
    tracking = copy.deepcopy(job.get('render_tracking') or initialize(job, graph)['render_tracking'])
    nodes = tracking['nodes']
    typ = event.get('type')
    node_id = str(data.get('node') or tracking.get('node') or '')
    kind = graph.get(node_id, {}).get('class_type', '')
    if typ == 'executing' and data.get('node') is not None:
        tracking.update(node=node_id, last_event=at)
        if node_id in nodes:
            tracking['phase'] = 'sampling'
            stage = 'Rendering · waiting for the first step'
        elif 'Decode' in kind:
            tracking['phase'] = 'finishing'
            stage = 'Decoding full-resolution output'
        elif 'Save' in kind or kind == 'CreateVideo':
            tracking['phase'] = 'finishing'
            stage = 'Saving output'
        else:
            stage = 'Preparing model and references' if tracking['phase'] == 'preparing' else 'Finishing output'
        return {**measured_fields(tracking, at), 'stage': stage, 'node_type': kind}
    if typ == 'execution_cached':
        for key in data.get('nodes', []):
            if str(key) in nodes:
                nodes[str(key)]['done'] = nodes[str(key)]['total']
        return measured_fields(tracking, at)
    if typ != 'progress' or node_id not in nodes:
        return {}
    try:
        value, maximum = float(data['value']), float(data['max'])
        if not math.isfinite(value) or not math.isfinite(maximum) or maximum <= 0:
            return {}
    except (KeyError, ValueError, TypeError):
        return {}
    current = nodes[node_id]
    # Do not let a decode/encode progress event or late duplicate reset the bar.
    if maximum != current['total'] or value <= current['done']:
        return {}
    current['done'] = min(current['total'], int(value))
    current['observations'].append([current['done'], at])
    current['observations'] = current['observations'][-8:]
    tracking.update(node=node_id, phase='sampling', last_event=at)
    fields = measured_fields(tracking, at)
    done, total = fields['steps']
    fields['stage'] = f'Rendering · step {done} of {total}' if done < total else 'Rendering complete · finishing output'
    return fields
