"""Opt-in forensic capture for the unchanged revision-2 preview; no inference here."""
import copy, hashlib, json, re
from pathlib import Path
PROFILE = 'ltx-preview-capture-v1'
FILES = ('__init__.py', 'runtime_sources.json')

def capability(root):
    base=Path(root)/'capture_extension/pixeloid_preview_capture'
    hashes={name:hashlib.sha256((base/name).read_bytes()).hexdigest() for name in FILES}
    fingerprint=hashlib.sha256(json.dumps(hashes,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    return {'profile':PROFILE,'fingerprint':fingerprint,'large_artifacts':'PC only'}

def check(profile,preset):
    if profile is not None and (profile!=PROFILE or preset!='ltx-preview-768x432-2s-v1'):
        raise ValueError('Capture is supported only for the fixed LTX preview.')

def missing(root,specs):
    required=('PixeloidCaptureConditioning','PixeloidCaptureLatent','PixeloidCaptureRGB','PixeloidCaptureFinish')
    absent=[name for name in required if name not in specs]
    choices=specs.get(required[0],{}).get('input',{}).get('required',{}).get('fingerprint',[[]])[0]
    if not isinstance(choices,list) or capability(root)['fingerprint'] not in choices:absent.append('capture extension fingerprint')
    return absent

def instrument(root,graph,job_id,profile):
    check(profile,'ltx-preview-768x432-2s-v1')
    if profile!=PROFILE or not re.fullmatch('[a-f0-9]{16,64}',str(job_id)):raise ValueError('Invalid capture identity.')
    g=copy.deepcopy(graph)
    g['38']={'class_type':'PixeloidCaptureConditioning','inputs':{'image':['10',0],'job_id':job_id,'fingerprint':capability(root)['fingerprint']}}
    g['12']['inputs']['image']=['38',0];g['35']['inputs']['image']=['38',0]
    g['39']={'class_type':'PixeloidCaptureLatent','inputs':{'samples':['36',2],'job_id':job_id}}
    g['29']['inputs']['samples']=['39',0]
    g['40']={'class_type':'PixeloidCaptureRGB','inputs':{'images':['34',0],'job_id':job_id}}
    g['31']['inputs']['images']=['40',0]
    g['42']={'class_type':'PixeloidCaptureFinish','inputs':{'video':['32',0],'job_id':job_id}}
    return g

def evidence(history,job_id):
    rows=history.get('outputs',{}).get('42',{}).get('pixeloid_capture',[])
    if len(rows)!=1 or rows[0].get('job_id')!=job_id or rows[0].get('profile')!=PROFILE or rows[0].get('state')!='complete':
        raise ValueError('Capture manifest missing or incomplete; saved PC files retained. Do not rerender.')
    return rows[0]
