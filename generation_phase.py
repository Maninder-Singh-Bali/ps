"""Project-scoped generation pause. Only an explicitly authorised new phase may replace it.
No HTTP/UI reset or resume operation is exposed; existing scene/review data is unrelated.
"""
RENDER_KINDS = frozenset(('image', 'video', 'reference'))
MESSAGE = 'Generation paused — current experiment allowance exhausted.'

class GenerationPaused(ValueError):
    pass

def assert_submission(store, project_id, kind):
    phase = store.project(project_id).get('generation_phase', {})
    if kind in RENDER_KINDS:
        if phase.get('status') == 'paused':raise GenerationPaused(MESSAGE)
        if 'allowed_jobs' in phase:
            allowance=phase.get('allowances',{}).get(kind,{})
            if kind not in phase['allowed_jobs'] or allowance.get('used',0)>=allowance.get('limit',0):
                raise GenerationPaused('No remaining authorised '+kind+' attempt in this phase.')
        if phase.get('allowed_job') and kind != phase['allowed_job']['kind']:
            raise GenerationPaused('This phase authorises only its fixed technical video test.')

def admit(store, job):
    """Called under Store.lock; reserve the attempt in the same save as the job."""
    phase = store.project(job['project_id']).get('generation_phase', {})
    if 'allowed_jobs' in phase and job['kind'] in RENDER_KINDS:
        spec=phase['allowed_jobs'].get(job['kind'])
        if not spec or not bounded_matches(job,spec):raise GenerationPaused('Job differs from the authorised project, room, camera or scene.')
        allowance=phase.get('allowances',{}).get(job['kind'],{})
        if allowance.get('used',0)>=allowance.get('limit',0):raise GenerationPaused(MESSAGE)
        if job['kind']=='video':
            image=store.asset(job.get('source_image_id'))
            parent=store.db['jobs'].get(image.get('job_id'),{})
            if parent.get('kind')!='image' or parent.get('generation_phase_id')!=phase['id'] or parent.get('status')!='completed' or parent.get('project_id')!=job['project_id'] or parent.get('room_id')!=job['room_id']:
                raise GenerationPaused('Video must use the completed image from this same bounded test phase.')
        allowance['used']+=1
        phase.setdefault('continuing_job_ids',[]).append(job['id'])
        job.update(generation_phase_id=phase['id'],single_submission=True,approval_scope='technical_preview_only')
        if all(phase['allowances'].get(k,{}).get('used',0)>=phase['allowances'].get(k,{}).get('limit',0) for k in phase['allowed_jobs']):
            phase.update(status='paused',reason='All explicitly authorised attempts admitted')
        return
    spec = phase.get('allowed_job')
    if job.get('video_capture') and (not spec or spec.get('video_capture')!=job['video_capture']):
        raise GenerationPaused('Capture requires an explicitly authorised matching one-attempt phase.')
    if not spec or job['kind'] not in RENDER_KINDS:return
    if any(job.get(k) != v for k,v in spec.items()):
        raise GenerationPaused('Job differs from the explicitly authorised technical preview.')
    allowance = phase['allowances']['video_test']
    if allowance['used'] >= allowance['limit']:raise GenerationPaused(MESSAGE)
    allowance['used'] += 1
    phase.update(status='paused', reason='single authorised video attempt admitted', continuing_job_ids=[job['id']])
    job.update(generation_phase_id=phase['id'], single_submission=True, approval_scope='technical_preview_only')

def assert_dispatch(store, job):
    phase = store.project(job['project_id']).get('generation_phase', {})
    if 'allowed_jobs' in phase and job['kind'] in RENDER_KINDS:
        spec=phase['allowed_jobs'].get(job['kind'])
        if job.get('generation_phase_id')!=phase.get('id') or job['id'] not in phase.get('continuing_job_ids',[]) or not spec or not bounded_matches(job,spec):
            raise GenerationPaused('Only this phase’s admitted fixed attempts may continue.')
    if job.get('video_capture') and phase.get('allowed_job',{}).get('video_capture')!=job['video_capture']:
        raise GenerationPaused('Capture requires an explicitly authorised matching one-attempt phase.')
    if phase.get('allowed_job') and job['kind'] in RENDER_KINDS:
        if job.get('generation_phase_id') != phase.get('id') or job['id'] not in phase.get('continuing_job_ids', []) or any(job.get(k) != v for k,v in phase['allowed_job'].items()):
            raise GenerationPaused('Only the admitted technical preview may continue.')
    if job['kind'] in RENDER_KINDS and phase.get('status') == 'paused' and job['id'] not in phase.get('continuing_job_ids', []):
        raise GenerationPaused(MESSAGE)


def bounded_matches(job, spec):
    """Exact scene identity; no revision aliases or arbitrary capture overrides."""
    return not job.get('video_capture') and all(
        job.get('scene_ticket',{}).get('fingerprint')==v if k=='scene_fingerprint' else job.get(k)==v
        for k,v in spec.items())
