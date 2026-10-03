'use strict';
function imageRevisionCurrent(a,r){return a.input_revision===r.revision||(r.edit_revision_equivalents||[]).includes(a.input_revision)}
(() => {
 let draft=null,previewTimer=null,previewSequence=0;
 function preparePreview(){
  clearTimeout(previewTimer);const target=$('#scene-prepared');if(!target)return;
  const sequence=++previewSequence,project=draft.project,room=draft.room;
  target.textContent='Preparing your edit instructions…';
  previewTimer=setTimeout(async()=>{
   try{const result=await api(`/api/projects/${project}/rooms/${room}/prepare-edit`,{instruction:$('#scene-instruction').value,mode:$('#scene-mode').value});
    if(sequence!==previewSequence||modalType!=='scene-control')return;
    $('#scene-prepared').textContent=result.prompt;
   }catch(err){if(sequence===previewSequence&&$('#scene-prepared'))$('#scene-prepared').textContent=err.message}
  },400);
 }
 window.augmentSceneControl=()=>{
  if(tab!=='references'||!R())return;
  const target=document.querySelector('[data-action="room-direction"]');
  if(!target||document.querySelector('[data-scene="open"]'))return;
  const b=document.createElement('button');b.type='button';b.className='btn small ghost';b.dataset.scene='open';
  const mode=R().scene_control?.mode||'reference';
  b.textContent=mode==='region'?'Protected area ✓':mode==='structure'?'Room structure guidance ✓':'Consistency controls';
  target.before(b);
 };
 function controls(){
  const local=$('#scene-mode').value==='region',free=$('#scene-mode').value==='reference';
  $('#scene-detail').hidden=free;$('#scene-area-help').hidden=!local;
  $('#scene-map').classList.toggle('drawing-enabled',local);
  $('#scene-mode-note').textContent=free?'The model can redraw the full scene. This mode does not protect the background.':local?'Only the selected area can change. The surrounding image is copied from the master and checked pixel by pixel. Include the old object, its new position and affected shadows.':'Start from the master image’s structure with less noise. This reduces freedom to redesign, but every object still needs review.';
  draw();preparePreview();
 }
 function draw(){
  const box=draft.region,r=$('#scene-selection');const poly=$('#scene-outline');if(poly)poly.innerHTML=draft.mask_polygon?.length?`<polygon points="${draft.mask_polygon.map(p=>[p[0]*1920,p[1]*1080].join(',')).join(' ')}" fill="#eebc3044" stroke="#eebc30" stroke-width="3"/>`:'';
  r.hidden=!box||$('#scene-mode').value!=='region';
  if(box)Object.assign(r.style,{left:box[0]*100+'%',top:box[1]*100+'%',width:box[2]*100+'%',height:box[3]*100+'%'});
 }
 window.openSceneControls=function(sourceId){
  const room=R(),c=room.scene_control||{mode:'reference'};
  draft={project:pid,room:room.id,revision:room.revision,edit_revision:room.edit_revision||0,...JSON.parse(JSON.stringify(c))};
  const ids=[room.anchor_id,...[...room.images].reverse().filter(id=>A(id)?.kind==='image')].filter((id,i,a)=>id&&a.indexOf(id)===i);
  draft.source_id=sourceId||draft.source_id||room.anchor_id||ids[0];
  showModal('Revise image · '+esc(room.name),`<p>Select an object reference, preview its edit region, then generate a child version.</p><div class="scene-controls"><section><div class="scene-preview" id="scene-map"><img id="scene-master" src="${url(draft.source_id)}" alt="Master image for protected editing" draggable="false"><div id="scene-selection" hidden></div><svg id="scene-outline" viewBox="0 0 1920 1080" aria-label="Object mask preview"></svg></div><p id="scene-area-help" class="help">Drag a rectangle over the area that may change. Everything outside it stays as it is in this master image.</p><div class="actions"><button type="button" class="btn small" data-scene="rectangle">Rectangle</button><button type="button" class="btn small" data-scene="polygon">Object outline</button><button type="button" class="btn small ghost" data-scene="clear">Clear region</button></div><p class="help" id="scene-draw-help">Drag a rectangle, or choose Object outline and click around the object. Include its old silhouette and affected shadows.</p></section><aside><label class="field"><span>Master image</span><select id="scene-source">${ids.map(id=>`<option value="${id}" ${id===draft.source_id?'selected':''}>${id===room.anchor_id?'Original room reference':`Version ${room.images.indexOf(id)+1} · ${A(id)?.status==='approved'?'approved':A(id)?.status==='rejected'?'needs changes':'for review'}`}</option>`).join('')}</select></label><label class="field"><span>How much can change?</span><select id="scene-mode"><option value="reference" ${c.mode==='reference'?'selected':''}>Free edit · reference guidance</option><option value="structure" ${c.mode==='structure'?'selected':''}>Keep room structure</option><option value="region" ${c.mode==='region'?'selected':''}>Edit selected area only</option></select></label><p class="help" id="scene-mode-note"></p><div id="scene-detail"><label class="field"><span>Edit strength</span><select id="scene-strength">${[[.25,'Very restrained'],[.5,'Restrained'],[.75,'Moderate'],[1,'Full replacement']].map(([v,n])=>`<option value="${v}" ${v===(c.denoise||.5)?'selected':''}>${n}</option>`).join('')}</select></label><label class="field"><span>What should change?</span><textarea id="scene-instruction" rows="5" placeholder="e.g. Change only this chair’s fabric to plain cream linen; keep its frame and position.">${esc(c.instruction||'')}</textarea></label><p class="help">Protected editing requires a 1920 × 1080 master. No enlargement. Use full-room mode for sunlight changes; a local edit keeps the surrounding lighting.</p></div><p class="help">Edit settings leave previous versions and approvals unchanged. Scene, camera and product changes still invalidate affected images.</p></aside></div>`,`<span class="help" id="scene-status">Master references remain unchanged</span><button type="button" class="btn ghost" data-action="close-modal">Cancel</button><button type="button" class="btn" data-scene="save">Save edit</button><button type="button" class="btn primary" data-scene="generate">Generate child version</button>`,'scene-control');
  $('#scene-detail').insertAdjacentHTML('afterbegin',`<label class="field"><span>Product reference for this edit</span><select id="scene-reference"><option value="">All assigned references</option>${room.references.filter(id=>A(id)?.enabled!==false).map(id=>`<option value="${id}" ${id===c.reference_id?'selected':''}>${esc(A(id)?.category||'Reference')}</option>`).join('')}</select><small>Product assignments stay saved.</small></label><div class="scene-ref-preview" id="scene-ref-preview"><img id="scene-ref-image" alt="Exact selected product reference"><div id="scene-ref-crop"></div></div><p id="scene-ref-info" class="help"></p><button type="button" class="btn small" data-scene="crop">Isolate reference · drag crop</button><button type="button" class="btn small ghost" data-scene="uncrop">Full reference</button>`);
  $('#scene-detail').insertAdjacentHTML('beforeend',`<details id="scene-advanced"><summary>Advanced</summary><label class="field"><span>Reference crop · x, y, width, height in pixels</span><input id="scene-crop-pixels" placeholder="Full reference"></label><label class="field"><span><input id="scene-masked" type="checkbox" ${c.masked_context?'checked':''}> Object mask in sampler and blend</span><small>Native context crop. Reference conditioning is global; no guaranteed spatial binding.</small></label><label class="field"><span><input id="scene-context" type="checkbox" ${c.context_crop?'checked':''}> Native context crop</span><small>Advanced: regenerate a local image crop, then composite the selected region. This does not use a sampler mask.</small></label></details>`);
  const instruction=$('#scene-instruction');instruction.rows=4;instruction.maxLength=2500;instruction.placeholder='e.g. Replace this chair with the reference. Keep the room the same.';
  instruction.closest('label').insertAdjacentHTML('beforeend','<small>Use normal language. The edit area, references and preservation instructions are added automatically.</small>');
  instruction.closest('label').insertAdjacentHTML('afterend','<details class="prepared-edit"><summary>Prepared instructions · automatic</summary><pre id="scene-prepared"></pre><p class="help">Your wording stays unchanged. This adds known scene context; it does not infer missing dimensions.</p></details>');
  instruction.oninput=preparePreview;
  $('#scene-advanced').append($('#scene-strength').closest('label'),document.querySelector('.prepared-edit'));
  const el=$('#scene-map');let start=null;draft.drawMode='rectangle';
  function reference(){const a=A($('#scene-reference').value);$('#scene-ref-image').src=a?url(a.id):'';$('#scene-ref-info').textContent=a?[(a.display_name||a.category),a.source_product?.dimensions||room.block_layout?.items?.find(i=>i.asset_id===a.id)?.prompt||'Dimensions not supplied'].join(' · '):'Choose the exact product image.';const c=draft.reference_crop;$('#scene-ref-crop').hidden=!c;if(c)Object.assign($('#scene-ref-crop').style,{left:c[0]*100+'%',top:c[1]*100+'%',width:c[2]*100+'%',height:c[3]*100+'%'});}
  $('#scene-reference').onchange=()=>{draft.reference_crop=null;$('#scene-crop-pixels').value='';reference()};reference();
  if(draft.reference_crop){const a=A($('#scene-reference').value);$('#scene-crop-pixels').value=draft.reference_crop.map((v,i)=>Math.round(v*(i%2?a.height:a.width))).join(', ')}
  $('#scene-crop-pixels').oninput=$('#scene-crop-pixels').onchange=e=>{const a=A($('#scene-reference').value),p=e.target.value.split(',').map(Number);if(a&&p.length===4&&p.every(Number.isFinite)){draft.reference_crop=p.map((v,i)=>v/(i%2?a.height:a.width));reference()}};
  const ref=$('#scene-ref-preview');let refStart=null;const refPoint=e=>{const b=ref.getBoundingClientRect();return [Math.max(0,Math.min(1,(e.clientX-b.left)/b.width)),Math.max(0,Math.min(1,(e.clientY-b.top)/b.height))]};
  ref.onpointerdown=e=>{if(!draft.cropMode)return;e.preventDefault();refStart=refPoint(e);ref.setPointerCapture(e.pointerId)};
  ref.onpointermove=e=>{if(!refStart)return;const end=refPoint(e);draft.reference_crop=[Math.min(refStart[0],end[0]),Math.min(refStart[1],end[1]),Math.abs(end[0]-refStart[0]),Math.abs(end[1]-refStart[1])];reference()};
  ref.onpointerup=e=>{if(!refStart)return;ref.onpointermove(e);refStart=null;draft.cropMode=false;const a=A($('#scene-reference').value);$('#scene-crop-pixels').value=draft.reference_crop.map((v,i)=>Math.round(v*(i%2?a.height:a.width))).join(', ');ref.releasePointerCapture(e.pointerId)};
  const point=e=>{const b=el.getBoundingClientRect();return [Math.max(0,Math.min(1,(e.clientX-b.left)/b.width)),Math.max(0,Math.min(1,(e.clientY-b.top)/b.height))]};
  el.onpointerdown=e=>{if($('#scene-mode').value!=='region')return;e.preventDefault();if(draft.drawMode==='polygon'){const p=point(e);draft.mask_polygon=(draft.mask_polygon||[]).concat([p]);const xs=draft.mask_polygon.map(p=>p[0]),ys=draft.mask_polygon.map(p=>p[1]);const x=Math.max(0,Math.min(...xs)-8/1920),y=Math.max(0,Math.min(...ys)-8/1080);draft.region=[x,y,Math.min(1,Math.max(...xs)+8/1920)-x,Math.min(1,Math.max(...ys)+8/1080)-y];draw();return}draft.mask_polygon=null;start=point(e);el.setPointerCapture(e.pointerId)};
  el.onpointermove=e=>{if(!start)return;const end=point(e);draft.region=[Math.min(start[0],end[0]),Math.min(start[1],end[1]),Math.abs(end[0]-start[0]),Math.abs(end[1]-start[1])];draw()};
  el.onpointerup=e=>{if(!start)return;el.onpointermove(e);start=null;el.releasePointerCapture(e.pointerId)};
  el.onpointercancel=()=>{start=null};
  $('#scene-mode').onchange=controls;
  $('#scene-source').onchange=e=>{draft.source_id=e.target.value;draft.region=null;$('#scene-master').src=url(draft.source_id);draw()};
  controls();
 };
 document.addEventListener('click',async e=>{
  const b=e.target.closest('[data-scene]');if(!b)return;
  if(b.dataset.scene==='open'){openSceneControls(b.dataset.source);return}
  if(modalType!=='scene-control'||!draft)return;
  if(b.dataset.scene==='clear'){draft.region=null;draft.mask_polygon=null;draw();return}
  if(['rectangle','polygon'].includes(b.dataset.scene)){draft.drawMode=b.dataset.scene;draft.mask_polygon=null;$('#scene-draw-help').textContent=b.dataset.scene==='polygon'?'Click around the object. The closed outline is the mask; a small blend margin is included.':'Drag the allowed edit rectangle.';draw();return}
  if(b.dataset.scene==='crop'){draft.cropMode=true;$('#scene-ref-info').textContent='Drag over the artwork itself. Its original pixels and aspect are retained.';return}
  if(b.dataset.scene==='uncrop'){draft.reference_crop=null;$('#scene-crop-pixels').value='';$('#scene-ref-crop').hidden=true;return}
  if(['save','generate'].includes(b.dataset.scene)){
   b.disabled=true;try{const cropText=$('#scene-crop-pixels').value.trim();if(cropText){const a=A($('#scene-reference').value),coords=cropText.split(',').map(Number);if(!a||coords.length!==4||!coords.every(Number.isFinite))throw Error('Use four crop coordinates in pixels.');draft.reference_crop=coords.map((v,i)=>v/(i%2?a.height:a.width))}const body={...draft,mode:$('#scene-mode').value,source_id:$('#scene-source').value,denoise:Number($('#scene-strength').value),instruction:$('#scene-instruction').value,reference_id:$('#scene-reference').value,context_crop:$('#scene-context').checked,masked_context:$('#scene-masked').checked};
    await api(`/api/projects/${draft.project}/rooms/${draft.room}/scene-control`,body);$('#modal').close();if(b.dataset.scene==='generate'){const job=await api(`/api/projects/${draft.project}/rooms/${draft.room}/generate-image`,{view_id:WorkspaceSelection.cameraId});openGenerationProgress(job)}await refresh(true);toast('Edit saved. Previous versions remain available.');
   }catch(err){$('#scene-status').textContent=err.message;b.disabled=false}
  }
 });
})();

(() => {
 document.addEventListener('click',async e=>{
  const b=e.target.closest('[data-revision-compare],[data-revision-keep],[data-revision-discard]');if(!b)return;
  if(b.dataset.revisionKeep||b.dataset.revisionDiscard){
   const id=b.dataset.revisionKeep||b.dataset.revisionDiscard,a=A(id);b.disabled=true;
   try{await api(`/api/projects/${pid}/rooms/${a.room_id}/${b.dataset.revisionKeep?'keep-image':'reject-image'}`,{asset_id:id,reason:'Discarded in revision comparison; preserved in history.'});$('#modal').close();await refresh(true);toast(b.dataset.revisionKeep?'Kept for review; not approved.':'Discarded candidate remains in history.')}catch(err){toast(err.message);b.disabled=false}return;
  }
  try{await openRevisionComparison(b.dataset.revisionCompare)}catch(err){toast(err.message)}
 });
})();
