"""Bounded, resumable tiled detection with explicit coverage and provenance."""
import copy, hashlib, json, math, re, time
from pathlib import Path
from urllib.parse import urlparse
import requests
from PIL import Image, ImageOps
from detection_review import identity, compare_sources, reconcile

VERSION=1
PROMPT='Coordinates range from 0 to 1000 relative to this image. Use tight visible bounds. No prose outside JSON.'


def recover_finished_rows(text,key):
    """Preserve complete JSON objects before an output-limit cut; never repair a partial row."""
    match=re.search(r'"'+re.escape(key)+r'"\s*:\s*\[',text)
    rows=[]
    if not match:return rows
    tail=text[match.end():].lstrip();decoder=json.JSONDecoder()
    while tail.startswith('{'):
        try:row,end=decoder.raw_decode(tail)
        except ValueError:break
        if isinstance(row,dict):rows.append(row)
        tail=tail[end:].lstrip()
        if not tail.startswith(','):break
        tail=tail[1:].lstrip()
    return rows

def tiles(box,size,limit=1200):
    x,y,w,h=box
    if len(box)!=4 or not all(math.isfinite(v) for v in box) or min(w,h)<=0 or min(x,y)<0 or x+w>1.00001 or y+h>1.00001:
        raise ValueError('Invalid selected section bounds.')
    nx=max(1,math.ceil(w*size[0]/limit));ny=max(1,math.ceil(h*size[1]/limit))
    for iy in range(ny):
        for ix in range(nx):
            dx=w/nx;dy=h/ny
            left=max(x,x+ix*dx-dx*.08);top=max(y,y+iy*dy-dy*.08)
            right=min(x+w,x+(ix+1)*dx+dx*.08);bottom=min(y+h,y+(iy+1)*dy+dy*.08)
            yield [left,top,right-left,bottom-top]

def signature(path,enhanced,model,sections):
    root=Path(__file__).parent
    modules=['detection_pipeline.py','detection_review.py','object_detection.py','object_knowledge.py','vision_study.py','plan_upscale.py']
    return identity([VERSION,hashlib.sha256(Path(path).read_bytes()).hexdigest(),hashlib.sha256(Path(enhanced).read_bytes()).hexdigest(),model,sections,
                     {name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in modules},
                     hashlib.sha256((root/'static/furniture-library.js').read_bytes()).hexdigest()])

def read(path,enhanced,settings,sections,progress,cache_dir=None,cancelled=None):
    from object_detection import encode_crop,parse_objects,map_box,merge_features
    from object_knowledge import RULES,quality_flags
    from vision_study import MODEL,check_observations
    model=settings.get('vision_model') or MODEL
    address=urlparse(settings.get('vision_url','http://127.0.0.1:11434').rstrip('/'))
    if address.scheme!='http' or address.hostname not in ('127.0.0.1','localhost') or address.username or address.password or address.path not in ('','/') or address.query or address.fragment:
        raise ValueError('Object detection requires a local vision service.')
    url=address.geturl().rstrip('/');started=time.monotonic();cancelled=cancelled or (lambda:False)
    budget=max(1,min(128,int(settings.get('detection_max_passes',32))))
    seconds=max(1,min(1800,float(settings.get('detection_max_seconds',600))))
    source_hash=hashlib.sha256(Path(path).read_bytes()).hexdigest()
    enhanced_hash=hashlib.sha256(Path(enhanced).read_bytes()).hexdigest();paired=source_hash!=enhanced_hash
    with Image.open(path) as im:original=ImageOps.exif_transpose(im).convert('RGB')
    with Image.open(enhanced) as im:detail=ImageOps.exif_transpose(im).convert('RGB')
    key=signature(path,enhanced,model,sections)
    checkpoint=Path(cache_dir)/(key+'.json') if cache_dir else None
    completed={}
    if checkpoint and checkpoint.exists():
        try:completed=json.loads(checkpoint.read_text(encoding='utf-8')).get('completed_passes',{})
        except (OSError,ValueError):pass
    queue=[{'region':[0,0,1,1],'mode':'sections','depth':0,'section_id':None}]
    scopes=sections or [{'id':'full-page','bbox':[0,0,1,1]}]
    for scope in scopes:
        for box in tiles(scope['bbox'],original.size):queue.append({'region':box,'mode':'objects','depth':0,'section_id':scope.get('id')})
    result={'features':[],'warnings':[],'reviewed':False,'passes':[],'source_sha256':source_hash,'pipeline_version':VERSION}
    native=[];count=0;network_calls=0;seen=set();done_keys=set();limited=False;was_cancelled=False
    session=requests.Session();session.trust_env=False
    def save():
        if checkpoint:
            checkpoint.parent.mkdir(parents=True,exist_ok=True);tmp=checkpoint.with_suffix('.tmp')
            tmp.write_text(json.dumps({'pipeline_key':key,'completed_passes':completed}),encoding='utf8');tmp.replace(checkpoint)
    def request(region,mode,source):
        task=('Identify visible rooms separately. Return JSON {"rooms":[{"name":"room name","bbox_2d":[x1,y1,x2,y2]}]}.' if mode=='sections' else
              'Identify individual visible furniture, fixtures, doors, windows and stairs. Return JSON {"objects":[{"name":"object name","kind":"furniture|door|window|sliding_door|stair|wall|curved_wall|unknown","bbox_2d":[x1,y1,x2,y2],"confidence":"low|medium|high","evidence":"visible cue, maximum 8 words"}]}. Up to 12 objects; no rooms. Prefer concise records; additional crops cover dense regions.')
        response=session.post(url+'/api/chat',json={'model':model,'messages':[{'role':'user','content':task+' '+PROMPT+'\n'+RULES,'images':[encode_crop(source,region)]}],
            'format':'json','stream':False,'think':False,'keep_alive':'2m','options':{'temperature':0,'num_ctx':8192,'num_predict':2800}},timeout=(10,min(240,max(1,seconds-(time.monotonic()-started)))))
        response.raise_for_status();data=response.json()
        try:raw=json.loads(data.get('message',{}).get('content',''))
        except ValueError:
            if data.get('done_reason')!='length':raise
            key='rooms' if mode=='sections' else 'objects'
            raw={key:recover_finished_rows(data.get('message',{}).get('content',''),key),'uncertainties':['Reader output was truncated; only complete records retained; subdividing this region.']}
        parsed=parse_objects(raw,mode)
        parsed['saturated']=data.get('done_reason')=='length' or len(raw.get('rooms' if mode=='sections' else 'objects',[]))>=(20 if mode=='sections' else 12)
        return parsed
    try:
        while queue:
            task=queue.pop(0);taskkey=identity(task)
            if taskkey in seen:continue
            seen.add(taskkey)
            if cancelled():was_cancelled=True;queue.insert(0,task);break
            # Cached passes do not consume the per-run network budget.
            needs_original=paired and task['mode']=='objects'
            cached=completed.get(taskkey)
            needed=(1 if needs_original and cached.get('comparison_pending') else 0) if cached else (2 if needs_original else 1)
            if needed and (network_calls+needed>budget or time.monotonic()-started>=seconds):
                limited=True;queue.insert(0,task);break
            count+=1;progress(f"Reading plan · region {count} · {len(queue)} queued",None)
            try:
                if cached:record=copy.deepcopy(cached)
                else:
                    network_calls+=1;parsed=request(task['region'],task['mode'],detail)
                    record={'task':task,'parsed':parsed,'original':None,'comparison_pending':needs_original}
                    completed[taskkey]=copy.deepcopy(record);save()
                if record.get('comparison_pending'):
                    if cancelled():was_cancelled=True;queue.insert(0,task);break
                    if time.monotonic()-started>=seconds:limited=True;queue.insert(0,task);break
                    network_calls+=1;record['original']=request(task['region'],'objects',original)
                    record['comparison_pending']=False;completed[taskkey]=copy.deepcopy(record);save()
                parsed=record['parsed'];reference=record['original']
                for source_name,output in [('enhanced' if paired else 'original',parsed),('original',reference)]:
                    if output is None:continue
                    for f in output['features']:
                        f['bbox']=map_box(f['bbox'],task['region'])
                        f['id']='observation'+identity([source_hash,taskkey,source_name,f['kind'],f['object_type'],f['bbox']])
                        f.update(detection_pass=count,source_variant=source_name,section_id=task['section_id'])
                if reference:
                    compare_sources(parsed['features'],reference['features']);native.extend(reference['features'])
                    # Original-only detections remain explicit alternatives too.
                    for f in reference['features']:
                        if not any(f['id'] in v.get('original_matches',[]) for v in parsed['features']):
                            f['source_agreement']='disagrees';parsed['features'].append(f)
                result['features'].extend(parsed['features']);result['warnings'].extend(parsed['warnings'])
                saturated=parsed['saturated'] or bool(reference and reference['saturated'])
                result['passes'].append({**task,'id':taskkey,'count':len(parsed['features']),'status':'saturated' if saturated else 'completed','source_comparison':bool(reference)})
                if saturated and task['depth']<2:
                    x,y,w,h=task['region']
                    for yy in (0,.45):
                        for xx in (0,.45):queue.append({**task,'region':[x+xx*w,y+yy*h,w*.55,h*.55],'depth':task['depth']+1,'parent_id':taskkey})
                elif saturated:result['warnings'].append('Dense region still exceeds one pass; coverage remains incomplete.')
                done_keys.add(taskkey)
            except (requests.RequestException,ValueError,KeyError,TypeError) as exc:
                result['warnings'].append(f'Region {count} could not finish: {str(exc)[:180]}')
                result['passes'].append({**task,'id':taskkey,'status':'failed'})
            if cancelled():was_cancelled=True;break
    finally:
        if network_calls:
            try:session.post(url+'/api/generate',json={'model':model,'keep_alive':0},timeout=10)
            except requests.RequestException:pass
        session.close()
    if limited:result['warnings'].append('Processing budget reached. Resume analysis to continue unfinished regions.')
    if was_cancelled:result['warnings'].append('Analysis stopped. Completed regions are saved for resume.')
    result['features']=merge_features(result['features']);quality_flags(result)
    check_observations(result,sections or [{'bbox':f['bbox'],'name':f['label']} for f in result['features'] if f['kind']=='space'])
    # A saturated parent is covered only when every overlapping child has finished.
    def covered(p):
        if p['status']=='completed':return True
        children=[v for v in result['passes'] if v.get('parent_id')==p['id']]
        return p['status']=='saturated' and len(children)==4 and all(covered(v) for v in children)
    coverage=not queue and all(covered(v) for v in result['passes']) and bool(result['passes']) and not was_cancelled
    result.update(processing_finished=not was_cancelled,coverage_complete=coverage,complete=coverage,cancelled=was_cancelled,
        geometry_validated=False,user_reviewed=False,source_size=list(original.size),model=model,elapsed_seconds=round(time.monotonic()-started,2),
        coverage={'selected_sections':len(sections),'processed_sections':sorted({v['section_id'] for v in result['passes'] if v.get('section_id')}),
                  'pending_regions':len(queue),'failed_regions':sum(v['status']=='failed' for v in result['passes']),'network_calls':network_calls,'resumable':bool(checkpoint)},
        pipeline_key=key,scale_status='estimated',original_observations=native,scope='Visual estimates; processing coverage is not detection accuracy.')
    result['warnings']=list(dict.fromkeys(result['warnings']))
    return reconcile(result)
