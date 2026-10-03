"""Versioned, deliberately narrow image/video contract. No remote shell or paths."""
import copy, hashlib, json, re
from pathlib import Path

VERSION = 1
ID = re.compile(r'^[a-f0-9]{16,64}$')
EXTRA = {'ImagePadForOutpaint','VAEEncode','ImageCrop','SolidMask','FeatherMask',
         'MaskComposite','SetLatentNoiseMask','ImageCompositeMasked','ReferenceLatent',
         'SplitSigmasDenoise','ImageToMask','CropMask','ImageScaleToTotalPixels'}

def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()

def contract(root):
    from video_workflow import REVISION,PRESETS
    from video_capture import capability
    graph=json.loads((Path(root)/'templates/flux.json').read_text(encoding='utf-8-sig'))
    return {'protocol':VERSION,'workflow':digest(graph),'kinds':['image','reference','video'],
            'video':True,'video_workflow_revision':REVISION,'video_presets':list(PRESETS),'video_workflow':video_contract(root),'video_capture':capability(root),'max_input_bytes':32*1024*1024}

def video_contract(root):
    from video_workflow import REVISION,PRESETS
    return digest({'revision':REVISION,'presets':PRESETS,'template':json.loads((Path(root)/'templates/ltx.json').read_text(encoding='utf-8-sig'))})

def validate_video(root,body,assets):
    from video_workflow import build,NATIVE,REVISION
    if body.get('video_workflow')!=video_contract(root) or body.get('video_workflow_revision')!=REVISION:raise ValueError('Video workflow version mismatch.')
    if body.get('output_node')!='32':raise ValueError('Unsupported video output node.')
    g=body.get('graph');settings=body.get('video_settings',{})
    if not isinstance(g,dict) or not isinstance(settings,dict) or set(settings)-{'preset','duration','motion','capture'}:raise ValueError('Invalid video graph or settings.')
    from video_capture import capability,check,instrument
    capture=settings.get('capture');check(capture,settings.get('preset',NATIVE))
    if capture and body.get('video_capture')!=capability(root):raise ValueError('Capture extension version mismatch.')
    try:
        image=g['8']['inputs']['image'];seed=g['15']['inputs']['noise_seed'];prompt=g['5']['inputs']['text']
        prefix=g['32']['inputs']['filename_prefix']
        expected=build(root,image,settings.get('duration'),settings.get('motion'),seed,prompt,prefix,settings.get('preset',NATIVE))
        if capture:expected=instrument(root,expected,body['id'],capture)
    except (KeyError,TypeError):raise ValueError('Incomplete video graph.')
    # Only declared duration, movement mode, text, seed and uploaded image may vary.
    # Fixed topology also bounds resolution, batch count, schedule and decode memory.
    if g!=expected:raise ValueError('Video graph differs from the bounded installed workflow.')
    if not isinstance(image,str) or not image.startswith('asset:') or image[6:] not in assets:raise ValueError('Upload the approved image before submitting video.')
    if assets[image[6:]].get('dimensions')!=[1920,1080]:raise ValueError('Video requires a native 1920 × 1080 transferred image. Re-upload legacy transfers.')
    expected['8']['inputs']['image']=assets[image[6:]]['comfy_name']
    expected['32']['inputs']['filename_prefix']='Pixeloid_Worker/'+body['id']+'/node_32'
    return expected

def validate(root,body,assets):
    expected=contract(root)
    if body.get('protocol')!=VERSION or body.get('workflow')!=expected['workflow']:
        raise ValueError('Worker/workflow version mismatch. Deploy the same tested source snapshot on both machines while idle.')
    if body.get('kind') not in expected['kinds']:raise ValueError('Unsupported worker job kind.')
    if not ID.fullmatch(str(body.get('id',''))):raise ValueError('Invalid persistent job ID.')
    if body['kind']=='video':return validate_video(root,body,assets)
    template=json.loads((Path(root)/'templates/flux.json').read_text(encoding='utf-8-sig'))
    allowed={v['class_type'] for v in template.values()}|EXTRA
    models={k:{v['inputs'][k] for v in template.values() if k in v['inputs']} for k in ('unet_name','clip_name','vae_name')}
    graph=copy.deepcopy(body.get('graph'))
    if not isinstance(graph,dict) or not 1<=len(graph)<=150:raise ValueError('Invalid image graph.')
    if str(body.get('output_node')) not in graph:raise ValueError('Missing output node.')
    for key,node in graph.items():
        if not str(key).isdigit() or not isinstance(node,dict) or set(node)-{'class_type','inputs'}:raise ValueError('Unsupported node record.')
        cls=node.get('class_type');inputs=node.get('inputs')
        if cls not in allowed or not isinstance(inputs,dict):raise ValueError('Unsupported workflow node: '+str(cls))
        for name,value in inputs.items():
            if name in models and value not in models[name]:raise ValueError('Model is not part of this installed FLUX contract.')
            if name in ('width','height') and isinstance(value,(int,float)) and not 1<=value<=4096:raise ValueError('Image dimensions exceed worker limit.')
            if name=='steps' and isinstance(value,(int,float)) and not 1<=value<=50:raise ValueError('Sampling steps exceed worker limit.')
        if cls=='LoadImage':
            aid=inputs.get('image','')
            if not isinstance(aid,str) or not aid.startswith('asset:') or aid[6:] not in assets:raise ValueError('Upload the required input asset before submitting.')
            inputs['image']=assets[aid[6:]]['comfy_name']
        if cls=='SaveImage':inputs['filename_prefix']='Pixeloid_Worker/'+body['id']+'/node_'+str(key)
    return graph


def video_missing(root,specs):
    from video_workflow import build,PREVIEW
    g=build(root,'registry-check',2,'still',2909202661,'Registry check only','check',PREVIEW)
    missing=[]
    for n in g.values():
        cls=n['class_type'];spec=specs.get(cls)
        if not spec:
            missing.append(cls);continue
        for name in spec.get('input',{}).get('required',{}):
            if name not in n['inputs']:missing.append(cls+'.'+name)
        for key in ('unet_name','clip_name','vae_name'):
            if key in n['inputs']:
                choices=spec.get('input',{}).get('required',{}).get(key,[[]])[0]
                if not isinstance(choices,list) or n['inputs'][key] not in choices:missing.append(n['inputs'][key])
    return sorted(set(missing))
