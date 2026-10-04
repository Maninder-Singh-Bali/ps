"""Build isolated production-UI staging. Reads code, never the production Store."""
from pathlib import Path
import runpy,shutil,json,re,hashlib,sys,subprocess,copy,os
from PIL import Image,ImageDraw
import av
ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'source' if (ROOT/'source/static').is_dir() else ROOT
runpy.run_path(str(ROOT/'staging-preview/build.py'))
OUT=ROOT/'verification/https-staging-ui-20261004/site';OUT.mkdir(parents=True,exist_ok=True)
shutil.copytree(ROOT/'verification/https-staging-20261004/site/app',OUT/'app',dirs_exist_ok=True)
APP=OUT/'app';MEDIA=OUT/'samples';MEDIA.mkdir(exist_ok=True)
sys.path.insert(0,str(SOURCE));import plan_drafts
seed=json.loads((APP/'fixture.json').read_text());docs={};scenes={};footprints={}
node=os.environ.get('PIXELOID_NODE') or shutil.which('node')
if not node:raise RuntimeError('Node is required. Put it on PATH or set PIXELOID_NODE.')
for i in [1,2]:
 d=copy.deepcopy(seed);d.update(id=f'synthetic-floor-{i}',name=f'Synthetic · Floor {i}',revision=1,active_project_id='synthetic-ui',draft_only=False)
 d['room_names']={};d['source_url']=f'/ps/samples/floor-{i}.svg'
 if i==2:
  # Reposition one partition and shorten the floor without reusing private geometry.
  for f in d['features']:
   f['points']=[[p[0],p[1]*.8+20] for p in f['points']]
   if f.get('host_wall_id') in ['east','divider']:f['offset']*=.8;f['width']*=.8
   for n in f.get('junction_nodes',[]):n['point'][1]=n['point'][1]*.8+20
  d['features']=[f for f in d['features'] if f['id'] not in ['divider','bathroom','bedroom-door','bathroom-door']]
  for f in d['features']:f.pop('junction_nodes',None)
  d['surface_design']['surfaces']=[];d['surface_design']['items']=[]
  # Use the production right-angle fillet implementation on a clear shell corner.
  code="const G=require('./static/trace-geometry.js');let f=JSON.parse(require('fs').readFileSync(0,'utf8'));process.stdout.write(JSON.stringify(G.fillet(f,'east',1,35,'demo-round',2.8)));"
  d['features']=json.loads(subprocess.check_output([node,'-e',code],input=json.dumps(d['features']).encode(),cwd=SOURCE))
 if i==1:
  d['surface_design']['surfaces'][0]['finish'].update(tile_width=.6,tile_length=.6,grout=.004,grout_color='#ddd4c5',rotation=0,offset_x=0,offset_y=0,layout='grid',bookmatch=False)
  d['surface_design']['items'][0]['reference']={'dimension_status':'assumed','aspect_locked':False}
  d['surface_design']['items'] += [{'id':'demo-pendant','surface_id':'ceiling','kind':'pendant','x':3,'y':2.4,'width':.45,'height':.45,'depth':.2,'drop':.6,'rotation':0,'reference':{'dimension_status':'assumed'}},{'id':'demo-rug','surface_id':'floor','kind':'rug','x':3,'y':2.8,'width':2,'height':1.5,'depth':.02,'rotation':0,'reference':{'dimension_status':'assumed'}}]
 d=plan_drafts.validate(d,d);d['opening_attachment_revision']=1;docs[d['id']]=d;scenes[d['id']]=plan_drafts.preview(d);footprints[d['id']]=plan_drafts.footprint(d)
 (MEDIA/f'floor-{i}.svg').write_text(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 940 700"><rect width="940" height="700" fill="white"/><text x="470" y="35" text-anchor="middle" font-family="sans-serif" fill="#617083" font-size="20">SYNTHETIC FLOOR {i} · invented dimensions</text></svg>')
# Programmatically drawn fixtures, not inference output or photographs.
for version in [1,2,3]:
 im=Image.new('RGB',(1920,1080),'#d9d2c5');dr=ImageDraw.Draw(im)
 dr.polygon([(0,0),(1920,0),(1480,640),(460,640)],fill='#ebe4d9');dr.polygon([(0,1080),(1920,1080),(1480,640),(460,640)],fill='#b8a085')
 dr.polygon([(0,0),(460,180),(460,640),(0,1080)],fill='#c7bbae');dr.rectangle((600,100,980,460),fill='#819bab');dr.rectangle((620,120,960,440),fill='#bcdce4');dr.line((790,120,790,440),fill='white',width=8)
 dr.rounded_rectangle((1120,480,1760,820),30,fill=['#7c9891','#b8aa88','#8b8eac'][version-1]);dr.rectangle((1140,515,1740,610),fill='#bbc9c4');dr.ellipse((650,720,1050,940),fill='#806443');dr.rectangle((250,300,390,540),fill='#b27454');dr.line((1340,0,1340,220),fill='#414243',width=9);dr.ellipse((1240,190,1440,270),fill='#e6c376')
 dr.rectangle((0,0,1920,55),fill='#253042');dr.text((25,20),f'SYNTHETIC UI FIXTURE · VERSION {version} · NOT GENERATED · NOT A LIVE CAMERA REBUILD',fill='white')
 im.save(MEDIA/f'room-v{version}.png')
for name,color in [('sofa','#7c9891'),('art','#b27454'),('tile','#b8a085'),('lamp','#e6c376')]:
 im=Image.new('RGB',(512,512),'#eee9df');dr=ImageDraw.Draw(im)
 if name=='tile':
  for x in range(0,512,64):
   for y in range(0,512,64):dr.rectangle((x,y,x+61,y+61),fill=color)
 elif name=='lamp':dr.ellipse((90,170,422,340),fill=color);dr.line((256,10,256,170),fill='#373d44',width=6)
 else:dr.rounded_rectangle((50,140,462,390),20,fill=color)
 dr.rectangle((0,0,512,35),fill='#253042');dr.text((10,12),'SYNTHETIC REFERENCE · '+name.upper(),fill='white');im.save(MEDIA/f'{name}.png')
# Deterministic two-second sample clip, using a still with moving progress marker.
container=av.open(str(MEDIA/'sample.mp4'),'w');stream=container.add_stream('libx264',rate=24);stream.width=768;stream.height=432;stream.pix_fmt='yuv420p'
base=Image.open(MEDIA/'room-v2.png').resize((768,432))
for n in range(48):
 im=base.copy();dr=ImageDraw.Draw(im);dr.rectangle((0,412,768,432),fill='#253042');dr.rectangle((0,425,int(768*(n+1)/48),431),fill='#6e9df4');dr.text((12,416),'SIMULATED SAMPLE VIDEO · NO INFERENCE',fill='white')
 frame=av.VideoFrame.from_image(im)
 for packet in stream.encode(frame):container.mux(packet)
for packet in stream.encode():container.mux(packet)
container.close()
assets={};rooms=[]
for i,(did,d) in enumerate(docs.items(),1):
 aid=f'plan-{i}';rid=f'room-{i}';vid=f'view-{i}';floor=f'Floor {i}'
 assets[aid]={'id':aid,'kind':'plan','project_id':'synthetic-ui','name':floor,'display_name':floor,'width':940,'height':700,'url':d['source_url'],'manual_draft_id':did,'manual_document':d,'drawing':{'revision':1},'plan_reading':{'reviewed':True},'created':1}
 bbox=[.08,.1,.84,.8] if i==1 else [.08,.1,.84,.66]
 cam={'position':[.24,.7],'target':[.65,.3],'height':1.6,'target_height':1.4,'horizontal_fov':67}
 views={vid:{'id':vid,'name':'Living view' if i==1 else 'Upper lounge','revision':1,'camera':cam},vid+'-detail':{'id':vid+'-detail','name':'Detail view','revision':1,'camera':{**cam,'position':[.4,.6],'horizontal_fov':45}}}
 r={'id':rid,'plan_id':aid,'name':'Living / dining' if i==1 else 'Upper lounge','floor':floor,'kind':'room','bbox':bbox,'revision':1,'edit_revision':0,'notes':'Invented UI testing room. No backend validation.','references':[],'images':[],'videos':[],'camera_views':views,'view_approvals':{},'approved_image_id':None,'approved_video_id':None,'block_layout':{'items':[],'reviewed':False},'area_polygon':[[bbox[0],bbox[1]],[bbox[0]+bbox[2],bbox[1]],[bbox[0]+bbox[2],bbox[1]+bbox[3]],[bbox[0],bbox[1]+bbox[3]]]}
 for ref in ['sofa','art','tile','lamp']:
  refid=f'{rid}-{ref}';r['references'].append(refid);assets[refid]={'id':refid,'project_id':'synthetic-ui','room_id':rid,'kind':'reference','category':'Synthetic '+ref,'name':ref,'display_name':'Synthetic '+ref,'width':512,'height':512,'url':f'/ps/samples/{ref}.png','enabled':True,'placement':'Demonstration only','created':1,'status':'review'}
 r['block_layout']['items']=[{'id':f'sofa-{i}','preset_id':'sofa-3','label':'Synthetic sofa','kind':'sofa','shape':'box','seat_count':3,'x':.35,'y':.45,'width':220/940,'depth':90/700,'height_m':.85,'angle':0,'asset_id':r['references'][0],'color':'#7c9891','dimension_status':'assumed'}]
 for v in [1,2,3]:
  key=f'image-{i}-{v}';r['images'].append(key);assets[key]={'id':key,'kind':'image','project_id':'synthetic-ui','room_id':rid,'view_id':vid,'view_revision':1,'input_revision':1,'width':1920,'height':1080,'url':f'/ps/samples/room-v{v}.png','status':'rejected' if v==3 else 'review','review_note':'Synthetic sample — browser-local review only.','created':v,'display_name':f'Synthetic image v{v}','version':v,'parent_id':f'image-{i}-{v-1}' if v>1 else None,'imported':True}
 r['anchor_id']=r['images'][0];r['approved_image_id']=r['images'][1];r['view_approvals'][vid]={'approved_image_id':r['images'][1]};assets[r['images'][1]]['status']='approved'
 key=f'video-{i}';r['videos']=[key];assets[key]={'id':key,'kind':'video','project_id':'synthetic-ui','room_id':rid,'view_id':vid,'view_revision':1,'input_revision':1,'source_image_id':r['approved_image_id'],'width':768,'height':432,'fps':24,'frames':48,'duration':2,'video_preset':'ltx-preview-768x432-2s-v1','url':'/ps/samples/sample.mp4','status':'review','created':4,'review_note':'SIMULATED sample clip — not inference output.'}
 rooms.append(r)
p={'id':'synthetic-ui','name':'Synthetic studio · two floors','rooms':rooms,'floor_plans':['plan-1','plan-2'],'manual_draft_id':'synthetic-floor-1','map_revision':1,'map_confirmed':True,'measurements':[],'style':'Synthetic fixtures for UI testing only','seed':1,'generation_phase':{'status':'simulated','allowances':{}},'created':1}
pack={'state':{'projects':{p['id']:p},'assets':assets,'jobs':{},'engine':{'connected':True,'remote':False,'running':0,'pending':0},'settings':{},'activity':[]},'docs':docs,'scenes':scenes,'footprints':footprints}
(APP/'ui-fixtures.json').write_text(json.dumps(pack))
sys.path.insert(0,str(ROOT/'staging-preview'))
from multi_room_fixture import build as build_multi_room
(APP/'multi-room-fixtures.json').write_text(json.dumps(build_multi_room(pack,plan_drafts,MEDIA)))
# Copy production components; omit all PC/settings/storage-management modules.
html=(SOURCE/'static/index.html').read_text();omit={'studio-access.js','local-setup.js','system-status.js','project-files.js','plan-reading.js','raster-review.js','source-panels.js','construction-area.js','products.js'}
names=set(re.findall(r'(?:src|href)="/([^"?]+)',html));names|={'furniture-meshes.json'}
for name in names:
 if name in omit:html=re.sub(r'<script src="/'+re.escape(name)+r'" defer></script>','',html);continue
 src=SOURCE/'static'/name
 if not src.is_file():continue
 text=src.read_text()
 if name.endswith('.js'):
  text=text.replace('/icons/','/ps/app/icons/').replace("'/floor-plan.html","'/ps/app/floor-plan.html").replace('"/floor-plan.html','"/ps/app/floor-plan.html').replace("'/?project=","'/ps/?project=")
  # Isolate every production local preference in the staging origin namespace.
  text=text.replace('pixeloid-','pixeloid-ui-staging-')
  text=text.replace('/ps/app/floor-plan.html#','/ps/app/floor-plan.html?preview=ui8#')
  text=text.replace("link.href='/ps/app/floor-plan.html'", "link.href='/ps/app/floor-plan.html?preview=ui8'")
  text=text.replace("location.href='/ps/app/floor-plan.html'+(stage==='surfaces'?'?stage=surfaces':'')", "location.href='/ps/app/floor-plan.html?preview=ui8'+(stage==='surfaces'?'&stage=surfaces':'')")

 if name=='app.js':
  text=re.sub(r'<div class="manual-plan-choice">.*?</div>','',text)
  text=re.sub(r'^function settings\(\).*$',"function settings(){toast('Deployment settings are unavailable in staging.');}",text,flags=re.M)
  text=re.sub(r"else if\(action==='save-settings'\).*?(?=else if\(action==='direction'\))","else if(action==='save-settings'){throw Error('Unavailable in staging.')}",text)
  text += '\nwindow.Staging.hasUnsaved=()=>window.CameraEditor?.pending()||window.FurnitureEditor?.pending();window.Staging.discardForReset=()=>window.InlinePlan?.reset();\n'
  text=text.replace("e.remote?'● Local design · PC on demand':e.connected?`● Renderer connected${e.running||e.pending?' · busy':''}`:'○ Renderer offline'","'SIMULATED · browser only'")
  text=text.replace('Native render','Synthetic sample').replace('Native 1080','Synthetic 1920 × 1080')
 if name=='interior-planner.js':text=text.replace('FLUX image · configured worker workflow','SIMULATED image · bundled fixture').replace('Renderer offline. Generation requires the paired PC.','SIMULATED disconnected state. Reconnect in Testing controls.')
 if name=='furniture-blocks.js':text=text.replace('No conflicts found with the currently mapped features.','Mock check only; placement has no backend validation.').replace('Check missing geometry and walking space yourself.','Review geometry manually.').replace('No mapped conflicts','Mock check · not validated').replace('Check missing geometry and walking space. This is not structural validation.','No backend validation runs in this preview. Review geometry manually.')
 if name=='camera-view.js':text=text.replace("'Saved camera view.'","'Saved camera view. STATIC sample — not rebuilt from this camera.'").replace("'View changed · not saved.'","'View changed · not saved. STATIC sample — not a live rebuild.'")
 if name=='scene-control.js':text=text.replace('The surrounding image is copied from the master and checked pixel by pixel.','This simulation records the mask only; no pixels are regenerated or validated.').replace('Everything outside it stays as it is in this master image.','This is a mask interaction test, not an image edit result.')
 if name=='video-presets.js':text=text.replace('Generation still requires approval and an available phase.','SIMULATED controls; every result is the bundled 2-second clip.').replace('Preview samples at 768 × 448 and crops to 768 × 432. No upscaling. Frames 0–47 are retained; guided endpoint frame 48 is excluded.','SIMULATED preset selection. No sampler runs; the bundled 768 × 432, 48-frame clip is returned.')
 if name=='generation-progress.js':text=text.replace('Rendering steps','SIMULATED steps').replace('rendered','simulated').replace('renderer completes a step','simulator advances a step').replace('Native 1080','SIMULATED sample')
 (APP/name).write_text(text)
html=re.sub(r'([\'"])/(?!ps/)',r'\1/ps/app/',html)
html=html.replace('<script src="/ps/app/appearance.js">','<script src="/ps/app/ui-adapter.js"></script><script src="/ps/app/appearance.js">')
html=html.replace('</head>','<link rel="stylesheet" href="/ps/app/ui-staging.css">'+(ROOT/'staging-preview/csp.html').read_text().replace("img-src 'self' data: blob:;","img-src 'self' data: blob:; media-src 'self' blob:;")+'</head>')
html=html.replace('href="/ps/app/"','href="/ps/"').replace('Private. Local. Yours.','Synthetic browser sandbox.').replace('Local design · Saved edits update the shared scene','SIMULATED · local saves · no backend validation')
html=html.replace('</body>','<script src="/ps/app/ui-controls.js"></script></body>')
(OUT/'index.html').write_text(html)
# Existing real Plan/Surface components keep the staging API boundary.
floor=(APP/'floor-plan.html').read_text().replace('staging-api.js','ui-adapter.js').replace('staging.css','ui-staging.css');floor=re.sub(r'<div class="staging-bar">.*?</div>','',floor);floor=floor.replace('</body>','<script src="/ps/app/ui-controls.js"></script></body>');(APP/'floor-plan.html').write_text(floor)
floorjs=(APP/'floor-plan.js').read_text().replace('Apartment saved. Shared scene updated.','Synthetic draft saved in this browser. No backend validation.').replace('window.Staging.api(path,body,raw)','window.Staging.planApi(path,body,raw)').replace('pixeloid-','pixeloid-ui-staging-').replace("'/ps/?project='","'/ps/?preview=ui8&project='");floorjs = floorjs.rsplit('})();',1)[0]+'\nwindow.Staging.hasUnsaved=()=>dirty;window.Staging.discardForReset=()=>{dirty=false;saveTicket++;changeSerial++;};\n})();\n'
(APP/'floor-plan.js').write_text(floorjs)
# Reuse the existing Surface Design assignment flow with a bundled reference provider.
surface=(APP/'surface-design.js').read_text().replace('pixeloid-','pixeloid-ui-staging-');start=surface.index('async function readReference(');end=surface.index('\nasync function action(',start)
surface=surface[:start]+"async function readReference(texture=false){const target=texture?finishTarget():selectedItems()[0];if(!target)throw Error('Select an item first.');const reference=await window.Staging.reference();update(()=>{const owner=texture?(target.finish||={}):target;owner.reference={...owner.reference,...reference};});h.toast('Bundled synthetic reference assigned; dimensions unchanged.');}\n"+surface[end:]
(APP/'surface-design.js').write_text(surface)
for name in ['ui-adapter.js','ui-controls.js','ui-staging.css']:shutil.copy2(ROOT/'staging-preview'/name,APP/name)
# Version resources so an updated Pages deployment cannot mix old browser scripts with new fixtures.
fixture_hash=hashlib.sha256((APP/'ui-fixtures.json').read_bytes()).hexdigest()[:12]
adapter=(APP/'ui-adapter.js').read_text().replace("'ui-fixtures.json'",f"'ui-fixtures.json?v={fixture_hash}'")
adapter=adapter.replace("'multi-room-fixtures.json'","'multi-room-fixtures.json?v="+hashlib.sha256((APP/'multi-room-fixtures.json').read_bytes()).hexdigest()[:12]+"'")
(APP/'ui-adapter.js').write_text(adapter)
for page in [OUT/'index.html',APP/'floor-plan.html']:
 def versioned(m):
  path=OUT/m.group(2).removeprefix('/ps/')
  return m.group(1)+m.group(2)+'?v='+hashlib.sha256(path.read_bytes()).hexdigest()[:12]+m.group(3) if path.is_file() else m.group(0)
 page.write_text(re.sub(r'''((?:src|href)=\")(/ps/[^\"?]+\.(?:js|css))(\")''',versioned,page.read_text()))

for name in ['.nojekyll','404.html']:shutil.copy2(ROOT/'verification/https-staging-20261004/site'/name,OUT/name)
(OUT/'README.md').write_text((ROOT/'staging-preview/UI-README.md').read_text())
(OUT/'VERIFICATION.md').write_text((ROOT/'staging-preview/UI-VERIFICATION.md').read_text())
for obsolete in ['fixture.json','staging-api.js','staging.css','products.js']:
 (APP/obsolete).unlink(missing_ok=True)
manifest={'source_commit':os.environ.get('PIXELOID_SOURCE_COMMIT','local-uncommitted'),'type':'production components + staging-only adapter','backend':'none','inference':False,'files':{str(p.relative_to(OUT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in OUT.rglob('*') if p.is_file() and p.name!='preview-manifest.json'}}
(OUT/'preview-manifest.json').write_text(json.dumps(manifest,indent=2));print('Production UI preview built:',len(manifest['files']),'files')
