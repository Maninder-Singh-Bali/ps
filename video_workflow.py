"""Fixed installed LTX presets. Conditioning does not enforce a camera path."""
import copy,json
from pathlib import Path

REVISION = 2
NATIVE = 'ltx-native-1080p-v1'
PREVIEW = 'ltx-preview-768x432-2s-v1'
DURATIONS = (5, 8)  # legacy/native callers
MOTIONS = ('still', 'push', 'slide')
PRESETS = {
    NATIVE: {'label':'Native 1080p','durations':[5,8],'motions':list(MOTIONS),
        'sampling':[1920,1088],'output':[1920,1080],'conditioning':[1920,1080],
        'pad_vertical':4,'decode':{'tile_size':768,'overlap':128,'temporal_size':32,'temporal_overlap':8},'fixed_seed':None},
    PREVIEW: {'label':'Preview — 768 × 432 — 2 seconds','durations':[2],'motions':['still'],
        'sampling':[768,448],'output':[768,432],'conditioning':[768,432],
        'pad_vertical':8,'decode':{'tile_size':512,'overlap':64,'temporal_size':16,'temporal_overlap':4},'fixed_seed':2909202661},
}

def settings(preset=NATIVE, seconds=None, motion='still'):
    if not isinstance(preset,str) or preset not in PRESETS:raise ValueError('Unknown video preset.')
    p=copy.deepcopy(PRESETS[preset])
    if seconds is None:seconds=p['durations'][0]
    if type(seconds) is not int or seconds not in p['durations'] or motion not in p['motions']:
        raise ValueError('Choose a supported duration and camera movement for this video preset.')
    p.update(preset=preset,duration=seconds,motion=motion,fps=24,frames=seconds*24,requested_frames=seconds*24+1)
    return p

def provenance(preset=NATIVE, seconds=None, motion='still'):
    p=settings(preset,seconds,motion);w,h=p['sampling'];ow,oh=p['output'];pad=p['pad_vertical']
    return {'preset_id':preset,'preset_label':p['label'],'video_workflow_revision':REVISION,
        'sampling_width':w,'sampling_height':h,'output_width':ow,'output_height':oh,
        'source_dimensions':[1920,1080],'conditioning_dimensions':p['conditioning'],
        'source_conditioning_may_be_resized':preset==PREVIEW,'conditioning_resize':{'method':'lanczos','crop':'disabled'} if preset==PREVIEW else None,
        'padding':{'left':0,'right':0,'top':pad,'bottom':pad,'fill':0.5},
        'output_crop':{'x':0,'y':pad,'width':ow,'height':oh},'crop_top':pad,'crop_bottom':pad,
        'output_upscaler':False,'native_1080p':preset==NATIVE,'protected_composite':False,
        'requested_frames':p['requested_frames'],'output_frames':p['frames'],'fps':24,'duration':p['duration'],
        'retained_frame_indices':[0,p['frames']-1],'retained_frame_indices_inclusive':True,
        'guided_endpoint_index':p['frames'] if motion=='still' else None,'guided_endpoint_in_output':False,
        'guide_tokens_cropped_before_decode':motion=='still','decoder':p['decode'],
        'workflow':'workflow.api.json','note':'Frame indices describe the graph selection, not proof of visual alignment to conditioning.'}

def build(root, image, seconds, motion, seed, prompt, prefix, preset=NATIVE):
    p=settings(preset,seconds,motion)
    if type(seed) is not int or not 0 <= seed <= 2**64-1:raise ValueError('Invalid video seed.')
    if p['fixed_seed'] is not None and seed!=p['fixed_seed']:raise ValueError('The preview preset uses its fixed reviewed seed.')
    if not isinstance(prompt,str) or not 0<len(prompt)<=16000:raise ValueError('Invalid video prompt.')
    g=json.loads((Path(root)/'templates/ltx.json').read_text(encoding='utf-8-sig'))
    frames=p['frames']
    g['8']['inputs']['image']=image
    g['11']['inputs'].update(width=p['sampling'][0],height=p['sampling'][1],length=frames+1)
    g['13']['inputs']['frames_number']=frames+1
    g['34']['inputs']['length']=frames
    g['15']['inputs']['noise_seed']=seed
    image_link=['8',0]
    if preset==PREVIEW:
        g['37']={'class_type':'ImageScale','inputs':{'image':image_link,'upscale_method':'lanczos','width':768,'height':432,'crop':'disabled'}}
        image_link=['37',0]
    pad=p['pad_vertical']
    g['9']={'class_type':'ImagePadForOutpaint','inputs':{'image':image_link,'left':0,'right':0,'top':pad,'bottom':pad,'feathering':0}}
    g['12']['inputs']['strength']=1.0
    g['29']['inputs'].update(p['decode'])
    g['33']['inputs'].update(width=p['output'][0],height=p['output'][1],y=pad)
    if motion=='still':
        g['35']={'class_type':'LTXVAddGuide','inputs':{'positive':['7',0],'negative':['7',1],'vae':['3',0],'latent':['12',0],'image':['10',0],'frame_idx':frames,'strength':1.0}}
        g['14']['inputs']['video_latent']=['35',2]
        g['16']['inputs'].update(positive=['35',0],negative=['35',1])
        g['36']={'class_type':'LTXVCropGuides','inputs':{'positive':['35',0],'negative':['35',1],'latent':['20',0]}}
        g['29']['inputs']['samples']=['36',2]
    g['5']['inputs']['text']=prompt
    g['32']['inputs']['filename_prefix']=prefix
    return g
