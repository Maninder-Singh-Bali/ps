"""In-dashboard connection to installed local components. No implicit downloads."""
import json,shutil,subprocess,time
from pathlib import Path
import requests
from standalone import config,renderer_address


def installations(root):
    root=Path(root);found=[]
    candidates=[root]+[p/'Pixeloid_Studio_Dashboard' for p in list(root.parents)[:3]]+[p/'pixeloid-studio' for p in list(root.parents)[:3]]
    for candidate in dict.fromkeys(candidates):
        file=candidate/'studio.local.json'
        if not file.is_file():continue
        try:entry=json.loads(file.read_text(encoding='utf-8-sig'))
        except (OSError,ValueError):continue
        python=Path(entry.get('comfy_python',''));comfy=Path(entry.get('comfy_root',''))
        if python.is_file() and (comfy/'main.py').is_file():
            paths={'comfy_python':str(python),'comfy_root':str(comfy),'ollama_executable':str(candidate/'runtime/ollama/ollama.exe')}
            if not any(i['comfy_python']==paths['comfy_python'] for i in found):found.append(paths)
    return found


def status(engine):
    from raster_reconstruction import runtime
    from engine import memory_headroom
    c=config(engine.app_root);components=[]
    try:geometry=runtime(engine.app_root);components.append({'name':'Raster boundaries & curve fitting','state':'ready','detail':'CPU processing using installed SciPy. No model weights needed.'})
    except (ValueError,OSError,subprocess.SubprocessError) as e:components.append({'name':'Raster boundaries & curve fitting','state':'missing','detail':str(e)})
    models=[];s=requests.Session();s.trust_env=False
    try:
        url=engine.store.db['settings'].get('vision_url','http://127.0.0.1:11434');renderer_address(url)
        r=s.get(url+'/api/tags',timeout=2);r.raise_for_status();models=r.json().get('models',[])
        components.append({'name':'Local object reader','state':'ready' if models else 'missing','detail':'Installed models: '+', '.join(m['name'] for m in models) if models else 'No local visual model found.'})
    except (requests.RequestException,ValueError):components.append({'name':'Local object reader','state':'offline','detail':'Connect the installed components, then start the reader here.'})
    finally:s.close()
    renderer={'name':'FLUX / LTX','state':'offline','detail':'Start the installed local renderer here. Models load only when a task is queued.'}
    if engine.health(force=True).get('connected'):
        from standalone import workflow_requirements
        try:
            specs=engine.get('/object_info');types,required=workflow_requirements(engine.app_root)
            absent=sorted(types-set(specs))
            for cls,key,name in required:
                choices=specs.get(cls,{}).get('input',{}).get('required',{}).get(key,[[]])[0]
                if not isinstance(choices,list) or name not in choices:absent.append(name)
            renderer.update(state='missing' if absent else 'ready',detail='Missing local components: '+', '.join(absent) if absent else f'Both workflows and {len(required)} installed model files are available. No downloads needed.')
        except (requests.RequestException,ValueError,KeyError) as exc:
            renderer.update(state='attention',detail='Renderer connected; component check failed: '+str(exc)[:180])
    components.append(renderer)
    components.append({'name':'DWG','state':'unsupported','detail':'No configured, validated local DWG adapter. DXF and PDF are supported. No online conversion is used.'})
    components.append({'name':'Trained architectural segmentation','state':'unavailable','detail':'No trained wall/room segmentation model or reviewed annotation set is installed. Pixel tracing stays explicitly provisional.'})
    gpu=[]
    try:
        proc=subprocess.run(['nvidia-smi','--query-gpu=name,memory.total,memory.free','--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=5,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        if proc.returncode==0:gpu=proc.stdout.strip().splitlines()
    except (OSError,subprocess.SubprocessError):pass
    from component_setup import catalog
    return {'components':components,'downloads':catalog(engine),'installations':installations(engine.app_root),'gpu':gpu,'ram_available_gb':round(memory_headroom()[0],1),
            'models':[{'name':m['name'],'bytes':m.get('size')} for m in models],
            'configuration':{k:c.get(k,'') for k in ('comfy_python','comfy_root')},
            'download_policy':'Connect performs no downloads. Optional downloads require explicit approval below and are size- and checksum-verified. The current catalogue includes the FLUX diffusion model only; installers for the remaining runtime/model components are not yet available.'}


def connect(engine,data):
    if any(j['status'] in ('queued','waiting','running') for j in engine.store.db['jobs'].values()):raise ValueError('Wait for current processing before changing components.')
    if 'installation' in data:
        choices=installations(engine.app_root);index=data['installation']
        if type(index) is not int or not 0<=index<len(choices):raise ValueError('Refresh Setup and choose an installed engine.')
        settings=choices[index]
    else:settings={k:str(data.get(k,'')) for k in ('comfy_python','comfy_root')}
    if not Path(settings['comfy_python']).is_file() or not (Path(settings['comfy_root'])/'main.py').is_file():raise ValueError('Choose the installed engine Python and ComfyUI folder.')
    c=config(engine.app_root);c.update(settings);c['auto_start_renderer']=True
    target=Path(engine.app_root)/'studio.local.json';temp=target.with_suffix('.tmp');temp.write_text(json.dumps(c,indent=2),encoding='utf-8');temp.replace(target)
    if not engine.store.db['settings'].get('vision_model'):
        s=requests.Session();s.trust_env=False
        try:
            url=engine.store.db['settings']['vision_url'];renderer_address(url)
            names=[m['name'] for m in s.get(url+'/api/tags',timeout=2).json().get('models',[])]
            if 'qwen3-vl:8b-instruct' in names:engine.store.db['settings']['vision_model']='qwen3-vl:8b-instruct';engine.store.save()
        except (requests.RequestException,ValueError):pass
        finally:s.close()
    return {'saved':True,'message':'Installed local components connected. No models downloaded or copied.'}


def start_vision(engine):
    from vision_study import ensure_service
    with engine.store.lock:
        if any(j['status']=='running' for j in engine.store.db['jobs'].values()):raise ValueError('Wait for the current job before starting another service.')
    tags=ensure_service(engine.app_root,engine.store.db['settings']['vision_url'])
    return {'message':'Local reader is ready. Models load only when analysis is queued.','models':[m['name'] for m in tags.get('models',[])]}
