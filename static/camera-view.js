'use strict';
(() => {
 let context=null,draft=null,mode=null,dirty=false,serial=0,timer=null,moving=null,view=null,pan=null,zoomFrame=null,zoomTarget=null;
 const button=(label,action)=>`<button type="button" class="btn small" data-camera="${action}">${label}</button>`;
 const room=()=>state.projects[context.pid].rooms.find(r=>r.id===context.rid);
 const route=action=>`/api/projects/${context.pid}/plans/${room().plan_id}/${action}`;
 const request=()=>({room_id:context.rid,revision:context.revision,...draft,
  height:Number($('#camera-height').value),target_height:Number($('#camera-target-height').value),horizontal_fov:Number($('#camera-fov').value)});
 const ready=()=>draft&&Math.hypot(draft.target[0]-draft.position[0],draft.target[1]-draft.position[1])>=.01;
 const hint=text=>{const el=$('#camera-status');if(el)el.textContent=text};
 window.openCameraView=async function(projectId=pid,roomId=rid,options={}){
  const r=state.projects[projectId]?.rooms.find(x=>x.id===roomId);
  if(!r?.bbox||!r.plan_id)return toast('Select a mapped section first.');
  context={pid:projectId,rid:roomId,revision:r.revision,viewId:Object.hasOwn(options,'viewId')?options.viewId:(window.WorkspaceSelection?.cameraForRoom(roomId)||null)};dirty=false;mode=null;moving=null;pan=null;stopZoom();view=null;serial++;
  if(window.InlinePlan?.active()){rid=roomId;InlinePlan.syncSections()}
  const opening=context;
  const [scene,drawing]=await Promise.all([api(route('shared-scene')+'?room_id='+encodeURIComponent(roomId),{},'GET'),api(route('drawing'),{},'GET')]);
  if(context!==opening)return;
  context.drawing=drawing;
  const named=r.camera_views?.[context.viewId];context.viewId=named?.id||null;context.viewRevision=named?.revision;draft=named?structuredClone(named.camera):scene.saved_camera?structuredClone(scene.saved_camera):null;
  const a=A(r.plan_id);view=options.view?[...options.view]:window.InlinePlan?.active()?InlinePlan.planView():[0,0,a.width,a.height];const field=(id,label,value,min,max,step)=>`<label class="field"><span>${label}</span><input id="camera-${id}" type="number" min="${min}" max="${max}" step="${step}" value="${value}"></label>`;
  showModal('Camera view · '+esc(r.name),`<div class="workspace-modes" role="group" aria-label="Workspace mode">${button('Furniture','furniture')}<button type="button" class="btn small active" aria-pressed="true">Camera</button></div><div class="camera-workspace"><section class="camera-plan-panel"><div class="camera-navigation" role="toolbar" aria-label="Plan navigation">${button('Place camera','position')}${button('Aim camera','target')}${button('Full plan','fit-plan')}${button('This section','fit-room')}<label><input id="camera-original" type="checkbox"> Original map</label></div><svg id="camera-plan" viewBox="0 0 ${a.width} ${a.height}" aria-label="Camera position and viewing direction on the floor plan"></svg><p id="camera-status" role="status">${draft?'Drag the camera or target. Scroll to zoom · Middle-drag to pan.':'Place the camera, then click where it should look.'}</p></section><section class="camera-settings"><label class="field">Saved view<select id="camera-saved-view" aria-label="Saved camera view"></select></label><label class="field">View name<input id="camera-name" maxlength="120" value="${esc(named?.name||'New view')}"></label><label class="field"><span>Section</span><select id="camera-room">${state.projects[projectId].rooms.filter(x=>x.plan_id===r.plan_id&&x.bbox).map(x=>`<option value="${x.id}" ${x.id===roomId?'selected':''}>${esc(x.name)}</option>`).join('')}</select></label><img id="camera-preview" alt="Perspective preview of the saved walls and furniture blocks" hidden><div id="camera-empty">Place the camera to see your view.</div><div class="camera-fields">${field('height','Eye height (m)',draft?.height??scene.model_scale?.eye_height_m??1.5664,.3,2.8,.1)}${field('fov','View width (°)',draft?.horizontal_fov??67.015,30,100,1)}</div><details class="camera-details"><summary>More options</summary><label class="inline-check"><input id="camera-identify" type="checkbox"> Highlight objects</label>${field('target-height','Target height',draft?.target_height??draft?.height??scene.model_scale?.eye_height_m??1.5664,0,3,.1)}${button('Refresh preview','preview')}<div id="camera-objects" class="camera-object-list" aria-label="Furniture visibility"></div></details></section></div>`,button('Close','close')+button('Save camera','save'),'camera');
  $('#modal').classList.add('camera-dialog');savedViews();draw();if(draft)schedule();
 };
 function savedViews(){const el=$('#camera-saved-view');if(!el||!context)return;el.innerHTML='<option value="">New view</option>'+Object.values(room().camera_views||{}).map(v=>`<option value="${esc(v.id)}">${esc(v.name)}</option>`).join('');el.value=context.viewId||'';}
 document.addEventListener('input',e=>{if(e.target.id==='camera-name'){dirty=true;hint('Camera changed · not saved.')}});
 function stopZoom(){if(zoomFrame!==null)cancelAnimationFrame(zoomFrame);zoomFrame=null;zoomTarget=null}
 function applyView(){
  const svg=$('#camera-plan');if(!svg||!view)return;svg.setAttribute('viewBox',view.join(' '));
  const a=A(room().plan_id),scale=svg.getScreenCTM()?.a||1;
  svg.querySelectorAll('circle[data-handle]').forEach(el=>el.setAttribute('r',(el.dataset.handle==='position'?7:6)/scale));
  svg.querySelectorAll('[data-camera-label]').forEach(el=>el.setAttribute('font-size',11/scale));
  const label=$('#camera-zoom-level');if(label)label.textContent=Math.round(a.width/view[2]*100)+'%';
 }
 function animateView(next){
  zoomTarget=next;if(zoomFrame!==null)return;
  const tick=()=>{if(modalType!=='camera'||!$('#camera-plan')){stopZoom();return}view=view.map((v,i)=>v+(zoomTarget[i]-v)*.35);const done=Math.max(...view.map((v,i)=>Math.abs(v-zoomTarget[i])))<.001;if(done)view=[...zoomTarget];applyView();zoomFrame=done?null:requestAnimationFrame(tick);if(done)zoomTarget=null};zoomFrame=requestAnimationFrame(tick);
 }
 function draw(){
  const svg=$('#camera-plan');if(!svg)return;const a=A(room().plan_id),r=room(),b=r.bbox,original=$('#camera-original').checked;
  const background=original?a.id:(a.cad_redraw_id||a.vector_preview_id);
  let overlay='';
  if(draft){const p=[draft.position[0]*a.width,draft.position[1]*a.height],q=[draft.target[0]*a.width,draft.target[1]*a.height],t=Math.atan2(q[1]-p[1],q[0]-p[0]),f=(draft.horizontal_fov??67.015)*Math.PI/360,L=Math.min(a.width,a.height)*.2;
   overlay=`<path d="M${p} L${p[0]+L*Math.cos(t-f)},${p[1]+L*Math.sin(t-f)} A${L},${L} 0 0 1 ${p[0]+L*Math.cos(t+f)},${p[1]+L*Math.sin(t+f)} Z" fill="#f2bd2850" stroke="#bb8a17" stroke-width=".7" pointer-events="none"/><line x1="${p[0]}" y1="${p[1]}" x2="${q[0]}" y2="${q[1]}" stroke="#ad7911"/><circle data-handle="position" cx="${p[0]}" cy="${p[1]}" r="5" fill="#efb81f" stroke="#644b16"/><circle data-handle="target" cx="${q[0]}" cy="${q[1]}" r="4" fill="#368b97" stroke="white"/><text data-camera-label x="${p[0]+7}" y="${p[1]-5}" font-size="6">Camera</text><text data-camera-label x="${q[0]+6}" y="${q[1]-5}" font-size="6">Target</text>`;
  }
  const corrected=!original&&window.DrawingPreview&&context.drawing;
  const furniture=state.projects[context.pid].rooms.filter(x=>x.plan_id===a.id&&x.bbox).flatMap(owner=>(owner.block_layout?.items||[]).map(v=>`<g data-camera-block="${v.id}" data-object-label="${esc(PlanLabels.objectName(v))}" data-object-kind="${esc(v.kind)}" class="drawing-library-furniture" transform="translate(${v.x*a.width} ${v.y*a.height}) rotate(${v.angle}) translate(${-v.width*a.width/2} ${-v.depth*a.height/2}) scale(${v.width*a.width/100} ${v.depth*a.height/100})"><title>${esc(v.label)} · ${esc(owner.name)}</title>${FurnitureLibrary.symbol(v)}</g>`)).join('');
  svg.innerHTML=`<rect width="${a.width}" height="${a.height}" fill="white"/><g pointer-events="none">${corrected?DrawingPreview.markup(context.drawing):background?`<image href="${url(background)}" width="${a.width}" height="${a.height}"/>`:''}${furniture}</g><rect x="${b[0]*a.width}" y="${b[1]*a.height}" width="${b[2]*a.width}" height="${b[3]*a.height}" fill="none" stroke="#bd941f" stroke-width="1" vector-effect="non-scaling-stroke" stroke-dasharray="3 2"/>${overlay}`;
  if(corrected)DrawingPreview.finish(svg);window.InlinePlan?.applyFloorVisibility(svg);window.PlanLabels?.attach(svg,state.projects[context.pid].rooms.filter(x=>x.plan_id===a.id&&x.bbox&&(!window.InlinePlan||InlinePlan.floorVisible(x.floor))),a,room().id);
  document.querySelectorAll('[data-camera="position"],[data-camera="target"]').forEach(el=>{el.classList.toggle('active',el.dataset.camera===mode);el.setAttribute('aria-pressed',el.dataset.camera===mode?'true':'false')});
  const point=e=>{const p=new DOMPoint(e.clientX,e.clientY).matrixTransform(svg.getScreenCTM().inverse());return [Math.max(0,Math.min(1,p.x/a.width)),Math.max(0,Math.min(1,p.y/a.height))]};
  svg.onpointerdown=e=>{stopZoom();if(e.button===1){e.preventDefault();pan={start:[e.clientX,e.clientY],view:[...view],scale:svg.getScreenCTM().a};svg.setPointerCapture(e.pointerId);svg.style.cursor='grabbing';return}if(e.button!==0)return;const handle=e.target.dataset.handle;if(handle){moving=handle;svg.setPointerCapture(e.pointerId);return}if(!mode)return;const q=point(e);if(mode==='position'){draft={...(draft||{}),position:q,target:draft?.target||q,height:Number($('#camera-height').value),target_height:Number($('#camera-target-height').value),horizontal_fov:Number($('#camera-fov').value)};mode='target';hint('Click where the camera should look.')}else{draft.target=q;mode=null;hint('View changed · not saved.');schedule()}dirty=true;draw()};
  svg.onpointermove=e=>{if(pan){view=[pan.view[0]-(e.clientX-pan.start[0])/pan.scale,pan.view[1]-(e.clientY-pan.start[1])/pan.scale,...pan.view.slice(2)];applyView();return}if(!moving)return;draft[moving]=point(e);dirty=true;draw();hint('View changed · not saved.')};
  svg.onpointerup=()=>{if(pan){pan=null;svg.style.cursor='';return}if(moving){moving=null;if(ready())mode=null;schedule()}};
  svg.onpointercancel=()=>{const edited=!!moving;pan=null;svg.style.cursor='';moving=null;if(edited){if(ready())mode=null;schedule()}};
  svg.onauxclick=e=>{if(e.button===1)e.preventDefault()};
  svg.onwheel=e=>{e.preventDefault();if(moving||pan)return;const p=new DOMPoint(e.clientX,e.clientY).matrixTransform(svg.getScreenCTM().inverse());animateView(DrawingGeometry.zoom(zoomTarget||view,[p.x,p.y],e.deltaY*(e.deltaMode===1?16:e.deltaMode===2?300:1),a.width))};
  applyView();
 }
 function schedule(){clearTimeout(timer);const ticket=++serial;timer=setTimeout(()=>preview(ticket),250)}
 async function preview(ticket=++serial){
  if(ticket!==serial||modalType!=='camera')return;
  clearTimeout(timer);
  if(!ready()){const message=draft?'Click Aim camera, then choose a target away from the camera, or drag the blue target.':'Click Place camera and select a position on the plan.';hint(message);$('#camera-preview').hidden=true;$('#camera-empty').hidden=false;$('#camera-empty').textContent=message;return}
  const img=$('#camera-preview');img.hidden=true;$('#camera-empty').hidden=false;$('#camera-empty').textContent='Updating view…';
  try{const result=await api(route('camera-preview'),{...request(),identify_objects:$('#camera-identify')?.checked===true});if(ticket!==serial||modalType!=='camera')return;img.src=result.image;$('#camera-objects').innerHTML=(result.objects||[]).map(o=>`<div><span class="camera-object-swatch" style="background:${/^#[0-9a-f]{6}$/i.test(o.color)?o.color:'#888'}"></span><span>${esc(o.label)}</span><small>${esc(o.status)}</small></div>`).join('');img.hidden=false;$('#camera-empty').hidden=true;hint((dirty?'View changed · not saved.':'Saved camera view.')+(result.typed_segments?'':' No typed walls yet; refine the drawing first.'))}
  catch(err){if(ticket!==serial||modalType!=='camera')return;$('#camera-empty').textContent=err.message;$('#camera-objects').innerHTML='';hint(err.message)}
 }
 document.addEventListener('change',async e=>{if(modalType!=='camera')return;if(e.target.id==='camera-saved-view'){if(dirty&&!confirm('Discard unsaved camera changes?')){e.target.value=context.viewId||'';return}const id=e.target.value;await openCameraView(context.pid,context.rid,{viewId:id||null,view});if(id)window.WorkspaceSelection?.selectCamera(id);window.recordWorkspaceRoute?.('cameras');return}if(e.target.id==='camera-name'){dirty=true;return}if(e.target.id==='camera-room'){if(dirty&&!confirm('Discard unsaved camera changes?')){e.target.value=context.rid;return}try{await openCameraView(context.pid,e.target.value,{view})}catch(err){toast(err.message)}return}if(e.target.id==='camera-original'){draw();return}if(e.target.id==='camera-identify'){schedule();return}const fields={'camera-height':'height','camera-target-height':'target_height','camera-fov':'horizontal_fov'};if(fields[e.target.id]&&draft){draft[fields[e.target.id]]=Number(e.target.value);dirty=true;draw();schedule()}});
 document.addEventListener('click',e=>{if(modalType==='camera'&&dirty&&e.target.closest('[data-action="close-modal"]')&&!confirm('Discard unsaved camera changes?')){e.preventDefault();e.stopImmediatePropagation()}},true);
 document.addEventListener('cancel',e=>{if(modalType==='camera'&&dirty&&!confirm('Discard unsaved camera changes?'))e.preventDefault()},true);
 document.addEventListener('click',async e=>{
  if(e.target.closest('[data-action="camera-view"]'))return openCameraView().catch(err=>toast(err.message));
  const b=e.target.closest('[data-camera]');if(!b||modalType!=='camera')return;
  const action=b.dataset.camera;
  if(['zoom-in','zoom-out','fit-plan','fit-room'].includes(action)){
   const a=A(room().plan_id),base=zoomTarget||view;
   if(action==='fit-plan')animateView(window.InlinePlan?.active()?InlinePlan.planView():[0,0,a.width,a.height]);
   else if(action==='fit-room'){const b=room().bbox,pad=Math.max(b[2]*a.width,b[3]*a.height)*.12;animateView([b[0]*a.width-pad,b[1]*a.height-pad,b[2]*a.width+2*pad,b[3]*a.height+2*pad])}
   else animateView(DrawingGeometry.zoom(base,[base[0]+base[2]/2,base[1]+base[3]/2],action==='zoom-in'?-180:180,a.width));
   return;
  }
  if(action==='furniture'){if(dirty&&!confirm('Discard unsaved camera changes?'))return;serial++;clearTimeout(timer);stopZoom();return openFurnitureBlocks(context.pid,context.rid,{view:[...view]}).catch(err=>toast(err.message))}
  if(action==='close'){if(dirty&&!confirm('Discard unsaved camera changes?'))return;serial++;$('#modal').close();return}
  if(action==='position'||action==='target'){if(action==='target'&&!draft)return hint('Place the camera first.');mode=action;draw();hint(action==='position'?'Click inside the selected section.':'Click where the camera should look.');return}
  if(action==='preview')return preview();
  if(action==='save'){if(!ready())return hint('Choose a viewing target away from the camera.');mode=null;b.disabled=true;hint('Saving camera…');try{const result=await api(route('floor-camera'),{...request(),view_name:$('#camera-name').value.trim()||'New view',view_id:context.viewId,view_revision:context.viewRevision});context.revision=result.revision;context.viewId=result.view?.id;if(result.view){room().camera_views ||= {};room().camera_views[result.view.id]=result.view;}window.WorkspaceSelection?.selectCamera(context.viewId);context.viewRevision=result.view?.revision;draft=result.camera;dirty=false;await refresh(true);window.WorkspaceSelection?.selectCamera(context.viewId);savedViews();window.recordWorkspaceRoute?.('cameras','replace');hint('Camera view saved.');toast('Camera view saved.')}catch(err){hint('Not saved · '+err.message);toast(err.message)}finally{b.disabled=false}}
 });
 window.CameraEditor={pending:()=>dirty,dispose(){serial++;clearTimeout(timer);stopZoom();context=null;dirty=false}};
})();
