'use strict';

(() => {

 let session=null,scene=null,viewRoom=null,clickMode=0,cameraDraft=null,rotation=-35,visualJob=null,enhancedView=false,diagnosticDraft=false;

 const button=(label,key,disabled=false)=>`<button type="button" class="btn small" data-structure="${key}" ${disabled?'disabled':''}>${label}</button>`;

 const route=key=>`/api/projects/${session.pid}/plans/${session.aid}/${key}`;

 const rooms=()=>state.projects[session.pid].rooms.filter(r=>r.plan_id===session.aid&&r.bbox);
 const currentOwner=()=>session?.pid===pid&&session?.aid===(tab==='plan'?planId:R()?.plan_id||planId);

 function reviewStateKey(){const a=A(session?.aid);return JSON.stringify([a?.vision_report?.pipeline_key,a?.vision_report?.elapsed_seconds,a?.vision_report?.features?.length,a?.review_revision,a?.raster_revision,a?.source_review?.revision,a?.raster_geometry?.pipeline_key,a?.drawing?.revision,a?.plan_reading?.revision,state.projects[session?.pid]?.map_revision])}

 async function load(force=false){
  if(!force&&window.SourcePanels?.pending())return;
  if(!session)return;const target=session;
  if(target.loading){if(!force)return target.pending;await target.pending;if(target!==session)return}
  target.loading=true;const stateKey=reviewStateKey();
  target.pending=(async()=>{try{const report=await api(route('structure'),{},'GET');if(target!==session)return;session.report=report;await loadScene();if(target!==session)return;session.stateKey=stateKey;render()}finally{target.loading=false}})();
  return target.pending;
 }

 async function loadScene(){const owner=session;if(!rooms().some(r=>r.id===viewRoom))viewRoom=rooms()[0]?.id;const target=reviewSceneTarget(A(session.aid),viewRoom,diagnosticDraft);const result=target?await api(route(target.endpoint)+target.query,{},'GET'):null;if(owner!==session||!currentOwner())return;scene=result;cameraDraft=null;clickMode=0}

 window.openStructureCheck=async function(){

  const aid=tab==='plan'?planId:R()?.plan_id||planId;if(!aid)return toast('Upload a full floor plan first.');

  session={pid,aid,report:null};diagnosticDraft=false;enhancedView=false;viewRoom=R()?.plan_id===aid?R().id:null;

  try{await load()}catch(err){toast(err.message)}

 };

 function render(){
  if(!currentOwner())return;

  const d=session.report,rs=rooms(),safe=d.repairs.length,blocking=d.sections.filter(r=>!r.can_generate).length;

  showModal('Review & 3D',`
<div class="structure-summary">

<strong>${rs.length?`${rs.length} room${rs.length===1?'':'s'}`: 'Room analysis incomplete'}</strong>

<span>${safe} safe correction${safe===1?'':'s'} available · ${rs.length?`${blocking} rooms need review`:`Review source evidence to establish rooms`}</span>

</div>

<div class="structure-actions primary-review-action">${button('Edit model','blocks',!viewRoom)}${rs.length?btn(P().map_confirmed?'Map confirmed':'Confirm map','confirm-map',P().map_confirmed?'disabled':'','small'):''}${button(d.vision_report?.coverage_complete===false?'Resume analysis':'Analyze plan','vision',!!visualJob)}${visualJob?button('Stop analysis','cancel-vision'):''}<details class="review-advanced"><summary class="btn small">Advanced</summary>${button('Run checks','refresh')}${button('Apply safe corrections','repair',!safe)}${button('Undo last automatic correction','undo',!d.history.some(h=>!h.undone))}${button('Review symbols & connections','study')}${button('Correct walls & openings','drawing')}${button('Room boundaries & dimensions','areas')}</details></div>

<p id="structure-vision-status" role="status">${visualJob?'Local plan reading is running. Elapsed time will update; no guessed percentage.':''}</p>

${d.vision_report?`<details><summary>Local visual reading · ${d.vision_report.elapsed_seconds}s · ${d.vision_report.features.length} estimates${d.vision_report.complete===false?' · incomplete':''}</summary><p>Estimated sections and objects. Review against the original before using their bounds.</p><ul>${d.vision_report.features.map(f=>`<li>${esc(f.label)}${f.seat_count?` · ${f.seat_count} seats`:''} · ${esc(f.confidence)} confidence${f.suggested_asset_id?' · library match: '+esc(f.suggested_asset_id):' · no exact library match'} — ${esc(f.evidence)}</li>`).join('')}</ul><p>${d.vision_report.warnings.map(esc).join(' · ')}</p>${button('Add predictions to review','import-vision',!d.vision_report.features.length||!!d.vision_report.imported||d.vision_report.input_map_revision!==state.projects[session.pid].map_revision)}</details>`:''}

<aside class="review-issue-list" aria-label="Unresolved items">${window.SourcePanels?.panel(d)||''}${window.RasterReview?.panel(d)||''}<h2>Needs your review</h2>

${(d.vision_report?.review_issues||[]).filter(i=>!['accept','reject'].includes(i.status)).map(i=>`<article data-review-issue="${esc(i.id)}"><button class="review-locate" data-review-focus="${esc(i.id)}">${esc(i.message)}</button><p>Compare the highlighted source before choosing.</p>${(i.alternatives||[]).map(a=>`<button class="btn small" data-review-decision="accept" data-issue="${esc(i.id)}" data-element="${esc(a.id)}">Use ${esc(a.label)}</button>`).join('')}<div>${button('Change in study','study')}<button class="btn small" data-review-decision="reject" data-issue="${esc(i.id)}">Reject</button><button class="btn small" data-review-decision="defer" data-issue="${esc(i.id)}">Defer</button></div>${i.status==='defer'?'<small>Deferred · still unresolved</small>':''}</article>`).join('')||`<p>${rs.length?(d.raster_validation?.geometry_validated?'No classification conflicts remain. Estimated dimensions still need verification.':'No classification conflicts found. Geometry still needs review.'):'Room analysis incomplete. No validated room boundaries yet.'}</p>`}

<p class="help">${d.vision_report?.coverage_complete===true?'Selected regions processed. Accuracy unverified.':d.vision_report?.coverage_complete===false?'Coverage incomplete. Resume analysis.':'Legacy analysis: coverage unverified.'}</p><p class="help">Scale estimated unless calibrated.</p>

<a class="btn small" href="${route('scene-document')}" download="scene.json">Scene data</a>${scene?`<a class="btn small" href="${route('model.glb')}${viewRoom&&!diagnosticDraft?'?room_id='+encodeURIComponent(viewRoom):'?view=draft'}" download="draft.glb">Export GLB</a>`:''}</aside>

<div class="structure-workspace">

<section>

<div class="actions"><h3>Plan detections</h3><button class="btn small" data-structure="fit-source" title="Wheel to zoom; Shift-drag to pan">Fit</button><label><input id="detection-enhanced" type="checkbox" ${enhancedView?'checked':''} ${!A(session.aid).enhanced_reading_id?'disabled':''}> Enhanced copy</label></div>

<div class="structure-map">

<svg id="structure-map" role="img" aria-label="Original full floor plan and saved camera" viewBox="0 0 ${A(session.aid).width} ${A(session.aid).height}">

</svg>

</div>

<div class="structure-actions">

<label class="field">

<span>Section view</span>

<select id="structure-room">${rs.map(r=>`<option value="${r.id}" ${r.id===viewRoom?'selected':''}>${esc(r.floor+' · '+r.name)}</option>`).join('')}</select>

</label>${button('Camera view & preview','camera-editor',!viewRoom)}</div>

<p id="structure-camera-hint" class="help">Place the camera first, then click where it looks. This changes the view, never the plan.</p>

</section>

<section>

<h3>${viewRoom&&!diagnosticDraft?(scene?.partial?'Furnished scene — geometry needs review':'Shared furnished scene'):scene?'Partial 3D draft — unverified':'Enhanced reading copy'}</h3>${viewRoom&&(d.raster_geometry||A(session.aid).plan_source?.vector)?`<label class="help"><input id="review-diagnostic-draft" type="checkbox" ${diagnosticDraft?'checked':''}> Boundary draft only</label>`:''}${!scene?`<img src="${url(A(session.aid).enhanced_reading_id||session.aid)}" alt="Enhanced floor plan reading copy" style="width:100%;height:560px;object-fit:contain;background:white"/><p class="help">Reading aid · compare with the original. Scale remains estimated.</p>`:''}<div ${!scene?'hidden':''}>

<canvas id="structure-3d" width="800" height="560" aria-label="Schematic 3D preview from typed drawing segments">

</canvas>

<label class="field">

<span>Rotate preview</span>

<input id="structure-rotate" type="range" min="-180" max="180" value="${rotation}">

</label>

<p class="help">${scene?`${scene.lines.length} typed segments · ${scene.calibrated?'calibrated footprint':'proportional preview'} · wall/opening heights illustrative. Furniture blocks mark positions, not product shapes.`:'Add room sections before choosing a view.'}</p>${scene?.issues.length?`<div class="structure-issues">${scene.issues.map(t=>`<p>${esc(t)}</p>`).join('')}</div>`:''}</div></section>

</div>

<details open>

<summary>Section checks</summary>

<div class="structure-checks">${d.sections.map(r=>`<article>

<strong>${esc(r.room_name)}</strong>

<span class="tag">${r.can_generate?'Inputs checked':'Needs review'}</span>

<ul>${r.checks.filter(c=>c.level!=='pass').map(c=>`<li>

<b>${c.level==='blocked'?'Fix':'Check'}:</b> ${esc(c.message)}</li>`).join('')||'<li>Saved inputs passed. Generated-image review still required.</li>'}</ul>

</article>`).join('')}</div>

</details>

<details open>

<summary>Shared connections</summary>

<div class="structure-connections">${d.connections.map(c=>`<p>

<strong>${esc(c.from)} ↔ ${esc(c.to)}</strong>

<br>${esc(c.constraint)} · ${esc(c.status)}</p>`).join('')||'<p>No shared connections recorded. Use Review symbols & connections to add them.</p>'}</div>

</details>

<details>

<summary>Automatic correction history</summary>${d.history.map(h=>`<p>${esc(new Date(h.created*1000).toLocaleString())} · ${h.repairs.length} wall correction(s) · ${h.undone?'Undone':'Saved'} · drawing ${h.before_revision} → ${h.after_revision}</p>`).join('')||'<p>No automatic repairs have been applied.</p>'}</details>

<p class="help">${esc(d.scope)}</p>`,button('Close','close'),'structure');

  if(!$('#review-workspace'))$('#modal').classList.add('structure-dialog');drawMap();draw3d();

 }

 function drawMap(){

  const svg=$('#structure-map');if(!svg)return;const a=A(session.aid),cam=cameraDraft||scene?.saved_camera;

  svg.innerHTML=`<image href="${url(enhancedView&&a.enhanced_reading_id?a.enhanced_reading_id:session.aid)}" width="${a.width}" height="${a.height}"/>`+(cam?`<line x1="${cam.position[0]*a.width}" y1="${cam.position[1]*a.height}" x2="${cam.target[0]*a.width}" y2="${cam.target[1]*a.height}" stroke="#db9f00" stroke-width="2"/>

<circle cx="${cam.position[0]*a.width}" cy="${cam.position[1]*a.height}" r="4" fill="#db9f00"/>

<circle cx="${cam.target[0]*a.width}" cy="${cam.target[1]*a.height}" r="3" fill="#296c72"/>`:'');

  svg.innerHTML+=(session.report.raster_geometry?[]:session.report.vision_report?.features||[]).map(f=>{const [x,y,w,h]=f.bbox;return `<g><rect x="${x*a.width}" y="${y*a.height}" width="${w*a.width}" height="${h*a.height}" fill="none" stroke="${f.kind==='space'?'#438477':'#c28f24'}" stroke-width="1" vector-effect="non-scaling-stroke"/><title>${esc(f.label+' · '+f.confidence+' confidence')}</title></g>`}).join('');

  svg.onpointerdown=e=>{

   if(!clickMode)return;const p=new DOMPoint(e.clientX,e.clientY).matrixTransform(svg.getScreenCTM().inverse());const q=[Math.max(0,Math.min(1,p.x/a.width)),Math.max(0,Math.min(1,p.y/a.height))];

   if(clickMode===1){cameraDraft={position:q,target:q,height:1.5};clickMode=2;$('#structure-camera-hint').textContent='Now click the viewing target.';drawMap()}

   else{cameraDraft.target=q;clickMode=0;$('#structure-camera-hint').textContent='View selected. Save camera view to use it for this section.';$('[data-structure="save-camera"]').disabled=false;drawMap()}

  };

  window.RasterReview?.attach(svg,session.report,async data=>{if(data.run){await api(route('reconstruct'));toast('Boundary tracing queued.');return}if(data.source){await api(route('source-panels'),{...data,revision:session.report.source_review?.revision||0})}else if(data.binding){await api(route('curve-binding'),{...data,fingerprint:session.report.curve_review.fingerprint})}else if(data.validation){await api(route('raster-validation'),{...data,fingerprint:session.report.raster_validation.fingerprint})}else await api(route('raster-correction'),{...data,revision:session.report.raster_revision,source_sha256:session.report.raster_geometry.source_sha256});await refresh(false);await load(true);toast('Boundary review saved. Both views updated.');});
 }

 function draw3d(){

  const c=$('#structure-3d');if(!c)return;const ctx=c.getContext('2d');ctx.clearRect(0,0,c.width,c.height);ctx.fillStyle='#f0efe9';ctx.fillRect(0,0,c.width,c.height);if(!scene)return;

  const yaw=rotation*Math.PI/180,co=Math.cos(yaw),si=Math.sin(yaw);
  const project=p=>[p[0]*co-p[1]*si,(p[0]*si+p[1]*co)*.5-p[2]];
  const projected=scene.surfaces.flatMap(f=>f.points.map(project));
  const extent=axis=>[Math.min(...projected.map(p=>p[axis])),Math.max(...projected.map(p=>p[axis]))];
  const [x0,x1]=projected.length?extent(0):[0,1],[y0,y1]=projected.length?extent(1):[0,1];
  const scale=Math.min((c.width-80)/Math.max(.01,x1-x0),(c.height-80)/Math.max(.01,y1-y0));
  const point=p=>{const [x,y]=project(p);return [c.width/2+(x-(x0+x1)/2)*scale,c.height/2+(y-(y0+y1)/2)*scale]};

  const surfaces=scene.surfaces.slice().sort((a,b)=>{const depth=f=>f.points.reduce((n,p)=>n+p[0]*si+p[1]*co+p[2]*.1,0)/f.points.length;return depth(a)-depth(b)});

  for(const f of surfaces){ctx.beginPath();f.points.map(point).forEach(([x,y],i)=>i?ctx.lineTo(x,y):ctx.moveTo(x,y));ctx.closePath();ctx.fillStyle=`rgba(${f.color.join(',')},${f.kind==='window'||f.kind==='sliding_door'?.62:1})`;ctx.fill();ctx.strokeStyle='#6c756a';ctx.lineWidth=.6;ctx.stroke()}

  c.onclick=event=>{const rect=c.getBoundingClientRect(),ratio=Math.min(rect.width/c.width,rect.height/c.height),x=(event.clientX-rect.left-(rect.width-c.width*ratio)/2)/ratio,y=(event.clientY-rect.top-(rect.height-c.height*ratio)/2)/ratio;for(const face of surfaces.slice().reverse()){const poly=face.points.map(point);let inside=false;for(let i=0,j=poly.length-1;i<poly.length;j=i++){const a=poly[i],b=poly[j];if((a[1]>y)!==(b[1]>y)&&x<(b[0]-a[0])*(y-a[1])/(b[1]-a[1])+a[0])inside=!inside}if(inside){window.RasterReview?.select(face.source_id);return}}};

  if(scene.camera){const a=point(scene.camera.position),b=point(scene.camera.target);ctx.strokeStyle='#c68c00';ctx.lineWidth=3;ctx.beginPath();ctx.moveTo(...a);ctx.lineTo(...b);ctx.stroke()}

  if(!scene.lines.length){ctx.fillStyle='#485246';ctx.font='18px sans-serif';ctx.fillText(session.report.raster_active===false?'No wall draft — review source type and plan panels':'No typed architecture yet — trace the original plan',50,45)}

 }

 document.addEventListener('click',async e=>{

  if(e.target.closest('[data-action="structure-check"]'))return openStructureCheck();

  const b=e.target.closest('[data-structure]');if(!b||!session)return;b.disabled=true;

  try{

   const action=b.dataset.structure;

   if(action==='fit-source')return window.RasterReview?.fit();

   if(action==='close'){session=null;window.StructureReview.closed=true;$('#review-workspace')?.remove();renderMain();return $('#modal').close()}

   if(action==='blocks')return window.openFurnitureBlocks(session.pid,viewRoom);

   if(action==='refresh')return await load();

   if(action==='cancel-vision'){if(visualJob)await api(`/api/jobs/${visualJob}/cancel`);return}

   if(action==='vision'){

    const j=await api(route('read-visual'),{section_ids:viewRoom?[viewRoom]:[]});visualJob=j.id;

    const context={...session};render();

    const poll=async()=>{

     await refresh(false);const job=state.jobs[j.id];

     if(!job)return;

     if(['completed','failed','cancelled'].includes(job.status)){

      visualJob=null;if(session?.aid===context.aid&&($('#modal').open||$('#review-workspace')))await load();

      toast(job.status==='completed'?'Visual reading ready for review.':job.error||job.stage);return;

     }

     const label=$('#structure-vision-status');if(label)label.textContent=job.stage+' · '+Math.floor(Date.now()/1000-(job.started||job.created))+'s elapsed';

     setTimeout(()=>poll().catch(err=>{visualJob=null;toast(err.message)}),2000);

    };setTimeout(()=>poll().catch(err=>{visualJob=null;toast(err.message)}),1000);return;

   }

   if(action==='import-vision'){

    await api(route('import-visual'),{revision:session.report.study_revision});await refresh(true);await load();toast('Predictions added as unconfirmed symbols. Review them before rendering.');return;

   }

   if(action==='repair'||action==='undo'){const res=await api(route(action==='repair'?'repair-structure':'undo-structure'),{fingerprint:session.report.fingerprint});await refresh(true);await load();toast(res.message||'No safe corrections needed.');return}

   if(action==='camera-editor')return openCameraView(session.pid,viewRoom);

   if(action==='camera'){clickMode=1;cameraDraft=null;$('#structure-camera-hint').textContent='Click a camera position inside the selected section.';return}

   if(action==='save-camera'){const r=rooms().find(r=>r.id===viewRoom);await api(route('floor-camera'),{room_id:viewRoom,revision:r.revision,...cameraDraft});await refresh(true);await load();toast('Shared-floor camera saved.');return}

   planId=session.aid;

   if(action==='study'){await window.openPlanStudy();return}

   if(action==='drawing'){await window.openDrawingEditor({full:true});return}

   if(action==='areas'){await window.openPlanAreas();return}

  }catch(err){toast(err.message)}finally{b.disabled=false}

 });

 document.addEventListener('change',async e=>{if(e.target.id==='review-diagnostic-draft'){diagnosticDraft=e.target.checked;try{await loadScene();render()}catch(err){toast(err.message)}return}if(e.target.id==='detection-enhanced'){enhancedView=e.target.checked;drawMap();return}if(e.target.id==='structure-room'){viewRoom=e.target.value;try{await loadScene();render()}catch(err){toast(err.message)}}});

 document.addEventListener('input',e=>{if(e.target.id==='structure-rotate'){rotation=Number(e.target.value);draw3d()}});



 window.StructureReview={closed:false,

  preserve(){return tab==='plan'&&session?.pid===pid&&session?.aid===planId&&!!$('#review-workspace')},

  present(title,body,footer){

   if(tab!=='plan')return false;

   const old=$('#structure-map')?.getAttribute('viewBox'),view=$('#review-workspace')?.dataset.view||'split';

   $('#modal').open&&$('#modal').close();modalType='';

   $('#main').innerHTML=`<section id="review-workspace" data-view="${view}"><header class="review-top"><nav aria-label="Plan workflow"><button class="btn small" data-action="upload-plan">1 Upload</button><strong>2 Review & 3D</strong><button class="btn small" data-action="tab" data-tab="images">3 Images & Video</button></nav><div class="review-view-modes"><button class="btn small" data-local-setup>Setup</button><button class="btn small" data-review-view="2d">2D</button><button class="btn small" data-review-view="3d" ${!scene?'disabled':''}>3D</button><button class="btn small" data-review-view="split">Split</button></div></header><div class="review-content">${body}</div></section>`;

   const content=$('.review-content'),workspace=$('.structure-workspace'),issues=$('.review-issue-list');

   const grid=document.createElement('div');grid.className='review-grid';content.insertBefore(grid,issues);grid.append(workspace,issues);

   content.querySelectorAll(':scope > details').forEach(el=>{el.open=false});

   if(old)$('#structure-map')?.setAttribute('viewBox',old);

   return true;

  },

  update(){

   if(!this.preserve()||$('#modal').open)return;

   const job=Object.values(state.jobs).find(j=>j.plan_id===planId&&['vision_study','raster_reconstruction','plan_setup'].includes(j.kind)&&['running','queued','waiting'].includes(j.status));

   const status=$('#structure-vision-status');if(status){const latest=job||Object.values(state.jobs).filter(j=>j.plan_id===planId).sort((a,b)=>b.created-a.created)[0];status.innerHTML=latest?jobMarkup(latest,true):''}

   if(!session.loading&&session.stateKey!==reviewStateKey())load().catch(err=>toast(err.message));

  }

 };

 document.addEventListener('click',async e=>{

  const mode=e.target.closest('[data-review-view]');if(mode){$('#review-workspace').dataset.view=mode.dataset.reviewView;return}

  const focus=e.target.closest('[data-review-focus]');

  if(focus){const issue=session.report.vision_report.review_issues.find(i=>i.id===focus.dataset.reviewFocus),a=A(session.aid),svg=$('#structure-map');

   drawMap();const [x,y,w,h]=issue.bbox;svg.innerHTML+=`<rect class="review-highlight" x="${x*a.width}" y="${y*a.height}" width="${w*a.width}" height="${h*a.height}" fill="#e8a72d22" stroke="#ac6410" stroke-width="3" vector-effect="non-scaling-stroke"/>`;return}

  const b=e.target.closest('[data-review-decision]');if(!b||!session)return;b.disabled=true;

  try{const r=session.report.vision_report;await api(route('review-decision'),{revision:session.report.review_revision,source_sha256:r.source_sha256,pipeline_key:r.pipeline_key,issue_id:b.dataset.issue,action:b.dataset.reviewDecision,element_id:b.dataset.element});await load();toast('Review saved. Original observations preserved.')}catch(err){toast(err.message)}finally{b.disabled=false}

 });

})();
