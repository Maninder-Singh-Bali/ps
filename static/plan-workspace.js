'use strict';
// A single main-page host for plan, furniture, walls and camera editing.
(() => {
 let mountedKey=null,mode='blocks',opening=0,mountReady=Promise.resolve();const hiddenFloors=new Set();
 const key=()=>`${pid}:${planId}`;
 const candidates=()=>P()?.rooms.filter(r=>r.plan_id===planId&&r.bbox&&(tab!=='references'||!A(planId)?.construction_selection?.confirmed||r.floor===A(planId).construction_selection.floor))||[];
 const pending=()=>mode==='camera'?window.CameraEditor?.pending():window.FurnitureEditor?.pending();
 function planView(floor=null){const a=A(planId),rs=candidates().filter(r=>!floor||r.floor===floor);if(!rs.length)return [0,0,a.width,a.height];const x=Math.min(...rs.map(r=>r.bbox[0]))*a.width,y=Math.min(...rs.map(r=>r.bbox[1]))*a.height,right=Math.max(...rs.map(r=>r.bbox[0]+r.bbox[2]))*a.width,bottom=Math.max(...rs.map(r=>r.bbox[1]+r.bbox[3]))*a.height,pad=Math.min(a.width,a.height)*.035;return [x-pad,y-pad,right-x+pad*2,bottom-y+pad*2]}
 function canRender(){return ['plan','references'].includes(tab)&&!drawMode&&!!planId&&candidates().length>0}
 function sectionDetails(){const r=R();if(!r)return '';return `<details class="inline-section-details"><summary>Section details</summary><form id="room-form" class="room-edit"><label class="field"><span>Name</span><input name="name" value="${esc(r.name)}" required></label><label class="field"><span>Floor</span><input name="floor" value="${esc(r.floor)}" required></label><label class="field"><span>Type</span><select name="kind">${['room','circulation','outdoor'].map(k=>`<option ${k===r.kind?'selected':''}>${k}</option>`).join('')}</select></label><div class="actions">${btn('Save','save-room','','small')}${btn('Remove','delete-room','','small danger')}</div></form></details>`}
 const floorName=f=>f==='Lower floor'?'Ground floor':f==='Upper floor'?'First floor':f;
 function floorGroups(){return [...new Set(candidates().map(r=>r.floor))].map(f=>`<section class="floor-section-group"><div class="floor-group-heading"><button type="button" class="floor-section-heading ${R()?.floor===f?'active':''}" data-workspace-floor="${esc(f)}" aria-pressed="${R()?.floor===f}">${esc(floorName(f))}<span>${candidates().filter(r=>r.floor===f).length}</span></button><button type="button" class="floor-visibility" data-floor-visibility="${esc(f)}" aria-label="${hiddenFloors.has(f)?'Show':'Hide'} ${esc(floorName(f))}" title="${hiddenFloors.has(f)?'Show':'Hide'} ${esc(floorName(f))}"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12Z"/><circle cx="12" cy="12" r="3"/>${hiddenFloors.has(f)?'<path d="M3 3l18 18"/>':''}</svg></button></div>${candidates().filter(r=>r.floor===f).map(r=>`<button type="button" class="floor-room ${r.id===rid?'selected':''}" data-action="room" data-id="${r.id}">${esc(r.name)}</button>`).join('')}</section>`).join('')}
 function markup(){
  if(!candidates().some(r=>r.id===rid))rid=candidates()[0].id;
  return `<div class="inline-plan-heading"><h1>Furnish</h1><select id="plan-select" class="control" aria-label="Floor plan page">${P().floor_plans.map((id,i)=>`<option value="${id}" ${id===planId?'selected':''}>Page ${i+1} · ${esc(A(id).display_name||A(id).name)}</option>`).join('')}</select><div class="actions">${tab==='references'?'<button class="btn small" data-surfaces-open>Surfaces</button>':btn('Select area to construct','construction-area','','small')}${btn('Upload plan','upload-plan','','small')}<details class="inline-more"><summary class="btn small">Advanced</summary><div>${btn('Area & sections','plan-areas','','small')}${btn('Detect objects','structure-check','','small')}${btn('North & sunlight','refine-drawing','','small')}${btn(A(planId)?.construction_selection?.confirmed?'Confirm selected shell':P().map_confirmed?'Map confirmed ✓':'Confirm map','confirm-map','','small')}</div></details></div></div><div class="inline-plan-grid"><section id="plan-editor-inline" class="panel" aria-label="Plan editing workspace"><div class="empty">Building 3D from the plan…</div></section><aside class="panel inline-sections"><div class="panel-head"><h2>Sections</h2>${btn('+','add-room','aria-label="Add section"','small')}</div><div id="inline-room-list" class="room-list">${floorGroups()}</div><div id="inline-section-details">${sectionDetails()}</div></aside></div>`;
 }
 function syncSections(){
  window.WorkspaceSelection?.remember();
  const list=$('#inline-room-list');if(!list)return;
  const signature=JSON.stringify([rid,[...hiddenFloors],P().rooms.map(r=>[r.id,r.name,r.floor,r.kind,!!r.bbox])]);
  if(list.dataset.signature!==signature){list.innerHTML=floorGroups();list.dataset.signature=signature;if(!$('#inline-section-details')?.contains(document.activeElement))$('#inline-section-details').innerHTML=sectionDetails()}
 }
 function preserve(){if(!canRender()||mountedKey!==key()||!$('#plan-editor-inline'))return false;const editorId=mode==='blocks'?window.FurnitureEditor?.roomId():rid;if(editorId&&!P().rooms.some(r=>r.id===editorId))return false;syncSections();return true}
 function reset(){if(mountedKey!==null){window.FurnitureEditor?.dispose();window.CameraEditor?.dispose();if(!$('#modal').open&&['blocks','camera'].includes(modalType))modalType=''}mountedKey=null;opening++;document.body.classList.remove('inline-plan-active')}
 function mount(){mountReady=mountEditor();return mountReady;}
 async function mountEditor(){
  if(!canRender()||!$('#plan-editor-inline'))return;
  mountedKey=key();document.body.classList.add('inline-plan-active');mode=currentWorkspaceStage()==='cameras'?'camera':'blocks';const ticket=++opening;
  try{await (mode==='camera'?openCameraView:openFurnitureBlocks)(pid,rid,{inline:true,view:planView(R()?.floor)})}catch(err){if(ticket===opening){$('#plan-editor-inline').innerHTML=`<div class="empty">${esc(err.message)} ${btn('Retry','furniture-blocks','','small')}</div>`;toast(err.message)}}
 }
 function show(title,body,footer,type){
  const host=$('#plan-editor-inline');if(!host||!['plan','references'].includes(tab)||!['blocks','camera'].includes(type))return false;
  mode=type;modalType=type;host.dataset.mode=type;const heading=document.querySelector('.inline-plan-heading h1');if(heading)heading.textContent=type==='camera'?'Cameras':'Furnish';window.setWorkflowHighlight?.(currentWorkspaceStage());
  host.innerHTML=`<div class="inline-editor-top"></div><div class="inline-editor-body">${body}</div><div class="inline-editor-footer">${footer}</div>`;
  const top=host.querySelector('.inline-editor-top');
  // The shared workflow bar owns navigation in the inline workspace.
  host.querySelector('.workspace-modes')?.remove();
  const floor=document.createElement('select');floor.id='workspace-floor';floor.className='control';floor.setAttribute('aria-label','Active floor');floor.innerHTML=[...new Set(candidates().map(r=>r.floor))].map(f=>`<option value="${esc(f)}" ${f===R()?.floor?'selected':''}>${esc(floorName(f))}</option>`).join('');top.append(floor);
  const save=host.querySelector('[data-block="save"],[data-camera="save"]');if(save){save.classList.add('primary');top.append(save)}
  host.querySelector('[data-block="close"],[data-camera="close"]')?.remove();host.querySelector('.inline-editor-footer')?.remove();
  const toolbar=host.querySelector('.block-toolbar');if(toolbar){
   toolbar.querySelectorAll('[data-block="library"],[data-block="add"],[data-block="propose"],[data-block="suggest"],[data-block="check"]').forEach(el=>el.remove());
   host.querySelector('.block-structure-status')?.remove();
   top.insertBefore(toolbar,save||null);
  }
  const inspector=host.querySelector('.block-inspector');if(inspector){
   const feedback=inspector.querySelector('#block-feedback');if(feedback){feedback.classList.add('inline-placement-feedback');host.querySelector('.block-left-panel')?.append(feedback)}
   const review=inspector.querySelector('.block-review');if(review){review.lastChild.textContent=' Placement checked';top.insertBefore(review,save||null)}
   const dock=host.querySelector('.block-left-panel'),props=inspector.querySelector('.block-object-properties'),transform=inspector.querySelector('.block-transform-panel'),wall=inspector.querySelector('#block-wall-properties');
   const controls=document.createElement('div');controls.className='inline-selection-controls';
   const selected=inspector.querySelector('.selected-furniture-inspector');if(selected)controls.append(selected);
   if(wall)controls.append(wall);
   const stair=props?.querySelector('#block-kind')?.value==='stair';
   if(transform&&!stair)controls.append(transform);else transform?.remove();
   if(props?.querySelector('input')&&!stair)controls.append(props);else props?.remove();
   dock.prepend(controls);
   for(const el of [...inspector.children])if(!el.matches('.block-model-panel'))el.hidden=true;
  }
  const map=host.querySelector('.block-map-wrap');if(map){const label=document.createElement('span');label.className='plan-location';label.textContent=R()?.name||'';map.append(label)}
  syncSections();return true;
 }
 async function select(id){
  const r=P().rooms.find(x=>x.id===id);if(r)hiddenFloors.delete(r.floor);if(!r?.bbox){toast('Mark this section’s area first.');return}
  if(r.plan_id!==planId){if(pending())return toast('Save your plan before changing pages.');const stage=mode==='camera'?'cameras':'furnish';window.WorkspaceSelection?.selectRoom(id);planId=r.plan_id;rid=id;pendingWorkspaceStage=stage;reset();renderMain();await mountReady;pendingWorkspaceStage=null;window.recordWorkspaceRoute?.(stage);return}
  if(mode==='camera'){if(window.CameraEditor?.pending())return toast('Save the camera before changing sections.');window.WorkspaceSelection?.selectRoom(id);rid=id;await openCameraView(pid,id,{view:planView(r.floor)})}
  else{await FurnitureEditor.switchSection(id);rid=FurnitureEditor.roomId()}
  syncSections();window.recordWorkspaceRoute?.(mode==='camera'?'cameras':'furnish');
 }
 async function toggleFloor(floor){
  if(hiddenFloors.has(floor))hiddenFloors.delete(floor);
  else{const other=candidates().find(r=>r.floor!==floor&&!hiddenFloors.has(r.floor));if(!other)return toast('Keep one floor visible.');hiddenFloors.add(floor);if(R()?.floor===floor)await select(other.id)}
  syncSections();if(mode==='blocks')FurnitureEditor.redraw();else if(!pending())await openCameraView(pid,rid,{view:planView(R()?.floor)});
 }
 function applyFloorVisibility(svg){
  if(!hiddenFloors.size)return;
  const floors=[...new Set(candidates().map(r=>r.floor))].map(f=>({floor:f,view:planView(f)})),root=svg.getScreenCTM();if(!root)return;
  for(const el of svg.querySelectorAll('[data-plan-element],[data-plan-kind],[data-block-room],[data-block-section],[data-camera-block]')){
   let f=candidates().find(r=>r.id===(el.dataset.blockRoom||el.dataset.blockSection))?.floor;
   if(!f){const box=el.getBoundingClientRect(),p=new DOMPoint((box.left+box.right)/2,(box.top+box.bottom)/2).matrixTransform(root.inverse());f=floors.map(v=>({...v,d:Math.hypot(Math.max(v.view[0]-p.x,0,p.x-v.view[0]-v.view[2]),Math.max(v.view[1]-p.y,0,p.y-v.view[1]-v.view[3]))})).sort((a,b)=>a.d-b.d)[0]?.floor}
   if(hiddenFloors.has(f))el.style.display='none';
  }
  const clips=floors.filter(v=>!hiddenFloors.has(v.floor)).map(v=>`<rect x="${v.view[0]}" y="${v.view[1]}" width="${v.view[2]}" height="${v.view[3]}"/>`).join('');
  svg.insertAdjacentHTML('afterbegin',`<defs><clipPath id="visible-plan-floors">${clips}</clipPath></defs>`);svg.querySelectorAll('image').forEach(el=>el.setAttribute('clip-path','url(#visible-plan-floors)'));
 }
 async function selectFloor(floor){const first=candidates().find(r=>r.floor===floor);if(!first)return;await select(first.id);if(mode==='blocks')FurnitureEditor.fitFloor();}
 document.addEventListener('click',e=>{
  if(!$('#plan-editor-inline')||!['plan','references'].includes(tab))return;
  const visibility=e.target.closest('[data-floor-visibility]');if(visibility){toggleFloor(visibility.dataset.floorVisibility).catch(err=>toast(err.message));return}
  const floor=e.target.closest('[data-workspace-floor]');if(floor){selectFloor(floor.dataset.workspaceFloor).catch(err=>toast(err.message));return}
  const row=e.target.closest('[data-action="room"]');if(row){e.preventDefault();e.stopImmediatePropagation();select(row.dataset.id).catch(err=>toast(err.message));return}
  const navigation=e.target.closest('[data-action="tab"],[data-action="open-room"],[data-action="upload-plan"],[data-action="delete-room"],[data-action="add-room"],[data-action="plan-areas"],[data-action="refine-drawing"],[data-action="structure-check"]');
  if(navigation&&pending()){e.preventDefault();e.stopImmediatePropagation();toast('Save your edits before leaving this workspace.');return}
  if(navigation?.dataset.action==='tab'&&navigation.dataset.tab!=='plan')reset();
 },true);
 document.addEventListener('change',e=>{
  if(e.target.id==='workspace-floor'){selectFloor(e.target.value).catch(err=>toast(err.message));return}
  if(!$('#plan-editor-inline')||!['project-select','plan-select'].includes(e.target.id))return;
  if(e.target.id==='plan-select'&&!pending()){e.stopImmediatePropagation();const next=P().rooms.find(r=>r.plan_id===e.target.value&&r.bbox);if(next)select(next.id).catch(err=>toast(err.message));return}
  if(pending()){e.stopImmediatePropagation();e.target.value=e.target.id==='project-select'?pid:planId;toast('Save your edits before changing plans.')}else reset();
 },true);
 window.addEventListener('beforeunload',e=>{if($('#plan-editor-inline')&&pending()){e.preventDefault();e.returnValue=''}});
 document.querySelector('#modal').addEventListener('close',()=>{if($('#plan-editor-inline')){modalType=mode;syncSections();if(mode==='blocks'&&!pending())window.FurnitureEditor?.reload()?.catch(err=>toast(err.message))}});
 window.InlinePlan={ready:()=>mountReady,applyFloorVisibility,floorVisible:f=>!hiddenFloors.has(f)&&(!A(planId)?.construction_selection?.confirmed||f===A(planId).construction_selection.floor),canRender,markup,preserve,reset,mount,show,select,syncSections,planView,active:()=>!!$('#plan-editor-inline'),mode:()=>mode};
})();
