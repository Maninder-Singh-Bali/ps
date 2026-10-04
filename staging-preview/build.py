"""Synthetic-only static preview. Never reads the deployed Store or private files."""
from pathlib import Path
import sys,json,shutil,hashlib,re,os,subprocess
ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'source' if (ROOT/'source/static').is_dir() else ROOT
sys.path.insert(0,str(SOURCE))
import plan_drafts
OUT=ROOT/'verification/https-staging-20261004/site';APP=OUT/'app';APP.mkdir(parents=True,exist_ok=True)
wall=lambda key,a,b:{'id':key,'kind':'wall','points':[a,b],'thickness':20,'height_m':2.8,'junction_ids':['j'+str(a),'j'+str(b)],'review_note':'Synthetic example; not a surveyed building.'}
fs=[wall('north',[70,70],[870,70]),wall('east',[870,70],[870,620]),wall('south',[870,620],[70,620]),wall('west',[70,620],[70,70]),wall('divider',[550,70],[550,620]),wall('bathroom',[550,400],[870,400])]
for f in fs:f['junction_ids']=[re.sub(r'[^a-zA-Z0-9]','_',s) for s in f['junction_ids']]
fs[0]['junction_nodes']=[{'id':'j550_70','point':[550,70]}];fs[4]['junction_ids'][0]='j550_70'
fs[2]['junction_nodes']=[{'id':'j550_620','point':[550,620]}];fs[4]['junction_ids'][1]='j550_620'
fs[4]['junction_nodes']=[{'id':'j550_400','point':[550,400]}];fs[5]['junction_ids'][0]='j550_400'
fs[1]['junction_nodes']=[{'id':'j870_400','point':[870,400]}];fs[5]['junction_ids'][1]='j870_400'
def opening(key,kind,host,offset,width,base,head):
 w=next(f for f in fs if f['id']==host);a,b=w['points'];L=((a[0]-b[0])**2+(a[1]-b[1])**2)**.5
 at=lambda t:[a[i]+(b[i]-a[i])*t/L for i in (0,1)]
 return {'id':key,'kind':kind,'host_wall_id':host,'points':[at(offset),at(offset+width)],'offset':offset,'width':width,'thickness':10,'frame_thickness':10,'head_m':head,('sill_m' if kind=='window' else 'base_m'):base,'flip':False,'dimension_provenance':'demonstration','review_note':'Demonstration dimensions only; synthetic staging fixture.'}
fs += [opening('living-window','window','north',160,160,.9,2.4),opening('bedroom-window','window','east',110,120,.9,2.4),opening('entry-door','door','south',490,90,0,2.5),opening('bedroom-door','door','divider',130,90,0,2.5),opening('bathroom-door','door','divider',420,62,0,2.1)]
boundary=[[70,70],[870,70],[870,620],[70,620]]
d={'id':'synthetic-apartment-v1','name':'Synthetic apartment · staging','revision':0,'width':940,'height':700,'source_url':'/ps/app/synthetic-paper.svg','features':fs,'wall_height_m':2.8,'units':'m','calibration':{'points':[[70,70],[870,70]],'metres':8,'method':'Synthetic fixture definition; all dimensions are invented'},'background':{'visible':True,'locked':True,'x':0,'y':0,'rotation':0,'opacity':.6},'notes':'Entirely synthetic staging apartment. No private plan, real product or certified measurements.','surface_design':{'version':1,'surfaces':[{'id':'floor','kind':'floor','label':'Demo floor','boundary':boundary,'holes':[],'elevation_m':0,'finish':{'kind':'paint','color':'#d8cbb7'}},{'id':'ceiling','kind':'ceiling','label':'Demo ceiling','boundary':boundary,'holes':[],'elevation_m':2.8},{'id':'wall-face','kind':'wall','wall_id':'west','side':-1,'label':'Demo living wall'}],'items':[{'id':'demo-art','surface_id':'wall-face','kind':'painting','x':2.7,'y':1.5,'width':.6,'height':.8,'depth':.03,'rotation':0,'reference':{'dimension_status':'assumed'}}]},'review':{'view_box':[20,20,900,650],'issues':[]}}
d=plan_drafts.validate(d,d);scene=plan_drafts.preview(d);d['active_project_id']='syntheticpreview';d['draft_only']=True
(APP/'fixture.json').write_text(json.dumps(d));(APP/'fixture-scene.json').write_text(json.dumps(scene));(APP/'fixture-footprint.json').write_text(json.dumps(plan_drafts.footprint(d)))
(APP/'synthetic-paper.svg').write_text('''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 940 700"><rect width="940" height="700" fill="white"/><g fill="#606b78" font-family="sans-serif" text-anchor="middle"><text x="300" y="345" font-size="20">Living / dining</text><text x="710" y="250" font-size="20">Bedroom</text><text x="710" y="515" font-size="20">Bathroom</text><text x="470" y="40" font-size="14">SYNTHETIC · 8.0 × 5.5 m · invented dimensions</text><text x="470" y="670" font-size="13">No original apartment or uploaded plan is included.</text></g></svg>''')
allowed=['appearance.js','appearance.css','workspace-chrome.css','floor-plan.css','floor-plan.html','floor-plan.js','workflow-highlight.js','drawing-geometry.js','trace-geometry.js','opening-editor.js','opening-hosts.js','model-viewer.js','surface-design-geometry.js','surface-design.js']
for name in allowed:
 s=(SOURCE/'static'/name).read_text()
 if name=='floor-plan.js':
  start=s.index('async function api(');end=s.index('\nfunction toast',start);s=s[:start]+"async function api(path,body,raw=false){return window.Staging.api(path,body,raw);}"+s[end:]
  s=s.replace('fill-rule="evenodd"','fill-rule="nonzero"')
  s=s.replace("$('.badge').textContent=doc?.active_project_id?'Active':'Draft'","$('.badge').textContent='Synthetic'")
  s=s.replace("$('.protected').textContent=doc?.active_project_id?'Saved edits update the shared scene':'Active scene protected'","$('.protected').textContent='Browser-local saves · no live backend'")
  s=s.replace("$('#save').lastChild.textContent=doc?.active_project_id?'Save':'Save draft'","$('#save').lastChild.textContent='Save locally'")
  s=s.replace("doc?.active_project_id?'Open project →':'Use this plan'","'Preview overview →'")
  # No static artifact is presented as a regenerated 3D result.
  start=s.index("$('#floating').textContent=doc.surface_design?");end=s.index("mode='3d';",start)
  s=s[:start]+"$('#floating').textContent='READ-ONLY SYNTHETIC FIXTURE · prepared offline · not a live backend';"+s[end:]
  s=s.replace("location.href='/?project='","location.href='/ps/?project='")
  s=s.replace("location.hash.slice(1)||rows.find(r=>r.id==='apartment-correction')?.id||rows[0]?.id","location.hash.slice(1)||rows[0]?.id")
 if name=='floor-plan.html':
  s=s.replace('<script src="/appearance.js">','<script src="/staging-api.js"></script><script src="/appearance.js">')
  s=s.replace('<script src="/reference-upload.js"></script>','')
  s=s.replace('</head>','<link rel="stylesheet" href="/staging.css">'+(ROOT/'staging-preview/csp.html').read_text()+'</head>')
  s=s.replace('<body class="studio-plan">','<body class="studio-plan"><div class="staging-bar">SYNTHETIC PREVIEW · browser-local edits · no live backend <a href="/ps/?stage=about">Capabilities & limits</a><button data-staging-reset>Reset demo</button></div>')
  s=s.replace('href="/"','href="/ps/"')
  s=s.replace('<title>Pixeloid · Floor plan</title>','<title>Pixeloid · Synthetic staging preview</title>')
 # Absolute application resources must stay inside the Pages project subpath.
 if name.endswith('.html'):s=re.sub(r'([\'"`])/(?!ps/)',r'\1/ps/app/',s)
 else:s=s.replace('/icons/','/ps/app/icons/')
 (APP/name).write_text(s)
shutil.copytree(SOURCE/'static/icons',APP/'icons',dirs_exist_ok=True)
for name in ['staging-api.js','staging.css'] :shutil.copy2(ROOT/'staging-preview'/name,APP/name)
for name in ['index.html','preview.js','preview.css'] :shutil.copy2(ROOT/'staging-preview'/name,OUT/name)
(OUT/'.nojekyll').write_text('')
(OUT/'404.html').write_text('<!doctype html><title>Unavailable in staging</title><h1>Unavailable in staging</h1><p>This preview serves static synthetic content only. It has no backend, worker or PC management endpoints.</p><a href="/ps/">Return to preview</a>')
(OUT/'README.md').write_text((ROOT/'staging-preview/README.md').read_text())
manifest={'source_commit':os.environ.get('PIXELOID_SOURCE_COMMIT','local-uncommitted'),'mode':'static synthetic preview','live_backend':False,'inference':False,'data':'newly constructed synthetic apartment','files':{str(p.relative_to(OUT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in OUT.rglob('*') if p.is_file() and p.name!='preview-manifest.json'}}
(OUT/'preview-manifest.json').write_text(json.dumps(manifest,indent=2));print('Synthetic preview:',len(manifest['files']),'files')
