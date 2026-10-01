"""Owned-job cancellation and retry without interrupting unrelated local work."""
from store import now


def cancel(engine, job):
    if job['status'] not in ('queued','waiting','running'):
        raise ValueError('This activity has already stopped.')
    if job.get('submission_intent') and not job.get('prompt_id'):
        raise ValueError('Submission acknowledgement is missing. Recover this activity before cancelling it.')
    prompt = job.get('prompt_id')
    if prompt:
        queue = engine.get('/queue')
        running = queue.get('queue_running', [])
        if any(row[1] == prompt for row in running):
            if len(running) != 1:
                raise ValueError('Another local render is active. Cancellation was withheld to protect it.')
            engine.post('/interrupt', {})
        elif any(row[1] == prompt for row in queue.get('queue_pending', [])):
            engine.post('/queue', {'delete': [prompt]})
    elif job['status'] == 'running' and job['kind'] not in ('vision_study','raster_reconstruction','component_download'):
        raise ValueError('This preparation step is finishing. Your source files remain saved.')
    return engine.store.update_job(job['id'], status='cancelled', stage='Cancelled; saved inputs retained', finished=now(), progress=None)


def recover(engine, job):
    if job['status'] not in ('failed','cancelled'):
        raise ValueError('This activity is still active or already complete.')
    if job.get('submission_intent') and not job.get('prompt_id'):
        # Comfy returns the submitted extra_data in prompt records. Do not guess.
        matches=[]
        queue=engine.get('/queue')
        records=queue.get('queue_running',[])+queue.get('queue_pending',[])
        records += [entry.get('prompt',[]) for entry in engine.get('/history').values()]
        for row in records:
            if len(row)>3 and isinstance(row[3],dict) and row[3].get('pixeloid_job_id')==job['id']:
                matches.append(row[1])
        matches=list(dict.fromkeys(matches))
        if len(matches)!=1:
            raise ValueError('The renderer cannot identify this interrupted submission uniquely. Inputs and output files are preserved; no duplicate was submitted.')
        job['prompt_id']=matches[0]
    if job['status']=='cancelled' and job.get('prompt_id'):
        raise ValueError('This render was cancelled. Generate a new version from Images & Video; it will use the current saved inputs.')
    return engine.store.update_job(job['id'],status='queued',stage='Resuming saved activity',error=None,finished=None)
