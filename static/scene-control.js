'use strict';
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
  const box=draft.region,r=$('#scene-selection');
  r.hidden=!box||$('#scene-mode').value!=='region';
  if(box)Object.assign(r.style,{left:box[0]*100+'%',top:box[1]*100+'%',width:box[2]*100+'%',height:box[3]*100+'%'});
 }
 window.openSceneControls=function(){
  const room=R(),c=room.scene_control||{mode:'reference'};
  draft={project:pid,room:room.id,revision:room.revision,...JSON.parse(JSON.stringify(c))};
  const ids=[room.anchor_id,...[...room.images].reverse().filter(id=>A(id)?.kind==='image')].filter((id,i,a)=>id&&a.indexOf(id)===i);
  draft.source_id=draft.source_id||room.anchor_id||ids[0];
  showModal('Scene consistency · '+esc(room.name),`<p>Choose one master view. FLUX edits from this image; LTX receives the exact result you approve, with the same saved scene settings.</p><div class="scene-controls"><section><div class="scene-preview" id="scene-map"><img id="scene-master" src="${url(draft.source_id)}" alt="Master image for protected editing" draggable="false"><div id="scene-selection" hidden></div></div><p id="scene-area-help" class="help">Drag a rectangle over the area that may change. Everything outside it stays as it is in this master image.</p><button type="button" class="btn small ghost" data-scene="clear">Clear selected area</button></section><aside><label class="field"><span>Master image</span><select id="scene-source">${ids.map(id=>`<option value="${id}" ${id===draft.source_id?'selected':''}>${id===room.anchor_id?'Original room reference':A(id)?.status==='approved'?'Approved image':A(id)?.status==='rejected'?'Generated image · needs changes':'Generated image · awaiting review'} · ${esc(A(id)?.display_name||A(id)?.name||id)}</option>`).join('')}</select></label><label class="field"><span>How much can change?</span><select id="scene-mode"><option value="reference" ${c.mode==='reference'?'selected':''}>Free edit · reference guidance</option><option value="structure" ${c.mode==='structure'?'selected':''}>Keep room structure</option><option value="region" ${c.mode==='region'?'selected':''}>Edit selected area only</option></select></label><p class="help" id="scene-mode-note"></p><div id="scene-detail"><label class="field"><span>Edit strength</span><select id="scene-strength">${[[.25,'Very restrained'],[.5,'Restrained'],[.75,'Moderate'],[1,'Full replacement']].map(([v,n])=>`<option value="${v}" ${v===(c.denoise||.5)?'selected':''}>${n}</option>`).join('')}</select></label><label class="field"><span>What should change?</span><textarea id="scene-instruction" rows="5" placeholder="e.g. Change only this chair’s fabric to plain cream linen; keep its frame and position.">${esc(c.instruction||'')}</textarea></label><p class="help">Protected editing requires a 1920 × 1080 master. No enlargement. Use full-room mode for sunlight changes; a local edit keeps the surrounding lighting.</p></div><p class="help">Changes clear image approval. Video remains locked until you approve a current result. These controls do not create a shared 3D model.</p></aside></div>`,`<span class="help" id="scene-status">Master references remain unchanged</span><button type="button" class="btn ghost" data-action="close-modal">Cancel</button><button type="button" class="btn primary" data-scene="save">Save controls</button>`,'scene-control');
  $('#scene-detail').insertAdjacentHTML('afterbegin',`<label class="field"><span>Product reference for this edit</span><select id="scene-reference"><option value="">All assigned references</option>${room.references.filter(id=>A(id)?.enabled!==false).map(id=>`<option value="${id}" ${id===c.reference_id?'selected':''}>${esc(A(id)?.category||'Reference')}</option>`).join('')}</select><small>Only controls this edit. Product assignments stay saved.</small></label>`);
  $('#scene-detail').insertAdjacentHTML('beforeend',`<label class="field"><span><input id="scene-context" type="checkbox" ${c.context_crop?'checked':''}> Native context crop</span><small>Advanced: regenerate a local image crop, then composite the selected region. This does not use a sampler mask.</small></label>`);
  const instruction=$('#scene-instruction');instruction.rows=4;instruction.maxLength=2500;instruction.placeholder='e.g. Replace this chair with the reference. Keep the room the same.';
  instruction.closest('label').insertAdjacentHTML('beforeend','<small>Use normal language. The edit area, references and preservation instructions are added automatically.</small>');
  instruction.closest('label').insertAdjacentHTML('afterend','<details class="prepared-edit"><summary>Prepared instructions · automatic</summary><pre id="scene-prepared"></pre><p class="help">Your wording stays unchanged. This adds known scene context; it does not infer missing dimensions.</p></details>');
  instruction.oninput=preparePreview;
  const el=$('#scene-map');let start=null;
  const point=e=>{const b=el.getBoundingClientRect();return [Math.max(0,Math.min(1,(e.clientX-b.left)/b.width)),Math.max(0,Math.min(1,(e.clientY-b.top)/b.height))]};
  el.onpointerdown=e=>{if($('#scene-mode').value!=='region')return;e.preventDefault();start=point(e);el.setPointerCapture(e.pointerId)};
  el.onpointermove=e=>{if(!start)return;const end=point(e);draft.region=[Math.min(start[0],end[0]),Math.min(start[1],end[1]),Math.abs(end[0]-start[0]),Math.abs(end[1]-start[1])];draw()};
  el.onpointerup=e=>{if(!start)return;el.onpointermove(e);start=null;el.releasePointerCapture(e.pointerId)};
  el.onpointercancel=()=>{start=null};
  $('#scene-mode').onchange=controls;
  $('#scene-source').onchange=e=>{draft.source_id=e.target.value;draft.region=null;$('#scene-master').src=url(draft.source_id);draw()};
  controls();
 };
 document.addEventListener('click',async e=>{
  const b=e.target.closest('[data-scene]');if(!b)return;
  if(b.dataset.scene==='open'){openSceneControls();return}
  if(modalType!=='scene-control'||!draft)return;
  if(b.dataset.scene==='clear'){draft.region=null;draw();return}
  if(b.dataset.scene==='save'){
   b.disabled=true;try{const body={...draft,mode:$('#scene-mode').value,source_id:$('#scene-source').value,denoise:Number($('#scene-strength').value),instruction:$('#scene-instruction').value,reference_id:$('#scene-reference').value,context_crop:$('#scene-context').checked};
    await api(`/api/projects/${draft.project}/rooms/${draft.room}/scene-control`,body);$('#modal').close();await refresh(true);toast('Consistency controls saved. Review the next image before video.');
   }catch(err){$('#scene-status').textContent=err.message;b.disabled=false}
  }
 });
})();
