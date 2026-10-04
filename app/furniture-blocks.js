'use strict';

(() => {

 let busyDone=Promise.resolve(),releaseBusy=()=>{},roomSelectionSerial=0;
 let history=null,restoringHistory=false,placement=null,multi=new Set(),groupDrag=null;
 let walls=null,ctx=null,items=[],selected=null,issues=[],drag=null,dirty=false,popupOpen=false,popupSurface='plan',modelViewer=null,modelView=null,productLookup=null,panDrag=null,zoomFrame=null,zoomTarget=null,libraryOpen=true,libraryCategory='All',libraryQuery='',busy=false;

 const room=()=>state.projects[ctx.pid].rooms.find(r=>r.id===ctx.rid), plan=()=>A(room().plan_id);

 const btn=(label,key)=>`<button type="button" class="btn small" data-block="${key}">${label}</button>`;

 const active=()=>items.find(v=>v.id===selected);

 const number=(id,label,value,step=1)=>`<label class="field"><span>${label}</span><input id="${id}" type="number" step="${step}" value="${value}"></label>`;

 const displayUnit=()=>plan()?.manual_document?.units||ctx?.drawing?.units||'m';
 const unitFactor=()=>displayUnit()==='ft'?.3048:displayUnit()==='in'?.0254:1;
 function dimensionHint(v,owner){const d=ctx?.dimensions,b=owner?.bbox,f=unitFactor();return owner?.id===ctx.rid&&b&&d?.width_m>0&&d?.depth_m>0?`${(v.width/b[2]*d.width_m/f).toFixed(2)} × ${(v.depth/b[3]*d.depth_m/f).toFixed(2)} ${displayUnit()}`:''}
 function referenceInspector(v){const refs=room().references.map(A).filter(a=>a?.enabled!==false),f=unitFactor(),u=displayUnit();return `<section class="object-reference" aria-label="Object reference"><div class="reference-heading">${v.asset_id?`<img src="${url(v.asset_id)}" alt="Assigned reference">`:'<span class="reference-empty">No image</span>'}<div><strong>Reference</strong><small>${v.asset_id?'Assigned to this object':'No reference assigned'} · ${esc(v.dimension_status||'estimated')} dimensions</small></div></div><select id="block-asset" aria-label="Choose reference"><option value="">Choose an image…</option>${refs.map(a=>`<option value="${a.id}" ${a.id===v.asset_id?'selected':''}>${esc(a.display_name||a.name||'Reference')}</option>`).join('')}</select><div class="actions">${btn(v.asset_id?'Replace / upload':'Upload image','upload')}${v.asset_id?btn('Remove reference','remove-reference'):''}</div><label class="field">Product URL<input id="block-product-url" type="url" value="${esc(v.product_url||'')}" placeholder="https://…"></label><details><summary>Product dimensions & metadata</summary><p class="help">Source dimensions converted to ${u}. Apply explicitly to change the scene proxy.</p><div class="block-fields">${['width','depth','height'].map(k=>number('product-size-'+k,k+' ('+u+')',v.physical_size?.[k]?+(v.physical_size[k]/f).toFixed(3):'',.01)).join('')}</div>${btn('Apply reviewed dimensions','apply-dimensions')}<label class="field">Variant<input id="block-variant" value="${esc(v.variant||'')}"></label>${btn('Fetch product metadata','fetch-product')}<p id="block-product-status" role="status"></p><div id="block-product-result"></div></details><details><summary>Additional design instructions (optional)</summary><textarea id="block-prompt" rows="2" placeholder="Intent that the placed geometry cannot express">${esc(v.prompt||'')}</textarea></details></section>`;}
 function selectedInspector(v){
  if(!v)return '';const d=ctx.dimensions,b=room().bbox,known=Number(d?.width_m)>0&&Number(d?.depth_m)>0,factor=unitFactor(),unit=displayUnit(),mount=v.host_attachment?.kind||'floor';
  const field=(key,label,value)=>`<label class="field">${label} (${unit})<input id="selected-${key}" type="number" step="0.01" ${value==null?'disabled placeholder="Unknown"':`value="${(value/factor).toFixed(3)}"`}></label>`;
  return `<section class="selected-furniture-inspector" aria-label="Selected furniture"><strong>${esc(v.label)}</strong><small>Scene proxy · ${esc(room().name)} · ${mount} mounted</small><div class="block-fields">${field('width','Width',known?v.width/b[2]*d.width_m:null)}${field('depth','Depth',known?v.depth/b[3]*d.depth_m:null)}${field('height','Height',v.height_m??null)}${number('selected-angle','Rotation (°)',v.angle,1)}${field('x','X from room',known?(v.x-b[0])/b[2]*d.width_m:null)}${field('y','Y from room',known?(v.y-b[1])/b[3]*d.depth_m:null)}${mount==='ceiling'?field('drop','Ceiling drop',v.host_attachment.drop||0):mount==='wall'?field('elevation','Base elevation',v.elevation_m||0):''}</div><div class="actions">${btn('Apply transform','precise-size')}${btn('Duplicate','duplicate')}${btn('Delete','remove')}</div>${referenceInspector(v)}</section>`;
 }
 function focusRoom(){ctx.focus='room';ctx.view=null;delete modelView.walk;modelView.pan=[0,0];modelView.zoom=1;}
 function saveStatus(message){const el=$('#block-edit-status');if(el)el.textContent=message;}
 window.openFurnitureBlocks=async function(projectId,roomId,options={}){

  if(!options.reload&&window.InlinePlan?.active()&&ctx?.pid===projectId&&$('#block-plan'))return switchSection(roomId);

  history=null;placement=null;multi.clear();modelView=BlockModelViewer.defaults();try{Object.assign(modelView,JSON.parse(localStorage.getItem('pixeloid-ui-staging-model-appearance')||'{}'))}catch{}ctx={pid:projectId,rid:roomId,showOriginal:false,drafts:{},view:options.view?[...options.view]:null};productLookup=null;const r=room();if(!r?.bbox)return toast('Map a section on the plan first.');

  const opening=ctx;opening.savedSource=savedSource();

  try{await FurnitureMeshes.load();opening.drawing=await api(`/api/projects/${projectId}/plans/${r.plan_id}/drawing`,{},'GET')}catch(err){toast('Could not load the editor: '+err.message);return}

  if(ctx!==opening)return;

  ctx.savedDrawing=structuredClone({edits:ctx.drawing.edits,features:ctx.drawing.features,site:ctx.drawing.site});
  walls=new PlanWalls(ctx.drawing,{svg:()=>$('#block-plan'),redraw:()=>draw(),select:()=>{selected=null;popupOpen=false},changed:()=>{const check=$('#block-reviewed');if(check)check.checked=false},error:toast,commit:()=>call('check').catch(err=>toast(err.message))});
  ctx.revision=r.revision;items=structuredClone(r.block_layout?.items||[]);selected=options.inline?null:items[0]?.id;issues=[];dirty=false;popupOpen=false;render();await call(r.block_layout?'check':'propose',{automatic:true});if(ctx===opening)ctx.ready=true;

 };

 // A mounted editor is a snapshot, not the saved architecture authority.
 function savedSource(){
  const p=state.projects[ctx.pid],a=plan();
  return JSON.stringify([p.map_revision,a.manual_document?.revision,a.drawing,a.raster_geometry]);
 }
 function sourceNotice(message=''){
  let notice=$('#block-source-status');
  if(!notice&&$('#block-edit-status')){notice=document.createElement('p');notice.id='block-source-status';notice.className='help';notice.setAttribute('role','status');$('#block-edit-status').after(notice)}
  if(notice&&notice.syncMessage!==message){notice.syncMessage=message;notice.hidden=!message;notice.textContent=message;if(message){const button=document.createElement('button');button.type='button';button.className='btn small';button.textContent='Reload saved plan';button.onclick=async()=>{if(pendingChanges()&&!confirm('Discard unsaved Furnish edits and load the latest saved plan?'))return;try{await openFurnitureBlocks(ctx.pid,ctx.rid,{reload:true,inline:true,view:ctx.view})}catch(err){toast(err.message)}};notice.append(' ',button)}}
 }
 function interacting(){return busy||drag||groupDrag||panDrag||walls?.drag||placement||['INPUT','TEXTAREA','SELECT'].includes(document.activeElement?.tagName)}
 async function syncSaved(){
  if(!ctx?.ready||!walls||modalType!=='blocks'||ctx.syncing||savedSource()===ctx.savedSource)return;
  if(pendingChanges()){sourceNotice('Plan changed. Your unsaved furniture edits are kept; reload when ready.');return}
  if(interacting())return;
  const current=ctx,section=ctx.rid,source=savedSource(),r=room();current.syncing=true;
  const valid=()=>ctx===current&&ctx.rid===section&&modalType==='blocks'&&savedSource()===source&&!pendingChanges()&&!interacting();
  try{
   const path=`/api/projects/${ctx.pid}/plans/${r.plan_id}/drawing`;
   const drawing=await api(path,{},'GET');if(!valid())return;
   const result=await api(`/api/projects/${ctx.pid}/rooms/${section}/blocks`,{action:'check',revision:r.revision,items:structuredClone(r.block_layout?.items||[])});
   if(!valid())return;
   // Check the drawing again so a save between the drawing and 3D requests
   // cannot produce a mixed-revision pair. Retry on the next normal state poll.
   const latest=await api(path,{},'GET');if(!valid()||JSON.stringify(drawing)!==JSON.stringify(latest))return;
   if(result.revision!==r.revision)return;
   ctx.drawing=drawing;walls.saved(drawing);ctx.savedDrawing=walls.snapshot();ctx.savedSource=source;
   items=result.items;issues=result.issues;ctx.dimensions=result.room_dimensions;ctx.architecture=result.architecture;
   ctx.scene=result.preview_scene;ctx.floors=result.preview_floors||[{room_id:section,scene:result.preview_scene}];ctx.revision=result.revision;
   ctx.drafts={};history=null;multi.clear();walls.clear();
   if(selected&&!items.some(v=>v.id===selected)){selected=null;popupOpen=false}
   render();sourceNotice();
  }catch(err){if(ctx===current)sourceNotice('Could not refresh the saved plan. '+err.message)}
  finally{current.syncing=false}
 }

 function historySnapshot(){
  return {rid:ctx.rid,selected,multi:[...multi],wallSelected:walls.selected,layouts:Object.fromEntries(state.projects[ctx.pid].rooms.filter(r=>r.plan_id===room().plan_id&&r.bbox).map(r=>[r.id,structuredClone(r.id===ctx.rid?items:ctx.drafts[r.id]?.items||r.block_layout?.items||[])])),drawing:walls.snapshot()};
 }
 function historyKey(s){return JSON.stringify({layouts:s.layouts,drawing:s.drawing})}
 function syncHistory(){
  if(!ctx||!walls||restoringHistory)return;
  const snapshot=historySnapshot();
  if(!history){history={past:[],future:[],current:snapshot};return}
  if(historyKey(snapshot)!==historyKey(history.current)){history.past.push(history.current);if(history.past.length>60)history.past.shift();history.future=[]}
  history.current=snapshot;
 }
 async function travelHistory(redo=false){
  if(busy||drag||modelEdit||groupDrag||walls.drag)return;
  syncHistory();const from=redo?history.future:history.past,to=redo?history.past:history.future;
  if(!from.length)return toast(redo?'Nothing to redo.':'Nothing to undo.');
  const snapshot=from.pop();to.push(history.current);restoringHistory=true;
  try{
   ctx.rid=snapshot.rid;selected=snapshot.selected;multi=new Set(snapshot.multi||[]);items=structuredClone(snapshot.layouts[ctx.rid]);ctx.revision=room().revision;ctx.drafts={};
   for(const [id,layout] of Object.entries(snapshot.layouts)){const r=state.projects[ctx.pid].rooms.find(r=>r.id===id);ctx.drafts[id]={items:structuredClone(layout),revision:r.revision,dirty:JSON.stringify(layout)!==JSON.stringify(r.block_layout?.items||[])}}
   dirty=ctx.drafts[ctx.rid].dirty;Object.assign(walls.doc,structuredClone(snapshot.drawing));walls.dirty=JSON.stringify(snapshot.drawing)!==JSON.stringify(ctx.savedDrawing);walls.clear();walls.selected=snapshot.wallSelected;walls.history=[];walls.future=[];
   popupOpen=!!selected&&!walls.selected;history.current=snapshot;render();await call('check');history.current=historySnapshot();toast(redo?'Edit redone.':'Edit undone.');
  }finally{restoringHistory=false}
 }
 document.addEventListener('keydown',e=>{
  if(modalType!=='blocks'||!ctx||!($('#modal').open||window.InlinePlan?.active())||e.isComposing||!(e.ctrlKey||e.metaKey)||e.key.toLowerCase()!=='z'||e.target.closest('input,textarea,select,[contenteditable=true]'))return;
  e.preventDefault();e.stopPropagation();travelHistory(e.shiftKey).catch(err=>toast(err.message));
 });
 function stashDraft(){ctx.drafts[ctx.rid]={items:structuredClone(items),selected,dirty,revision:ctx.revision}}
 function pendingChanges(){return walls?.dirty||walls?.first||dirty||Object.values(ctx.drafts).some(d=>d.dirty)}
 function visibleBlocks(){
  return state.projects[ctx.pid].rooms.filter(r=>r.plan_id===room().plan_id&&r.bbox).sort((a,b)=>(a.id===ctx.rid)-(b.id===ctx.rid)).flatMap(r=>(r.id===ctx.rid?items:ctx.drafts[r.id]?.items||r.block_layout?.items||[]).map(v=>({v,owner:r})));
 }
 async function switchSection(id,blockId=null,options={}){
  const selectionTicket=++roomSelectionSerial,selectionContext=ctx;while(busy)await busyDone;if(ctx!==selectionContext||selectionTicket!==roomSelectionSerial)return;
  if(id===ctx.rid){if(!blockId&&!options.preserveModel){focusRoom();render()}if(blockId){selected=blockId;popupOpen=false;libraryOpen=true;render()}return}
  const next=state.projects[ctx.pid].rooms.find(r=>r.id===id&&r.plan_id===room().plan_id&&r.bbox);if(!next)return;
  const floorChanged=next.floor!==room().floor;if(floorChanged&&!options.preserveModel)multi.clear();walls.clear();stashDraft();ctx.rid=id;if(!options.preserveModel)focusRoom();if(floorChanged){ctx.view=ctx.focus==='room'?null:window.InlinePlan?.planView(next.floor)||null;if(!options.preserveModel){ctx.resumeWalk=!!modelView.walk;modelView={...BlockModelViewer.defaults(),projection:modelView.projection,transparent:modelView.transparent,edges:modelView.edges,cutaway:modelView.cutaway}}}const draft=ctx.drafts[id];ctx.revision=draft?.revision??next.revision;
  items=structuredClone(draft?.items||next.block_layout?.items||[]);selected=blockId||draft?.selected||items[0]?.id;
  dirty=draft?.dirty||false;issues=[];productLookup=null;popupOpen=false;libraryOpen=true;ctx.scene=null;ctx.dimensions=null;
  if(window.InlinePlan?.active()){rid=id;window.InlinePlan.syncSections();if(!blockId)selected=null}
  render();await call('check');
 }
 async function call(action,extra={}){
  if(ctx.ready&&savedSource()!==ctx.savedSource)throw Error('Plan changed. Your edits are kept; reload the saved plan before checking or saving furniture.');
  if(busy)throw Error('Wait for the current placement check.');busy=true;busyDone=new Promise(resolve=>releaseBusy=resolve);const busyHost=$('#plan-editor-inline');if(busyHost){busyHost.setAttribute('aria-busy','true');busyHost.inert=true}
  try{
   items=items.map(v=>{const corrected=FurnitureLibrary.consistentSofa(v,plan());if(corrected!==v)dirty=true;return corrected});
   const payload={action,revision:ctx.revision,items,selected,...extra};
   if(walls?.dirty)payload.drawing=walls.payload();
   if(action==='save'){
    saveStatus('Saving…');
    if(walls.first)throw Error('Finish the wall or opening, or press Escape.');
    if(!walls.doc.manual_draft_id&&!walls.doc.site?.model?.metres_per_pixel&&ctx.scene?.model_scale){const s=ctx.scene.model_scale;walls.doc.site={...walls.doc.site,model:{...walls.doc.site?.model,metres_per_pixel:s.metres_per_pixel,scale_source:s.scale_source}};walls.dirty=true;payload.drawing=walls.payload()}
    stashDraft();payload.action='save-plan';
    payload.drafts=Object.entries(ctx.drafts).filter(([id,d])=>id===ctx.rid||d.dirty).map(([id,d])=>({room_id:id,revision:d.revision,items:d.items,reviewed:id===ctx.rid&&extra.reviewed===true}));
   }
   const requestContext=ctx,result=await api(`/api/projects/${ctx.pid}/rooms/${ctx.rid}/blocks`,payload);
   if(ctx!==requestContext)return result;
   items=result.items;issues=result.issues;ctx.dimensions=result.room_dimensions;ctx.architecture=result.architecture;ctx.scene=result.preview_scene;ctx.floors=result.preview_floors||[{room_id:ctx.rid,scene:result.preview_scene}];ctx.revision=result.revision;
   if(action==='save'){await refresh(true);if(ctx!==requestContext)return result;dirty=false;ctx.drafts={};if(result.drawing){ctx.drawing=result.drawing;walls.saved(ctx.drawing);ctx.savedDrawing=walls.snapshot();ctx.savedSource=savedSource()}}
   if(action==='suggest'||action==='propose')dirty=dirty||JSON.stringify(items)!==JSON.stringify(room().block_layout?.items||[]);
   if(selected&&!items.some(v=>v.id===selected))selected=items[0]?.id;
   render();if(ctx.resumeWalk){ctx.resumeWalk=false;startWalk()}return result;
  }catch(err){if(action==='save')saveStatus('Not saved · '+err.message);throw err;}finally{busy=false;releaseBusy();const busyHost=$('#plan-editor-inline');if(busyHost){busyHost.setAttribute('aria-busy','false');busyHost.inert=false}}
 }

 let catalogueOpen=false;
 function closeCatalogue(){catalogueOpen=false;document.querySelector('#furniture-catalogue')?.remove();document.querySelector('.block-workspace')?.classList.remove('catalogue-open');document.querySelector('[data-block="library"]')?.setAttribute('aria-expanded','false');}
 function openCatalogue(){
  catalogueOpen=true;const workspace=document.querySelector('.block-workspace');if(!workspace)return;document.querySelector('#furniture-catalogue')?.remove();const d=document.createElement('aside');d.id='furniture-catalogue';d.setAttribute('aria-label','Furniture catalogue');d.innerHTML=`<header><strong>Add furniture</strong><button class="btn" data-catalogue-close aria-label="Close furniture catalogue">×</button></header>${libraryMarkup()}<p class="help">Choose a shape, then click inside the active room. Escape ends placement.</p>`;workspace.prepend(d);workspace.classList.add('catalogue-open');d.querySelector('[data-catalogue-close]').onclick=closeCatalogue;document.querySelector('[data-block="library"]')?.setAttribute('aria-expanded','true');
 }
 function libraryCards(){const list=FurnitureLibrary.presets.filter(p=>(libraryCategory==='All'||p.category===libraryCategory)&&p.label.toLowerCase().includes(libraryQuery.toLowerCase()));return list.map(p=>`<button type="button" draggable="false" data-furniture-preset="${p.id}" title="Add ${p.label} to the plan" aria-label="Add ${p.label}"><svg viewBox="0 0 100 100" aria-hidden="true">${FurnitureLibrary.symbol(p)}</svg><span>${p.label}</span></button>`).join('')||'<span>No matching shapes</span>'}

 function libraryMarkup(){return `<div class="furniture-library" aria-label="Furniture library"><div class="library-heading"><strong>Shape library</strong><span>Choose an item to place</span><select id="furniture-category" aria-label="Library category">${['All',...Object.keys(FurnitureLibrary.categories)].map(c=>`<option ${c===libraryCategory?'selected':''}>${c}</option>`).join('')}</select><input id="furniture-search" aria-label="Search shapes" placeholder="Search shapes" value="${esc(libraryQuery)}"></div><div class="furniture-library-grid">${libraryCards()}</div></div>`}

 document.addEventListener('input',e=>{if(e.target.id==='furniture-search'){libraryQuery=e.target.value;document.querySelector('.furniture-library-grid').innerHTML=libraryCards()}});

 document.addEventListener('change',e=>{if(e.target.id==='furniture-category'){libraryCategory=e.target.value;document.querySelector('.furniture-library-grid').innerHTML=libraryCards()}});

 async function addPreset(id,position){
  if(busy)return toast('Wait for the current placement check.');
  multi.clear();walls.clear();if(items.length>=40)return toast('Use up to 40 objects in a section.');const item=FurnitureLibrary.create(id,room().bbox,plan(),ctx.dimensions,position,crypto.randomUUID());const mount=FurnitureLibrary.snapToWall(item,plan(),walls.geometries(),position?20/Math.abs($('#block-plan').getScreenCTM()?.a||1):Infinity);if(mount){Object.assign(item,mount.item);const [a,b]=mount.wall.points,L=Math.hypot(b[0]-a[0],b[1]-a[1]),side=Math.sign((b[0]-a[0])*(item.y*plan().height-a[1])-(b[1]-a[1])*(item.x*plan().width-a[0]))||1;item.host_attachment={kind:'wall',floor:room().floor,wall_id:mount.wall.id,normal:[-side*(b[1]-a[1])/L,side*(b[0]-a[0])/L]};}else if(item.kind==='decor'||item.preset_id==='wall-light')return toast('Place this item close to a compatible wall face.');else if(['pendant-light','ceiling-light','chandelier'].includes(item.preset_id)){item.host_attachment={kind:'ceiling',floor:room().floor,drop:0};item.elevation_m=(modelFloor()?.scene.height||2.8)-item.height_m;}else item.host_attachment={kind:'floor',floor:room().floor};const error=validObjectPosition(item);if(error)return toast(error);items.push(item);selected=item.id;dirty=true;popupOpen=false;await call('check')}

 document.addEventListener('dragstart',e=>{const tile=e.target.closest('[data-furniture-preset]');if(!tile)return;e.dataTransfer.setData('application/x-pixeloid-ui-staging-furniture',tile.dataset.furniturePreset);e.dataTransfer.effectAllowed='copy'});

 document.addEventListener('dragend',()=>$('#block-plan')?.classList.remove('library-drop-active'));

 function previewPlacement(position){if(!placement?.plan)return;const a=plan(),b=room().bbox,v=FurnitureLibrary.create(placement.preset,b,a,ctx.dimensions,position||[b[0]+b[2]/2,b[1]+b[3]/2],'preview'),svg=$('#block-plan');svg?.querySelector('#placement-ghost')?.remove();const error=validObjectPosition(v);svg?.insertAdjacentHTML('beforeend',`<polygon id="placement-ghost" points="${footprint(v).map(p=>p.join(',')).join(' ')}" fill="${error?'#dd5544':'#3684dd'}" fill-opacity=".3" stroke="${error?'#dd5544':'#245dcc'}" stroke-width="2" vector-effect="non-scaling-stroke" pointer-events="none"/>`)}
 function render(){

  if(!modelEdit)syncHistory();
  modelViewer?.dispose();modelViewer=null;
  const r=room(),v=active(),b=r.bbox;

  showModal('Furniture blocks · '+r.name,`

${ctx.architecture?`<details class="block-structure-status"><summary>Structure review</summary><p class="help">${ctx.architecture.typed_wall_count} mapped wall segments · ${ctx.architecture.typed_opening_count} mapped openings (whole plan). ${ctx.architecture.study_reviewed?'Plan study reviewed.':'Structure review pending; furniture remains a draft.'}</p>${ctx.architecture.notes.map(n=>`<p class="help">${esc(n)}</p>`).join('')}</details>`:''}

<div class="workspace-modes" role="group" aria-label="Workspace mode"><button type="button" class="btn small active" aria-pressed="true">Furniture</button>${btn('Camera','camera')}</div><div class="block-toolbar">${btn('Add furniture','library')}${btn('Whole apartment','fit-plan')}${btn('Selected room','fit-section')}${btn('Add block','add')}${btn('Scan section into blocks','propose')}${btn('Suggest clear position','suggest')}${btn('Check placement','check')}<label class="block-map-toggle"><input id="block-object-labels" type="checkbox" ${PlanLabels.objectsVisible?'checked':''}> All object labels</label><label class="block-map-toggle"><input id="block-original-map" type="checkbox" ${ctx.showOriginal?'checked':''}> Original map</label></div>

<div class="block-workspace with-library"><div class="block-left-panel"><p class="furniture-edit-empty">Select an object to edit.</p><div id="block-popover" class="block-details-panel" aria-label="Selected furniture details"></div></div><section><h3>Full plan · furniture & walls</h3>${walls.toolbar()}<div class="block-map-wrap"><svg id="block-plan" aria-label="Original floor plan with draggable furniture blocks" aria-description="Two-finger swipe to pan. Pinch to zoom."></svg></div><p id="block-edit-status" role="status"></p></section>

<aside class="block-inspector"><div class="block-model-panel"><div class="block-model-heading"><h3>3D model</h3><select id="model-projection" aria-label="3D projection"><option value="orthographic" ${modelView.projection!=='perspective'?'selected':''}>Orthographic</option><option value="perspective" ${modelView.projection==='perspective'?'selected':''}>Perspective</option></select><button type="button" class="btn small" id="model-walk" ${modelView.projection!=='perspective'?'hidden':''} aria-pressed="${!!modelView.walk}">${modelView.walk?'Exit walk':'Walk'}</button><span>${esc(r.floor)}</span>${scaleControls()}</div><canvas id="block-preview" tabindex="0" aria-label="Interactive 3D floor model"></canvas><div class="block-model-controls"><button type="button" class="btn small" id="model-edit-move" aria-pressed="${modelEditMode==='move'}">Move</button><button type="button" class="btn small" id="model-edit-rotate" aria-pressed="${modelEditMode==='rotate'}">Rotate</button><button type="button" class="btn small" id="model-place" ${!selected||modelView.projection!=='perspective'?'hidden':''}>Move object</button><span id="model-placement-hint" role="status">${placement?'Click a wall, ceiling or floor · Esc to cancel':modelView.walk?'WASD / arrows · Drag to look':''}</span><button type="button" class="btn small" data-model="reset">Fit</button><button type="button" class="btn small" data-model="top">Top</button><button type="button" class="btn small" data-model="out" aria-label="Zoom out 3D model">−</button><button type="button" class="btn small" data-model="in" aria-label="Zoom in 3D model">+</button><button class="btn small" id="model-solid" aria-pressed="${!modelView.transparent}">Solid</button><label><input id="model-transparent" type="checkbox" ${modelView.transparent?'checked':''}> X-ray</label><label><input id="model-edges" type="checkbox" ${modelView.edges?'checked':''}> Edges</label><label><input id="model-cutaway" type="checkbox" ${modelView.cutaway?'checked':''}> Cutaway</label></div><p class="block-model-hint" id="block-model-geometry"></p><p class="block-model-hint">Drag to rotate · Middle-drag to pan · Scroll to zoom</p>${btn('Set camera','camera')}</div><label class="field"><span>Section</span><select id="block-room">${state.projects[ctx.pid].rooms.filter(x=>x.plan_id===r.plan_id&&x.bbox).map(x=>`<option value="${x.id}" ${x.id===r.id?'selected':''}>${esc(x.name)}</option>`).join('')}</select></label>

<div id="block-wall-properties"></div>${selectedInspector(v)}
${v?`<details class="block-transform-panel" aria-label="Selected object controls"><summary>Advanced · percentage scale<span id="block-seat-status" aria-live="polite">${FurnitureLibrary.quantityLabel(v)?` \u00b7 ${FurnitureLibrary.quantityLabel(v)}`:""}</span></summary><strong>${esc(v.label)}</strong><div class="block-fields">${number('block-angle','Rotation (degrees)',v.angle,10)}${number('block-scale-percent','Scale (%)',100,10)}${number('block-width','Width (% of section)',+(v.width/b[2]*100).toFixed(1),.5)}${number('block-depth','Depth (% of section)',+(v.depth/b[3]*100).toFixed(1),.5)}</div><div class="block-toolbar">${btn('Rotate 90°','rotate')}${btn('Apply scale','scale')}${btn('Duplicate','duplicate')}</div></details>`:''}

<details class="block-object-properties"><summary>Object properties</summary>${v?`<label class="field"><span>Object</span><input id="block-label" value="${esc(v.label)}"></label><label class="field"><span>Type</span><select id="block-kind">${['unknown','sofa','chair','table','bed','storage','refrigerator','comforter','pillar','fixture','appliance','desk','plant','rug','stair','light','decor'].map(k=>`<option ${k===v.kind?'selected':''}>${k}</option>`).join('')}</select></label>

<label class="field"><span>Block shape</span><select id="block-shape"><option value="box" ${!['l','round'].includes(v.shape)?'selected':''}>Single block</option><option value="l" ${v.shape==='l'?'selected':''}>L-shaped</option><option value="round" ${v.shape==='round'?'selected':''}>Round</option></select></label>${v.shape==='l'?`<label class="field"><span>Return side (before rotation)</span><select id="block-return_side"><option value="left" ${v.return_side!=='right'?'selected':''}>Left</option><option value="right" ${v.return_side==='right'?'selected':''}>Right</option></select></label>`:''}<div class="block-fields">${!['light','decor'].includes(v.kind)?number('block-height_m','Height (m)',v.height_m??(v.kind==='table'?.45:.8),.05):''}${v.kind==='sofa'?number('block-seats','Seats (blank if unknown)',v.seat_count??''):''}</div>

<div class="block-toolbar">${btn('Split into two','split')}${btn('Remove block','remove')}</div>`:''}

</details>

<div class="block-list">${items.map((x,i)=>`<button type="button" data-block-select="${x.id}" class="${x.id===selected?'selected':''}"><span class="block-swatch">${i+1}</span>${esc(x.label)}</button>`).join('')||'<p>Add a block for each object you can identify on the drawing.</p>'}</div>


<p class="help">Preset sizes are editable estimates.</p>

<div id="block-feedback" role="status">${walls.dirty?'Walls changed · check placement before saving.':issues.length?`<strong>${issues.length} placement issue(s)</strong><ul>${issues.map(x=>`<li>${esc(x.message)}</li>`).join('')}</ul>`:'<details class="placement-details"><summary>Mock check · not validated</summary><p>No backend validation runs in this preview. Review geometry manually.</p></details>'}</div>

<label class="block-review"><input id="block-reviewed" type="checkbox" ${r.block_layout?.reviewed&&!dirty&&!walls.dirty&&!issues.length?'checked':''}> I checked these blocks against the original plan.</label><p class="help">Suggestions avoid known obstructions only. They do not identify missing objects or certify an accurate plan.</p></aside></div>`,`${btn('Close','close')}${btn('Save plan','save')}`,'blocks');

  $('#modal').classList.add('blocks-dialog');draw();if(catalogueOpen)openCatalogue();saveStatus(pendingChanges()?'Unsaved changes':'Saved');

 }

 function footprint(v){

  const a=plan(),t=v.angle*Math.PI/180,c=Math.cos(t),s=Math.sin(t);

  return [[-1,-1],[1,-1],[1,1],[-1,1]].map(([x,y])=>{x*=v.width*a.width/2;y*=v.depth*a.height/2;return [v.x*a.width+x*c-y*s,v.y*a.height+x*s+y*c]});

 }

 function pieces(v){
  if(v.kind==='chair'&&v.chair_modules)return FurnitureLibrary.chairInstances(v,plan()).flatMap(pieces);

  if(v.shape==='round'){const a=plan(),t=v.angle*Math.PI/180,c=Math.cos(t),s=Math.sin(t);return [Array.from({length:32},(_,i)=>{const angle=i*Math.PI/16,x=Math.cos(angle)*v.width*a.width/2,y=Math.sin(angle)*v.depth*a.height/2;return [v.x*a.width+x*c-y*s,v.y*a.height+x*s+y*c]})]}

  if(v.shape!=='l'&&v.preset_id!=='staircase-l')return [footprint(v)];

  const a=plan(),W=v.width*a.width,D=v.depth*a.height,t=v.angle*Math.PI/180,c=Math.cos(t),ss=Math.sin(t);

  const lw=(v.sofa_modules?.leg_width??v.width*.4)*a.width,ld=(v.sofa_modules?.leg_depth??v.depth*.4)*a.height;

  const rows=v.preset_id==='staircase-l'?[[-W/2,-D/2,W/2,-D/2+D*.28],[-W/2,-D/2+D*.28,-W/2+W*.48,D/2]]:[[-W/2,D/2-ld,W/2,D/2],v.return_side==='right'?[W/2-lw,-D/2,W/2,D/2-ld]:[-W/2,-D/2,-W/2+lw,D/2-ld]];

  return rows.map(([l,top,r,b])=>[[l,top],[r,top],[r,b],[l,b]].map(([x,y])=>{x*=v.flip_x?-1:1;y*=v.flip_y?-1:1;return [v.x*a.width+x*c-y*ss,v.y*a.height+x*ss+y*c]}));

 }

 function selectionRows(){
  return [...multi].flatMap(key=>{
   if(key.startsWith('w:')){const value=walls.geometry(key.slice(2));return value?[{key,type:'wall',value,featureId:value.id.startsWith('new')?value.id:'new'+crypto.randomUUID().replaceAll('-','')}]:[]}
   const row=visibleBlocks().find(({v,owner})=>key==='f:'+owner.id+':'+v.id);return row?[{key,type:'furniture',owner:row.owner.id,value:structuredClone(row.v)}]:[];
  });
 }
 function toggleSelection(key){
  const object=key.startsWith('f:')?visibleBlocks().find(({v,owner})=>key==='f:'+owner.id+':'+v.id):null;const geometry=key.startsWith('w:')?walls.geometry(key.slice(2)):null;const floor=object?.owner.floor||(geometry&&(ctx.floors||[]).find(({scene})=>geometry.points.every(p=>p[0]/plan().width>=scene.bounds[0]-.003&&p[0]/plan().width<=scene.bounds[2]+.003&&p[1]/plan().height>=scene.bounds[1]-.003&&p[1]/plan().height<=scene.bounds[3]+.003))?.scene.floor);if(floor&&floor!==room().floor)return toast('Select objects on the current floor.');
  if(!multi.size){if(selected)multi.add('f:'+ctx.rid+':'+selected);if(walls.selected)multi.add('w:'+walls.selected)}
  if(key.startsWith('w:')&&!walls.geometry(key.slice(2)))return toast('Trace this outline before adding it to a selection.');
  if(multi.has(key))multi.delete(key);else multi.add(key);
  selected=null;walls.clear();popupOpen=false;libraryOpen=true;render();
 }
 function writeSelection(rows,{duplicate=false,remove=false}={}){
  const next=new Set(),owners=new Map();
  for(const row of rows.filter(r=>r.type==='furniture')){if(!owners.has(row.owner)){const r=state.projects[ctx.pid].rooms.find(r=>r.id===row.owner);owners.set(row.owner,{room:r,items:structuredClone(row.owner===ctx.rid?items:ctx.drafts[row.owner]?.items||r.block_layout?.items||[])})}}
  for(const row of rows){
   if(row.type==='wall')continue;const target=owners.get(row.owner),v=structuredClone(row.value);
   if(duplicate){v.id=crypto.randomUUID();v.asset_id=null;v.label+=' copy'}else target.items=target.items.filter(v=>v.id!==row.value.id);
   if(!remove){target.items.push(v);next.add('f:'+row.owner+':'+v.id)}
  }
  if([...owners.values()].some(o=>o.items.length>40))throw Error('Use up to 40 objects per section.');
  const wallRows=rows.filter(r=>r.type==='wall');if(walls.doc.features.length+wallRows.filter(r=>duplicate||!r.value.id.startsWith('new')).length>400)throw Error('Use up to 400 drawing elements.');
  for(const row of wallRows){const v=structuredClone(row.value),source=walls.doc.features.find(f=>f.id===v.id)||walls.doc.elements.find(f=>f.id===v.id);if(!source)continue;
   if(duplicate){v.id='new'+crypto.randomUUID().replaceAll('-','');walls.doc.features.push(v)}else{v.id=row.featureId;walls.replace(source,remove?[]:[v])}
   if(!remove)next.add('w:'+v.id);walls.changed();
  }
  for(const [id,o] of owners){if(id===ctx.rid){items=o.items;dirty=true}else ctx.drafts[id]={items:o.items,dirty:true,revision:ctx.drafts[id]?.revision??o.room.revision}}
  multi=next;selected=null;walls.clear();popupOpen=false;libraryOpen=true;
 }
 async function selectionAction(action){
  if(busy||!multi.size)return;syncHistory();const rows=selectionRows();if(!rows.length)return;
  let options={};if(action==='rotate-left'||action==='rotate-right')options.rotation=action==='rotate-left'?-90:90;
  if(action==='flip-x'||action==='flip-y')options.flip=action.slice(-1);
  if(action==='grow'||action==='shrink')options.factor=action==='grow'?1.1:1/1.1;
  if(action==='duplicate'){const b=FurnitureLibrary.groupBounds(rows,plan());options.delta=[Math.min(8,plan().width-b.x-b.width),Math.min(8,plan().height-b.y-b.depth)]}
  writeSelection(action==='remove'?rows:FurnitureLibrary.transformGroup(rows,plan(),options),{duplicate:action==='duplicate',remove:action==='remove'});await call('check');
 }
 function groupPointerDown(e){
  const object=e.target.closest('[data-block-id]'),wall=e.target.closest('[data-plan-element]'),handle=e.target.closest('[data-group-handle]')?.dataset.groupHandle,key=object?'f:'+object.dataset.blockRoom+':'+object.dataset.blockId:wall&&!walls.doc.manual_draft_id?'w:'+wall.dataset.planElement:null;
  if(walls.tool!=='select')return false;
  if(key&&(e.shiftKey||e.ctrlKey||e.metaKey)){toggleSelection(key);return true}
  if(multi.size&&(handle||key&&multi.has(key))){const svg=$('#block-plan'),p=new DOMPoint(e.clientX,e.clientY).matrixTransform(svg.getScreenCTM().inverse());syncHistory();const rows=selectionRows();
   groupDrag={rows,bounds:FurnitureLibrary.groupBounds(rows,plan()),point:[p.x,p.y],screen:[e.clientX,e.clientY],handle,moved:false,state:{items:structuredClone(items),drafts:structuredClone(ctx.drafts),drawing:walls.snapshot(),dirty,wallDirty:walls.dirty,keys:[...multi]}};svg.setPointerCapture(e.pointerId);return true;
  }
  multi.clear();return false;
 }
 function groupPointerMove(e){
  if(!groupDrag)return false;const d=groupDrag;if(!d.moved&&Math.hypot(e.clientX-d.screen[0],e.clientY-d.screen[1])<3)return true;d.moved=true;
  const svg=$('#block-plan'),p=new DOMPoint(e.clientX,e.clientY).matrixTransform(svg.getScreenCTM().inverse()),c=d.bounds.center;let options={delta:[p.x-d.point[0],p.y-d.point[1]]};
  if(d.handle==='rotate')options={rotation:Math.round((Math.atan2(p.y-c[1],p.x-c[0])-Math.atan2(d.point[1]-c[1],d.point[0]-c[0]))*180/Math.PI/10)*10};
  else if(d.handle)options={factor:Math.max(.05,Math.hypot(p.x-c[0],p.y-c[1])/Math.hypot(d.point[0]-c[0],d.point[1]-c[1]))};
  try{const rows=FurnitureLibrary.transformGroup(d.rows,plan(),options);items=structuredClone(d.state.items);ctx.drafts=structuredClone(d.state.drafts);Object.assign(walls.doc,structuredClone(d.state.drawing));writeSelection(rows);draw()}catch{}return true;
 }
 async function groupPointerUp(e,cancel=false){
  if(!groupDrag)return false;const d=groupDrag;if(!cancel&&d.moved)groupPointerMove(e);groupDrag=null;
  if(cancel){items=d.state.items;ctx.drafts=d.state.drafts;Object.assign(walls.doc,d.state.drawing);dirty=d.state.dirty;walls.dirty=d.state.wallDirty;multi=new Set(d.state.keys)}
  const svg=$('#block-plan');if(svg.hasPointerCapture(e.pointerId))svg.releasePointerCapture(e.pointerId);if(d.moved&&!cancel)await call('check');else render();return true;
 }
 function groupTools(){
  const svg=$('#block-plan');svg.querySelector('#group-transform-handles')?.remove();if(!multi.size)return;
  const rows=selectionRows();if(!rows.length){multi.clear();return}const b=FurnitureLibrary.groupBounds(rows,plan()),scale=Math.abs(svg.getScreenCTM()?.a||1),size=7/scale,gap=26/scale;
  for(const key of multi){if(key.startsWith('w:'))svg.querySelector(`[data-plan-element="${key.slice(2)}"]`)?.classList.add('plan-wall-selected')}
  svg.insertAdjacentHTML('beforeend',`<g id="group-transform-handles" data-selection-count="${multi.size}"><rect class="block-selection-frame" x="${b.x}" y="${b.y}" width="${b.width}" height="${b.depth}" pointer-events="none"/>${[[0,0],[1,0],[1,1],[0,1]].map(([x,y])=>`<rect data-group-handle="scale" class="block-resize-handle" x="${b.x+x*b.width-size/2}" y="${b.y+y*b.depth-size/2}" width="${size}" height="${size}" style="cursor:${x===y?'nwse':'nesw'}-resize"/>`).join('')}<line class="block-rotation-stem" x1="${b.center[0]}" y1="${b.y}" x2="${b.center[0]}" y2="${b.y-gap}"/><circle data-group-handle="rotate" class="block-rotate-handle" cx="${b.center[0]}" cy="${b.y-gap}" r="${5/scale}"/></g>`);
 }
 function draw(){

  const a=plan(),b=room().bbox,svg=$('#block-plan');if(!svg)return;

  const pad=Math.min(b[2]*a.width,b[3]*a.height)*.1;

  ctx.view=ctx.view||[b[0]*a.width-pad,b[1]*a.height-pad,b[2]*a.width+2*pad,b[3]*a.height+2*pad];svg.setAttribute('viewBox',ctx.view.join(' '));

  const background=ctx.showOriginal?a.id:(a.cad_redraw_id||a.vector_preview_id);

  const corrected=!!ctx.drawing;

  svg.innerHTML=`<rect width="${a.width}" height="${a.height}" fill="white"/>${corrected?`${ctx.showOriginal?`<image href="${url(a.id)}" width="${a.width}" height="${a.height}" opacity=".4"/>`:''}${DrawingPreview.markup(ctx.drawing,true)}`:background?`<image href="${url(background)}" width="${a.width}" height="${a.height}"/>`:''}<rect x="${b[0]*a.width}" y="${b[1]*a.height}" width="${b[2]*a.width}" height="${b[3]*a.height}" fill="none" data-active-room="${ctx.rid}" stroke="#3b78db" stroke-width="2" vector-effect="non-scaling-stroke" stroke-dasharray="2 2"/>`+state.projects[ctx.pid].rooms.filter(r=>r.plan_id===a.id&&r.bbox).sort((a,b)=>b.bbox[2]*b.bbox[3]-a.bbox[2]*a.bbox[3]).map(r=>`<rect data-block-section="${r.id}" x="${r.bbox[0]*a.width}" y="${r.bbox[1]*a.height}" width="${r.bbox[2]*a.width}" height="${r.bbox[3]*a.height}" fill="transparent"><title>${esc(r.name)}</title></rect>`).join('')+visibleBlocks().map(({v,owner})=>{

   const pts=footprint(v),t=v.angle*Math.PI/180,x=v.x*a.width,y=v.y*a.height,L=Math.min(v.width*a.width,v.depth*a.height)*.3;

   return `<g data-block-id="${v.id}" data-block-room="${owner.id}" data-object-label="${esc(PlanLabels.objectName(v))}" data-object-kind="${esc(v.kind)}" data-label-detail="${esc(dimensionHint(v,owner))}" aria-label="${esc(v.label)} in ${esc(owner.name)}"><title>${esc(v.label)} - ${esc(owner.name)}</title>${pieces(v).map(part=>`<polygon points="${part.map(p=>p.join(',')).join(' ')}" fill="${(owner.id===ctx.rid&&selected===v.id||multi.has('f:'+owner.id+':'+v.id))?'#e9b72b':'#89959c'}" fill-opacity=".55" stroke="${owner.id===ctx.rid&&issues.some(z=>z.id===v.id)?'#b34334':'#354247'}" stroke-width=".8" vector-effect="non-scaling-stroke"/>`).join('')}<g pointer-events="none" transform="translate(${x} ${y}) rotate(${v.angle}) translate(${-v.width*a.width/2} ${-v.depth*a.height/2}) scale(${v.width*a.width/100} ${v.depth*a.height/100})" class="furniture-symbol">${FurnitureLibrary.symbol(v)}</g><line x1="${x}" y1="${y}" x2="${x+Math.sin(t)*L*(v.flip_y?-1:1)}" y2="${y-Math.cos(t)*L*(v.flip_y?-1:1)}" stroke="#243336" stroke-width=".8" vector-effect="non-scaling-stroke"/></g>`;

  }).join('');

  if(corrected){DrawingPreview.finish(svg);const art=svg.querySelector('.drawing-art');svg.insertBefore(art,svg.querySelector('[data-block-id]'));}

  svg.onpointerdown=e=>{

   if(busy||e.button!==0&&e.button!==1)return;e.preventDefault();

   if(e.button===1){$('#block-popover').hidden=true;panDrag={start:[e.clientX,e.clientY],view:[...ctx.view],scale:svg.getScreenCTM().a};svg.setPointerCapture(e.pointerId);return}

   if(groupPointerDown(e))return;
   if(placement?.plan&&e.button===0){const p=new DOMPoint(e.clientX,e.clientY).matrixTransform(svg.getScreenCTM().inverse()),v=FurnitureLibrary.create(placement.preset,room().bbox,a,ctx.dimensions,[p.x/a.width,p.y/a.height],'preview');const error=validObjectPosition(v);if(error){toast(error);return}addPreset(placement.preset,[p.x/a.width,p.y/a.height]).catch(e=>toast(e.message));return}if(walls.pointerDown(e))return;
   const handle=e.target.closest('[data-block-handle]')?.dataset.blockHandle;

   const object=e.target.closest('[data-block-id]');
   if(!handle&&!object){selected=null;walls.clear();popupOpen=false;libraryOpen=true;const point=new DOMPoint(e.clientX,e.clientY).matrixTransform(svg.getScreenCTM().inverse());const section=e.target.closest('[data-block-section]')?.dataset.blockSection||state.projects[ctx.pid].rooms.filter(r=>r.plan_id===a.id&&r.bbox&&point.x/a.width>=r.bbox[0]&&point.x/a.width<=r.bbox[0]+r.bbox[2]&&point.y/a.height>=r.bbox[1]&&point.y/a.height<=r.bbox[1]+r.bbox[3]).sort((u,v)=>u.bbox[2]*u.bbox[3]-v.bbox[2]*v.bbox[3])[0]?.id;if(section&&section!==ctx.rid){switchSection(section).catch(err=>toast(err.message));return}render();return}
   const owner=object?.dataset.blockRoom;
   if(!handle&&owner&&owner!==ctx.rid){switchSection(owner,object?.dataset.blockId).catch(err=>toast(err.message));return}
   const key=handle?selected:object?.dataset.blockId;

   svg.style.cursor=handle==='rotate'?'grabbing':handle?e.target.closest('[data-block-handle]').style.cursor:'';

   if(!key)return;

   walls.clear();selected=key;popupSurface='plan';$('#block-popover').hidden=true;

   const p=new DOMPoint(e.clientX,e.clientY).matrixTransform(svg.getScreenCTM().inverse());

   drag={start:[e.clientX,e.clientY],point:[p.x,p.y],x:active().x,y:active().y,original:structuredClone(active()),handle,moved:false};draw();svg.setPointerCapture(e.pointerId);

  };

  svg.onpointermove=e=>{if(placement?.plan){const p=new DOMPoint(e.clientX,e.clientY).matrixTransform(svg.getScreenCTM().inverse());previewPlacement([p.x/a.width,p.y/a.height]);return}if(groupPointerMove(e))return;if(walls.pointerMove(e))return;if(panDrag){ctx.view=[panDrag.view[0]-(e.clientX-panDrag.start[0])/panDrag.scale,panDrag.view[1]-(e.clientY-panDrag.start[1])/panDrag.scale,...panDrag.view.slice(2)];svg.setAttribute('viewBox',ctx.view.join(' '));popover();return}if(drag&&(drag.moved||Math.hypot(e.clientX-drag.start[0],e.clientY-drag.start[1])>3)){drag.moved=true;move(e)}};

  svg.onpointerup=async e=>{if(groupDrag){try{await groupPointerUp(e)}catch(err){toast(err.message)}return}if(walls.pointerUp(e))return;svg.style.cursor='';if(panDrag){panDrag=null;if(svg.hasPointerCapture(e.pointerId))svg.releasePointerCapture(e.pointerId);popover();return}if(!drag)return;const moved=drag.moved;if(moved)move(e);drag=null;walls.guides=[];if(svg.hasPointerCapture(e.pointerId))svg.releasePointerCapture(e.pointerId);popupOpen=false;libraryOpen=true;if(moved)try{await call('check')}catch(err){toast(err.message);render()}else render()};

  svg.onpointercancel=e=>{if(groupDrag){groupPointerUp(e,true);return}if(walls.pointerUp(e,true))return;svg.style.cursor='';panDrag=null;walls.guides=[];if(drag){Object.assign(active(),drag.original);drag=null}render()};

  svg.onauxclick=e=>{if(e.button===1)e.preventDefault()};

  svg.onwheel=e=>{e.preventDefault();if(drag||groupDrag||panDrag||walls.drag)return;
   // Match the plan editor: two-finger scrolling pans; Ctrl+wheel is pinch.
   const unit=e.deltaMode===1?16:e.deltaMode===2?svg.clientHeight:1;
   if(!e.ctrlKey){
    if(zoomFrame)cancelAnimationFrame(zoomFrame);zoomFrame=null;zoomTarget=null;
    const matrix=svg.getScreenCTM();if(!matrix)return;
    ctx.view=[ctx.view[0]+e.deltaX*unit/matrix.a,ctx.view[1]+e.deltaY*unit/matrix.d,...ctx.view.slice(2)];
    svg.setAttribute('viewBox',ctx.view.join(' '));walls.handles();popover();return;
   }
   if(zoomFrame)cancelAnimationFrame(zoomFrame);zoomFrame=null;zoomTarget=null;
   const matrix=svg.getScreenCTM();if(!matrix)return;
   const p=new DOMPoint(e.clientX,e.clientY).matrixTransform(matrix.inverse());
   ctx.view=DrawingGeometry.pinchZoom(ctx.view,[p.x,p.y],e.deltaY*unit,a.width);
   svg.setAttribute('viewBox',ctx.view.join(' '));walls.handles();popover();};

  svg.ondragover=e=>{if([...e.dataTransfer.types].includes('application/x-pixeloid-ui-staging-furniture')){e.preventDefault();e.dataTransfer.dropEffect='copy';svg.classList.add('library-drop-active')}};

  svg.ondragleave=e=>{if(!svg.contains(e.relatedTarget))svg.classList.remove('library-drop-active')};

  svg.ondrop=async e=>{const key=e.dataTransfer.getData('application/x-pixeloid-ui-staging-furniture');if(!key)return;e.preventDefault();svg.classList.remove('library-drop-active');const p=new DOMPoint(e.clientX,e.clientY).matrixTransform(svg.getScreenCTM().inverse());try{await addPreset(key,[Math.max(0,Math.min(1,p.x/a.width)),Math.max(0,Math.min(1,p.y/a.height))])}catch(err){toast(err.message)}};

  document.querySelectorAll('[data-block-select]').forEach(el=>el.classList.toggle('selected',el.dataset.blockSelect===selected));
  draw3d();walls.decorate();window.InlinePlan?.applyFloorVisibility(svg);window.ConstructionArea?.overlay(svg,a);objectTools();if(!drag)popover();svg.querySelectorAll('[data-block-id],[data-plan-element]').forEach(el=>{el.dataset.labelActive=String(el.dataset.blockId===selected||el.dataset.planElement===walls.selected)});window.PlanLabels?.attach(svg,state.projects[ctx.pid].rooms.filter(r=>r.plan_id===a.id&&r.bbox&&(!window.InlinePlan||InlinePlan.floorVisible(r.floor))),a,ctx.rid);

 }

 function selectionToolbar(){
  const svg=$('#block-plan'),host=svg?.parentElement;if(!host)return;
  let bar=host.querySelector('.object-action-bar');
  const v=active(),target=multi.size?svg.querySelector('#group-transform-handles'):v?svg.querySelector(`[data-block-id="${v.id}"][data-block-room="${ctx.rid}"]`):walls.element();
  if(!target||drag||groupDrag?.moved||panDrag||walls.drag?.moved){bar?.remove();return}
  const b=target.getBoundingClientRect(),h=host.getBoundingClientRect();
  if(b.right<h.left||b.left>h.right||b.bottom<h.top||b.top>h.bottom){bar?.remove();return}
  if(!bar){bar=document.createElement('div');bar.className='object-action-bar';bar.setAttribute('role','toolbar');bar.setAttribute('aria-label','Object actions');host.append(bar)}
  const actions=[['rotate-left','Rotate left 90°','<path d="M4 9a8 8 0 1 1 0 8M4 3v6h6"/>'],['rotate-right','Rotate right 90°','<path d="M20 9a8 8 0 1 0 0 8m0-14v6h-6"/>'],['flip-x','Flip horizontally','<path d="M12 3v18M3 17V7l6 10H3Zm18 0V7l-6 10h6Z"/>'],['flip-y','Flip vertically','<path d="M3 12h18M7 3h10L7 9V3Zm0 18h10l-10-6v6Z"/>'],['duplicate','Duplicate object','<rect x="8" y="8" width="12" height="12" rx="2"/><path d="M15 5V3H3v12h2"/>']];
  if(multi.size){actions.find(v=>v[0]==='duplicate')[1]='Duplicate selection';}if(multi.size)actions.push(['shrink','Scale selection down 10%','<path d="M4 12h16"/>'],['grow','Scale selection up 10%','<path d="M4 12h16M12 4v16"/>']);
  const attribute=multi.size?'data-group-action':v?'data-block':'data-wall-action';
  const html=(multi.size?`<span class="selection-count">${multi.size}</span>`:'')+actions.map(([key,label,icon])=>`<button type="button" ${attribute}="${key}" title="${label}" aria-label="${label}" ${key.startsWith('flip-')&&v?`aria-pressed="${!!v[key==='flip-x'?'flip_x':'flip_y']}"`:''}><svg viewBox="0 0 24 24" aria-hidden="true">${icon}</svg></button>`).join('');
  if(bar.innerHTML!==html)bar.innerHTML=html;
  const w=bar.offsetWidth,height=bar.offsetHeight;
  bar.style.left=Math.max(6,Math.min(h.width-w-6,(b.left+b.right)/2-h.left-w/2))+'px';
  // Leave space for the rotation handle between the object and its toolbar.
  const top=b.top-h.top-height-(v?40:10);
  bar.style.top=Math.max(6,Math.min(h.height-height-6,top>=6?top:b.bottom-h.top+12))+'px';
 }

 function objectTools(){
  groupTools();selectionToolbar();

  const seatStatus=$('#block-seat-status');if(seatStatus)seatStatus.textContent=FurnitureLibrary.quantityLabel(active())?` \u00b7 ${FurnitureLibrary.quantityLabel(active())}`:'';
  const svg=$('#block-plan'),v=active();if(!svg)return;svg.querySelector('#block-transform-handles')?.remove();if(multi.size||!v||panDrag||drag&&!drag.handle)return;

  const scale=Math.abs(svg.getScreenCTM()?.a||1),W=v.width*plan().width,D=v.depth*plan().height,size=7/scale,gap=26/scale;

  const sides=[['nw',-1,-1],['n',0,-1],['ne',1,-1],['e',1,0],['se',1,1],['s',0,1],['sw',-1,1],['w',-1,0]];

  svg.insertAdjacentHTML('beforeend',`<g id="block-transform-handles" transform="translate(${v.x*plan().width} ${v.y*plan().height}) rotate(${v.angle})"><rect class="block-selection-frame" x="${-W/2}" y="${-D/2}" width="${W}" height="${D}"/><line class="block-rotation-stem" x1="0" y1="${-D/2}" x2="0" y2="${-D/2-gap}"/>${sides.map(([key,x,y])=>`<rect data-block-handle="${key}" class="block-resize-handle" x="${x*W/2-size/2}" y="${y*D/2-size/2}" width="${size}" height="${size}" style='cursor:${FurnitureLibrary.resizeCursor(v,plan(),x,y)}'><title>${x&&y?'Drag to scale proportionally':v.kind==='stair'?'Drag to resize this side':v.kind==='chair'?'Drag to add or remove chairs':v.kind==='sofa'&&v.shape!=='round'?(x||v.shape==='l'?'Drag to add or remove seats':'Sofa depth is fixed · use a corner to scale'):'Drag to resize proportionally'}</title></rect>`).join('')}<circle data-block-handle="rotate" class="block-rotate-handle" cx="0" cy="${-D/2-gap}" r="${5/scale}"><title>Drag to rotate · snaps every 10°</title></circle></g>`);

 }

 window.addEventListener('resize',()=>{if(ctx&&typeof modalType!=='undefined'&&modalType==='blocks')objectTools()});

 function popover(){

  objectTools();

  const host=$('#block-popover'),v=active();if(!host)return;
  if(!v||multi.size)libraryOpen=true;
  const empty=document.querySelector('.furniture-edit-empty');if(empty)empty.hidden=!!v;
  const library=$('#block-library-panel');if(library)library.hidden=!libraryOpen;
  document.querySelectorAll('.block-left-tabs [data-block]').forEach(el=>{const pressed=el.dataset.block===(libraryOpen?'library':'reference');el.classList.toggle('selected',pressed);el.setAttribute('aria-pressed',String(pressed))});
  host.hidden=libraryOpen||!v||!popupOpen||!!(drag||panDrag);
  if(!v||!popupOpen||document.querySelector('.selected-furniture-inspector .object-reference')){host.innerHTML='';host.hidden=true;return}

  const refs=room().references.map(A).filter(a=>a?.enabled!==false);

  host.innerHTML=`<div class="block-popover-card"><button class="btn small" type="button" data-block="hide-popup" style="float:right" aria-label="Close furniture popup">x</button><strong>${esc(v.label)}</strong>${['light','decor'].includes(v.kind)?`<div class="block-fields">${number('block-elevation_m','Mounting height (m)',v.elevation_m??0,.05)}${number('block-height_m',v.kind==='decor'?'Frame height (m)':'Fixture height (m)',v.height_m??.5,.05)}</div>`:''}${v.kind==='stair'?`<div class="stair-controls">${number('stair-width',v.preset_id==='staircase-spiral'?'Diameter (% of section)':'Width (% of section)',+(v.width/room().bbox[2]*100).toFixed(1),.5)}${v.preset_id!=='staircase-spiral'?number('stair-depth','Length (% of section)',+(v.depth/room().bbox[3]*100).toFixed(1),.5):''}${number('stair-height','Height (m)',v.height_m??3,.1)}${number('stair-angle','Up direction (°)',v.angle,10)}${v.preset_id==='staircase-spiral'?`<label class="field"><span>Climb direction</span><select id="stair-winding"><option value="clockwise" ${!v.flip_x?'selected':''}>Clockwise</option><option value="counterclockwise" ${v.flip_x?'selected':''}>Counterclockwise</option></select></label>`:''}${btn('Apply','apply-stair')}${btn('Turn 90°','rotate')}${btn('Delete','remove')}<span class="help">Arrow points up the stairs.</span></div>`:''}<div class="block-product-link"><label class="field"><span>Product URL</span><input id="block-product-url" type="url" maxlength="4096" value="${esc(v.product_url||'')}" placeholder="https://shop.com/product/…"></label>${btn('Fetch photos & dimensions','fetch-product')}<p id="block-product-status" role="status"></p><div id="block-product-result"></div></div>${v.asset_id?`<img src="${url(v.asset_id)}" alt="Furniture linked to this block">`:'<div class="block-empty-photo">Link a furniture image to this block</div>'}<label class="field"><span>Furniture reference</span><select id="block-asset"><option value="">Choose an image…</option>${refs.map(a=>`<option value="${a.id}" ${a.id===v.asset_id?'selected':''}>${esc(a.category||a.display_name||a.name||'Furniture')}</option>`).join('')}</select></label>${btn('Upload image','upload')}<label class="field"><span>Variant / finish</span><input id="block-variant" value="${esc(v.variant||'')}" placeholder="Unspecified — enter the exact variant"></label><label class="field"><span>Dimension certainty</span><select id="block-dimension_status">${['missing','estimated','extracted','reviewed'].map(t=>`<option ${t===(v.dimension_status||'estimated')?'selected':''}>${t}</option>`).join('')}</select></label><div class="block-manual-dimensions"><p class="help">Dimensions: ${esc(v.dimension_status||'estimated')}. Missing values are not product measurements.</p>${number('product-size-width','Width (m)',v.physical_size?.width??'',.01)}${number('product-size-depth','Depth (m)',v.physical_size?.depth??'',.01)}${number('product-size-height','Height (m)',v.dimension_status==='reviewed'?v.height_m??'':'',.01)}${btn('Apply reviewed dimensions','apply-dimensions')}</div><label class="field"><span>Additional design instructions (optional)</span><textarea id="block-prompt" rows="3" placeholder="Intent that the placed geometry cannot express">${esc(v.prompt||'')}</textarea></label></div>`;

  const linked=A(v.asset_id)?.source_product;if(productLookup?.block_id!==v.id&&linked&&(!v.product_url||v.product_url===linked.url))productLookup={block_id:v.id,product:linked};
  if(productLookup?.block_id===v.id)showProduct();

 }

 function showProduct(){

  const holder=$('#block-product-result'),p=productLookup?.product;if(!holder||!p)return;

  const sizes=p.dimensions_m||{};if(!active()?.physical_size){for(const [key,val] of Object.entries({width:sizes.length?.metres??sizes.width?.metres,depth:sizes.depth?.metres??(sizes.length?sizes.width?.metres:null),height:sizes.height?.metres})){const input=$('#product-size-'+key);if(input&&val!=null)input.value=val/unitFactor()}}holder.innerHTML=`<strong>${esc(p.title)}</strong><p><a href="${esc(p.url)}" target="_blank" rel="noopener noreferrer">View source product</a></p><div class="block-product-photos">${(p.images||[p.image]).map((image,i)=>`<button type="button" data-block="choose-product" data-photo="${i}" title="Use photo ${i+1}"><img src="/product-photo/${p.id}?image=${i}" alt="Product photo ${i+1}"></button>`).join('')}</div><p>${['length','width','depth','height'].filter(k=>k!=='length'||sizes.length).map(k=>k+': '+(sizes[k]?esc(sizes[k].published):'not published')).join('<br>')}</p>${p.dimension_notes?.length?`<p>${p.dimension_notes.map(esc).join('<br>')}</p>`:''}<p class="help">Click a photo to use it for this block. Check the product variant and measurements.</p><p class="help">Review converted product dimensions in the selected scene units. Width is across the furniture front; depth is front to back. No size is applied until you choose it.</p><p class="help">${ctx.dimensions?'Sizes use the current plan scale; estimated scale stays approximate.':'Set the floor-plan dimensions before applying real product measurements. The source dimensions are retained with the image.'}</p>`;



 }

 async function fetchProduct(){

  const input=$('#block-product-url'),status=$('#block-product-status'),key=selected,url=input.value.trim();

  active().product_url=url;dirty=true;$('#block-reviewed').checked=false;
  status.textContent='Fetching product photos and published measurements…';

  try{const p=await api('/api/products/inspect',{url});if(selected!==key||active()?.product_url.trim()!==url)return;productLookup={block_id:key,product:p};showProduct();status.textContent='Product metadata read. Please check the exact variant.'}

  catch(err){status.textContent=err.message}

 }

 async function chooseProduct(index){

  const p=productLookup?.product,key=selected;if(!p)return;

  const result=await api(`/api/projects/${ctx.pid}/rooms/${ctx.rid}/add-product`,{product_id:p.id,image_index:index});

  await refresh(false);ctx.revision=room().revision;const item=items.find(v=>v.id===key);if(item){item.asset_id=result.assets[0].id;item.label=p.title;item.product_url=item.product_url||p.url;dirty=true}render();toast('Product image linked. Review dimensions before applying them.');

 }

 async function attach(file){

  if(!file)return;const error=validateReferenceFile(file,'reference');if(error)throw Error(error);

  const target=active(),key=target?.id;if(!target)return;

  const response=await fetch(`/api/projects/${ctx.pid}/upload?kind=reference&room_id=${ctx.rid}`,{method:'POST',headers:{'Content-Type':'application/octet-stream','X-Filename':encodeURIComponent(file.name)},body:file});

  const data=await response.json();if(!response.ok||!data.assets?.length)throw Error(data.error||'Could not save this image.');

  await refresh(false);ctx.revision=room().revision;const item=items.find(v=>v.id===key);if(item)item.asset_id=data.assets[0].id;dirty=true;render();toast('Image linked to this block. Save blocks to retain its placement.');

 }

 function move(e){

  const svg=$('#block-plan'),a=plan(),v=active(),last=structuredClone(active());const p=new DOMPoint(e.clientX,e.clientY).matrixTransform(svg.getScreenCTM().inverse());

  if(drag.handle)Object.assign(v,FurnitureLibrary.transform(drag.original,a,drag.handle,drag.point,[p.x,p.y]));

  else{v.x=Math.max(0,Math.min(1,drag.x+(p.x-drag.point[0])/a.width));v.y=Math.max(0,Math.min(1,drag.y+(p.y-drag.point[1])/a.height));walls.guides=[];
   if(walls.snapping&&!e.altKey){
    const mount=FurnitureLibrary.snapToWall(v,a,walls.geometries(),20/Math.abs(svg.getScreenCTM()?.a||1));
    if(mount){Object.assign(v,mount.item);walls.guides=[{points:mount.wall.points}]}else{
    const targets=visibleBlocks().filter(({v:other,owner})=>owner.floor===room().floor&&!(owner.id===ctx.rid&&other.id===v.id)).flatMap(({v:other})=>[...footprint(other),[other.x*a.width,other.y*a.height]]);
    const result=DrawingGeometry.snapBounds(footprint(v),targets,8/Math.abs(svg.getScreenCTM()?.a||1));
    const next=[v.x+result.shift[0]/a.width,v.y+result.shift[1]/a.height];
    if(next.every(n=>n>=0&&n<=1)){[v.x,v.y]=next;walls.guides=result.guides}}
   }
  }if(v.host_attachment?.kind==='wall'){const n=v.host_attachment.normal,dx=(v.x-last.x)*a.width,dy=(v.y-last.y)*a.height,dot=dx*n[0]+dy*n[1];v.x-=dot*n[0]/a.width;v.y-=dot*n[1]/a.height;v.angle=last.angle;}if(v.host_attachment?.kind==='ceiling')v.elevation_m=(modelFloor()?.scene.height||2.8)-v.height_m-(v.host_attachment.drop||0);const error=validObjectPosition(v);if(error){Object.assign(v,last);saveStatus(error);return;}dirty=true;

  $('#block-reviewed').checked=false;draw();

 }

 let modelEditMode='move',modelEdit=null;
 function beginModelEdit(hit,p){
  const v=active();if(busy||placement||!v||hit?.id!==v.id||hit.roomId!==ctx.rid||hit.architecture)return null;
  const f=modelFloor();if(!f)return null;const a=plan(),mount=v.host_attachment?.kind||'floor';
  if(modelEditMode==='rotate'&&mount==='wall'){toast('Wall orientation follows its host. Move it along the wall face.');return null}
  const centre=[(v.x-f.scene.bounds[0])*a.width,(v.y-f.scene.bounds[1])*a.height,(f.elevation+(v.elevation_m||0))*f.unit];
  const n=mount==='wall'?[...v.host_attachment.normal,0]:[0,0,1],ray=BlockModelViewer.rayFor(p,modelView,modelViewer.bounds,modelViewer.canvas.clientWidth,modelViewer.canvas.clientHeight),point=BlockModelViewer.planePoint(ray,centre,n);if(!point)return null;
  syncHistory();modelEdit={original:structuredClone(v),dirty,point,normal:n,centre,f,mode:modelEditMode,valid:true};return modelEdit;
 }
 function retainFloorAttachment(v){if(!v.host_attachment&&['sofa','chair','table','bed','storage','refrigerator','comforter','pillar','appliance','desk','plant','rug','stair'].includes(v.kind)&&!(v.elevation_m||0))v.host_attachment={kind:'floor',floor:room().floor};}
 function validObjectPosition(v){
  const a=plan(),b=room().bbox,f=modelFloor();if(!f)return 'Wait for the shared scene.';
  const pts=footprint(v);if(pts.some(p=>p[0]<b[0]*a.width-.1||p[0]>(b[0]+b[2])*a.width+.1||p[1]<b[1]*a.height-.1||p[1]>(b[1]+b[3])*a.height+.1))return 'Keep the object footprint inside the selected room. Choose the destination room to place there.';
  if((v.elevation_m||0)<0||(v.elevation_m||0)+(v.height_m||.8)>(f.scene.height||2.8)+.001)return 'The object must fit between the floor and ceiling.';
  if(v.host_attachment?.kind==='wall'){
   const host=walls.geometry(v.host_attachment.wall_id);if(!host)return 'The host wall is missing. Reattach this object before moving it.';
   const [p,q]=host.points,L=Math.hypot(q[0]-p[0],q[1]-p[1]),t=((v.x*a.width-p[0])*(q[0]-p[0])+(v.y*a.height-p[1])*(q[1]-p[1]))/L;
   const normal=v.host_attachment.normal,offset=((v.x*a.width-p[0])*normal[0]+(v.y*a.height-p[1])*normal[1]),old=active();if(old?.host_attachment&&Math.abs(offset-((old.x*a.width-p[0])*normal[0]+(old.y*a.height-p[1])*normal[1])-(v.depth-old.depth)*a.height/2)>.1)return 'Keep the object on its attached wall face.';if(t<v.width*a.width/2||t>L-v.width*a.width/2)return 'The object extends beyond its host wall.';
  }return '';
 }
 function moveModelEdit(d,ray,delta,event){
  const v=active(),a=plan();if(!v)return;const next=structuredClone(d.original);retainFloorAttachment(next);
  if(d.mode==='rotate')next.angle=(d.original.angle+delta[0]*(event.altKey?.3:1)+360)%360;
  else{const p=BlockModelViewer.planePoint(ray,d.centre,d.normal);if(!p)return;let shift=p.map((v,i)=>v-d.point[i]);if(!event.altKey){const step=.05*d.f.unit;shift=shift.map(v=>Math.round(v/step)*step)}next.x+=shift[0]/a.width;next.y+=shift[1]/a.height;if(next.host_attachment?.kind==='wall')next.elevation_m=(next.elevation_m||0)+shift[2]/d.f.unit;}
  const error=validObjectPosition(next);d.valid=!error;if(error){saveStatus(error);return}
  Object.assign(v,next);dirty=true;draw();saveStatus('Moving · '+dimensionHint(v,room())+' · '+Math.round(v.angle)+'°'+(v.host_attachment?.kind==='wall'?' · base '+((v.elevation_m||0)/unitFactor()).toFixed(2)+' '+displayUnit():''));
 }
 async function endModelEdit(d,cancel){
  modelEdit=null;if(cancel){Object.assign(active(),d.original);dirty=d.dirty;draw();saveStatus(d.dirty?'Unsaved changes':'Saved');return}
  try{await call('check');saveStatus('Unsaved changes')}catch(e){Object.assign(active(),d.original);dirty=d.dirty;render();toast(e.message)}
 }
 function drawModelGizmo(viewer){
  const c=viewer.canvas,v=active(),f=modelFloor();let svg=c.parentElement.querySelector('.model-gizmo');if(!svg){svg=document.createElementNS('http://www.w3.org/2000/svg','svg');svg.setAttribute('class','model-gizmo');svg.setAttribute('aria-hidden','true');c.after(svg)}
  svg.style.cssText=`position:absolute;pointer-events:none;left:${c.offsetLeft}px;top:${c.offsetTop}px;width:${c.clientWidth}px;height:${c.clientHeight}px`;svg.setAttribute('viewBox',`0 0 ${c.clientWidth} ${c.clientHeight}`);if(!v||!f||modelView.walk){svg.innerHTML='';return}
  const p=[(v.x-f.scene.bounds[0])*plan().width,(v.y-f.scene.bounds[1])*plan().height,(f.elevation+(v.elevation_m||0)+(v.height_m||.8)/2)*f.unit],q=BlockModelViewer.project(p,modelView,viewer.bounds,c.clientWidth,c.clientHeight);
  svg.innerHTML=`<g transform="translate(${q[0]} ${q[1]})"><circle r="18" fill="#245dcc22" stroke="#245dcc" stroke-width="2"/><path d="M-30 0H30M0-30V30" stroke="#245dcc" stroke-width="2"/><path d="M24-4L30 0 24 4M-4-24L0-30 4-24" fill="none" stroke="#245dcc" stroke-width="2"/><text y="-37" text-anchor="middle" fill="#153d87" stroke="#fff" stroke-width="3" paint-order="stroke" font-size="11">${esc(modelEditMode==='rotate'?'Rotate':v.host_attachment?.kind==='wall'?'Move on wall':v.host_attachment?.kind==='ceiling'?'Move on ceiling':'Move on floor')}</text></g>`;
 }

 function modelFloor(name=room().floor){
  const floors=(ctx.floors||[]).filter(({scene})=>!scene.selection_required),base=floors[0]?.scene;if(!base)return null;
  const unit=(base.bounds[2]-base.bounds[0])*plan().width/base.width;let elevation=0;
  for(const row of floors){if(row.scene.floor===name)return {...row,unit,elevation};elevation+=row.scene.height||3}return null;
 }
 function walkControls(){
  const b=$('#model-walk'),p=$('#model-place'),hint=$('#model-placement-hint');if(!b)return;
  b.hidden=modelView.projection!=='perspective';b.textContent=modelView.walk?'Exit walk':'Walk';b.setAttribute('aria-pressed',String(!!modelView.walk));
  const transparent=$('#model-transparent');transparent.disabled=!!modelView.walk;transparent.checked=modelView.walk?false:modelView.transparent;
  p.hidden=(!selected&&!multi.size)||modelView.projection!=='perspective';p.textContent=multi.size?'Move selection':'Move object';hint.textContent=placement?'Click a wall, ceiling or floor · Esc to cancel':modelView.walk?'WASD / arrows · Drag to look':'';
 }
 function startWalk(){
  if(modelView.walk){modelViewer.leaveWalk();walkControls();return}
  const f=modelFloor();if(!f)return;const b=room().bbox,a=plan(),bounds=f.scene.bounds;
  modelViewer.enterWalk({position:[(b[0]+b[2]/2-bounds[0])*a.width,(b[1]+b[3]/2-bounds[1])*a.height,(f.elevation+(f.scene.model_scale?.eye_height_m??1.5664))*f.unit],yaw:0,pitch:0,unit:f.unit,verticalFov:f.scene.model_scale?.vertical_fov||60,floorName:room().floor});walkControls();
 }
 function armPlacement(preset=null){placement=preset?{preset}:multi.size?{group:selectionRows(),floor:room().floor}:{id:selected,roomId:ctx.rid};libraryOpen=true;popupOpen=false;walkControls();$('#block-preview')?.focus();toast('Click a surface in the 3D view.');}
 async function placeInModel(hit,request){
  if(!hit?.point||!request)return;
  if(busy)return toast('Wait for the current placement check.');
  const f=modelFloor(hit.floorName),a=plan();if(!f)return;
  const position=[f.scene.bounds[0]+hit.point[0]/a.width,f.scene.bounds[1]+hit.point[1]/a.height];
  const target=state.projects[ctx.pid].rooms.filter(r=>r.plan_id===room().plan_id&&r.floor===hit.floorName&&r.bbox&&position[0]>=r.bbox[0]-.005&&position[0]<=r.bbox[0]+r.bbox[2]+.005&&position[1]>=r.bbox[1]-.005&&position[1]<=r.bbox[1]+r.bbox[3]+.005).sort((x,y)=>x.bbox[2]*x.bbox[3]-y.bbox[2]*y.bbox[3])[0];
  if(!target)return toast('Choose a surface inside a mapped section.');
  if(request.group){if(hit.floorName!==request.floor||!hit.floor)return toast('Move the selection onto the floor of the current level.');const b=FurnitureLibrary.groupBounds(request.group,a);writeSelection(FurnitureLibrary.transformGroup(request.group,a,{delta:[position[0]*a.width-b.center[0],position[1]*a.height-b.center[1]]}));placement=null;await call('check');toast('Selection moved.');return}
  let item=request.preset?FurnitureLibrary.create(request.preset,target.bbox,a,null,position,crypto.randomUUID()):structuredClone(visibleBlocks().find(({v,owner})=>v.id===request.id&&owner.id===request.roomId)?.v);
  if(!item)return;const mountWall=hit.surfaceKind==='wall',mountCeiling=hit.ceiling||hit.surfaceKind==='ceiling',mountFloor=hit.floor;
  const ceilingAsset=['pendant-light','ceiling-light','chandelier'].includes(item.preset_id),wallAsset=item.kind==='decor'||item.preset_id==='wall-light';
  if(!(mountWall||mountCeiling||mountFloor))return toast('Choose a wall, ceiling or floor surface.');
  if(ceilingAsset&&!mountCeiling)return toast('Place this light on a ceiling. Enter Walk and look up.');
  if(wallAsset&&!mountWall)return toast('Place this object on a wall.');
  if(!ceilingAsset&&!wallAsset&&!mountFloor)return toast('Place this object on the floor.');
  if((mountWall||mountCeiling)&&item.height_m>(f.scene.height||3))return toast('This object is taller than the room. Reduce its height first.');
  item.host_attachment={kind:mountWall?'wall':mountCeiling?'ceiling':'floor',floor:hit.floorName,...(mountWall?{wall_id:hit.sourceId,normal:hit.normal.slice(0,2)}:{})};item.x=position[0];item.y=position[1];const localZ=hit.point[2]/f.unit-f.elevation;
  if(mountWall){if(Math.abs(hit.normal[2])>.2)return toast('Choose the face of the wall.');const host=walls.geometry(hit.sourceId);if(host){const [p,q]=host.points,dx=q[0]-p[0],dy=q[1]-p[1],len=Math.hypot(dx,dy);if(Math.abs(dx*hit.normal[0]+dy*hit.normal[1])/len>.3||len<item.width*a.width)return toast('Choose a wider wall face.');const snap=FurnitureLibrary.snapToWall(item,a,[host],Infinity);if(snap){item.x=snap.item.x;item.y=snap.item.y;item.angle=snap.item.angle;}}item.angle=(Math.atan2(-hit.normal[0],hit.normal[1])*180/Math.PI+360)%360;const offset=item.depth*a.height/2+.05;if(!host){item.x+=hit.normal[0]*offset/a.width;item.y+=hit.normal[1]*offset/a.height;}item.elevation_m=Math.max(0,Math.min((f.scene.height||3)-item.height_m,localZ-item.height_m/2));}
  else item.elevation_m=mountCeiling?Math.max(0,localZ-item.height_m):0;if(mountCeiling)item.host_attachment.drop=0;
  if(item.x<0||item.x>1||item.y<0||item.y>1)return toast('Keep the object inside the plan.');
  if(target.id!==ctx.rid)await switchSection(target.id,null,{preserveModel:true});
  if(items.length>=40&&request.roomId!==target.id)return toast('Use up to 40 objects in a section.');
  if(request.id){if(request.roomId===ctx.rid)items=items.filter(v=>v.id!==request.id);else{const source=ctx.drafts[request.roomId]||{items:structuredClone(state.projects[ctx.pid].rooms.find(r=>r.id===request.roomId).block_layout?.items||[]),revision:state.projects[ctx.pid].rooms.find(r=>r.id===request.roomId).revision};source.items=source.items.filter(v=>v.id!==request.id);source.dirty=true;ctx.drafts[request.roomId]=source}}
  items.push(item);selected=item.id;placement=null;dirty=true;popupOpen=false;libraryOpen=true;await call('check');toast('Object placed.');
 }
 function scaleControls(){
  const s=ctx.scene?.model_scale||{},h=s.wall_height_m||3;
  if(walls.doc.manual_draft_id)return `<details class="model-scale"><summary class="btn small">${h.toFixed(2)} m walls</summary><p class="help">Scale and wall heights come from the linked floor plan.</p><a class="btn small" href="/ps/app/floor-plan.html?preview=ui7#${encodeURIComponent(walls.doc.manual_draft_id)}">Edit scale & heights</a></details>`;
  return `<details class="model-scale"><summary class="btn small" title="Wall height and real-world scale">${h.toFixed(2)} m walls</summary><div class="model-scale-fields"><strong>Scale & height</strong><span class="help">${esc(s.measured?'Measured plan':s.scale_source||'Estimated scale')}</span>${number('model-wall-height','Wall height (m)',h,.1)}${number('model-floor-width','Floor width (m)',+(ctx.scene?.width||10).toFixed(3),.1)}${number('model-human-height','Human height (ft)',+((s.human_height_m||1.6764)/.3048).toFixed(2),.1)}${number('model-fov','Walk field of view (°)',s.vertical_fov||60,5)}<span class="help">Eye level ${((s.human_height_m||1.6764)-.11).toFixed(2)} m · Current floor</span>${btn('Apply','apply-model-scale')}${btn('Balance furniture','balance-furniture')}<span class="help">Standard furniture sizes · Both floors</span></div></details>`;
 }
 function draw3d(){
  const canvas=$('#block-preview');if(!canvas)return;
  const scene=ctx.scene;
  const {faces,levels}=FurnitureMeshes.building(ctx.floors||[],plan(),visibleBlocks(),{room:ctx.rid,object:selected,wall:walls.selected,multi:[...multi]},floor=>!window.InlinePlan||InlinePlan.floorVisible(floor));
  canvas.dataset.visibleFloors=JSON.stringify(levels);canvas.dataset.levelCount=levels.length;
  const floorLabel=$('.block-model-heading span');if(floorLabel)floorLabel.textContent=levels.map(v=>v.name==='Lower floor'?'Ground floor':v.name==='Upper floor'?'First floor':v.name).join(' + ');
  if(!modelViewer||modelViewer.canvas!==canvas){modelViewer?.dispose();modelViewer=new BlockModelViewer.Viewer(canvas,modelView,async (hit,modifiers={})=>{
   const key=hit?.architecture?'w:'+hit.sourceId:hit?'f:'+hit.roomId+':'+hit.id:null;
   if(key&&(modifiers.shiftKey||modifiers.ctrlKey||modifiers.metaKey)){toggleSelection(key);return}
   if(key&&multi.has(key)){render();return}multi.clear();
   if(hit?.architecture){try{if(hit.floorName!==room().floor)await switchSection(hit.roomId,null,{preserveModel:true});selected=null;popupOpen=false;libraryOpen=true;walls.clear();walls.selected=hit.sourceId;render()}catch(err){toast(err.message)}}
   else if(hit){walls.clear();popupSurface='preview';switchSection(hit.roomId,hit.id,{preserveModel:true}).catch(err=>toast(err.message))}
   else{walls.clear();selected=null;popupOpen=false;libraryOpen=true;render()}
  },{beginEdit:beginModelEdit,moveEdit:moveModelEdit,endEdit:(d,c)=>endModelEdit(d,c),afterDraw:drawModelGizmo,onSurface:hit=>{if(!placement)return false;placeInModel(hit,placement).catch(e=>toast(e.message));return true},onDrop:(preset,hit)=>{if(modelView.projection!=='perspective')return toast('Switch to Perspective to place objects in 3D.');placeInModel(hit,{preset}).catch(e=>toast(e.message))},onModeChange:walkControls});
   for(const mode of ['move','rotate'])$('#model-edit-'+mode).onclick=()=>{modelEditMode=mode;for(const m of ['move','rotate'])$('#model-edit-'+m).setAttribute('aria-pressed',String(mode===m));modelViewer.draw()};$('#model-walk').onclick=startWalk;$('#model-place').onclick=()=>armPlacement();
   document.querySelectorAll('[data-model]').forEach(el=>el.onclick=()=>{const action=el.dataset.model;if(action==='in'||action==='out')modelViewer.zoom(action==='in'?1.2:1/1.2);else modelViewer.reset(action==='top');walkControls()});
   $('#model-projection').onchange=e=>{modelView.projection=e.target.value;if(e.target.value!=='perspective'){modelViewer.leaveWalk();placement=null}modelViewer.draw();walkControls()};
   const appearance=()=>{localStorage.setItem('pixeloid-ui-staging-model-appearance',JSON.stringify({transparent:modelView.transparent,edges:modelView.edges,cutaway:modelView.cutaway}));$('#model-solid').setAttribute('aria-pressed',String(!modelView.transparent));modelViewer.draw()};$('#model-transparent').onchange=e=>{modelView.transparent=e.target.checked;appearance()};$('#model-solid').onclick=()=>{modelView.transparent=false;$('#model-transparent').checked=false;appearance()};for(const key of ['edges','cutaway'])$('#model-'+key).onchange=e=>{modelView[key]=e.target.checked;appearance()};
  }
  const info=$('#block-model-geometry');if(info){const counts=scene?.architecture_counts;info.classList.toggle('needs-review',!!scene&&(!counts?.wall||!!scene.unresolved_architecture?.length));info.textContent=counts?.wall?`${counts.wall} wall spans · ${counts.window} windows · ${counts.door+counts.sliding_door} doors${scene.unresolved_architecture?.length?' · '+scene.unresolved_architecture.length+' outlines need review':''}`:scene?'Walls need tracing · use the wall tool on the plan.':'Loading structure…'}
  const f=modelFloor(),b=room().bbox,a=plan();const focus=ctx.focus==='room'&&f?{center:[(b[0]+b[2]/2-f.scene.bounds[0])*a.width,(b[1]+b[3]/2-f.scene.bounds[1])*a.height,(f.elevation+(f.scene.height||2.8)/2)*f.unit],radius:Math.max(1,Math.hypot(b[2]*a.width,b[3]*a.height,(f.scene.height||2.8)*f.unit)/2)}:null;canvas.dataset.activeRoom=ctx.rid;canvas.dataset.focusMode=ctx.focus||'whole';canvas.dataset.focusBounds=JSON.stringify(focus);modelViewer.update(faces,focus);walkControls();
 }

 document.addEventListener('click',async e=>{

  if(e.target.closest('[data-action="furniture-blocks"]')){const r=R();if(r?.bbox)return openFurnitureBlocks(pid,r.id);return toast('Select a mapped section first.')}

  const groupButton=e.target.closest('[data-group-action]');if(groupButton&&ctx){selectionAction(groupButton.dataset.groupAction).catch(err=>toast(err.message));return}
  const tile=e.target.closest('[data-furniture-preset]');if(tile&&ctx&&modalType==='blocks'){try{placement={preset:tile.dataset.furniturePreset,plan:true};previewPlacement();toast('Click inside '+room().name+' to place. Escape ends repeated placement.');}catch(err){toast(err.message)}return}

  const select=e.target.closest('[data-block-select]');if(select){walls.clear();selected=select.dataset.blockSelect;popupOpen=false;libraryOpen=true;render();return}

  const button=e.target.closest('[data-block]');if(!button||!ctx||busy)return;button.disabled=true;

  try{

   const action=button.dataset.block,v=active(),r=room();

   if(action==='camera'){if(pendingChanges())return toast('Save your block changes before opening the camera view.');return openCameraView(ctx.pid,ctx.rid,{view:ctx.view?[...ctx.view]:null})}

   if(action==='balance-furniture'){
    const s=ctx.scene.model_scale,scale=s.metres_per_pixel;let count=0;
    const rows=visibleBlocks().map(({v,owner})=>{const result=FurnitureLibrary.balance(v,plan(),scale,A(v.asset_id)?.source_product);if(JSON.stringify(result)!==JSON.stringify(v))count++;return {key:'f:'+owner.id+':'+v.id,type:'furniture',owner:owner.id,value:result}});
    if(rows.some(({value:v})=>v.width>1||v.depth>1))throw Error('Check the plan scale before balancing furniture.');
    walls.doc.site={...walls.doc.site,model:{...walls.doc.site?.model,metres_per_pixel:scale,scale_source:s.scale_source}};walls.dirty=true;
    writeSelection(rows);multi.clear();await call('check');toast(`${count} objects balanced · Positions and counts kept · Save plan to keep it.`);return;
   }
   if(action==='apply-model-scale'){
    const height=Number($('#model-wall-height').value),width=Number($('#model-floor-width').value),human=Number($('#model-human-height').value)*.3048,fov=Number($('#model-fov').value);
    if(![height,width,human,fov].every(Number.isFinite)||height<2.4||height>6||width<=0||human<1||human>2.4||fov<40||fov>85)throw Error('Use wall height 2.4–6 m, a positive floor width, human height 3.3–7.8 ft and field of view 40–85°.');
    const s=ctx.scene.model_scale,old=walls.doc.site?.model||{},changed=Math.abs(width-ctx.scene.width)>.001;
    if(s.measured&&changed)throw Error('This plan has a measured scale. Change it in Area & sections.');
    walls.doc.site={...walls.doc.site,model:{...old,metres_per_pixel:width/((ctx.scene.bounds[2]-ctx.scene.bounds[0])*plan().width),scale_source:changed?'Manual floor width':s.scale_source,wall_heights:{...old.wall_heights,[r.floor]:height},human_height_m:human,vertical_fov:fov}};
    walls.dirty=true;ctx.resumeWalk=!!modelView.walk;await call('check');toast('Scale updated · Save plan to keep it.');return;
   }
   if(action==='fit-plan'){ctx.focus='whole';delete modelView.walk;modelView.pan=[0,0];modelView.zoom=1;ctx.view=window.InlinePlan?.active()?InlinePlan.planView():[0,0,plan().width,plan().height];draw();return}
   if(action==='fit-section'){focusRoom();draw();return}
   if(action==='library'){catalogueOpen?closeCatalogue():openCatalogue();return}
   if(action==='reference'){if(!active())return toast('Select a furniture object first.');libraryOpen=false;popupOpen=true;render();return}

   if(action==='hide-popup'){popupOpen=false;libraryOpen=true;popover();return}



   if(action==='close'){if(pendingChanges()&&!confirm('Discard unsaved block changes?'))return;$('#modal').close();return}

   if(action==='apply-stair'){
    const v=active(),b=room().bbox,width=Number($('#stair-width').value)*b[2]/100,depth=v.preset_id==='staircase-spiral'?width*plan().width/plan().height:Number($('#stair-depth').value)*b[3]/100,height=Number($('#stair-height').value),angle=Number($('#stair-angle').value);
    if(!v||v.kind!=='stair')return;
    if(![width,depth,height,angle].every(Number.isFinite)||width<.005||width>1||depth<.005||depth>1||height<.01||height>5)throw Error('Enter valid staircase dimensions and a height between 0.01 and 5 m.');
    Object.assign(v,{width,depth:v.preset_id==='staircase-spiral'?width*plan().width/plan().height:depth,height_m:height,angle:(angle%360+360)%360});if(v.preset_id==='staircase-spiral'){v.flip_x=$('#stair-winding').value==='counterclockwise';v.flip_y=false;}delete v.physical_size;dirty=true;await call('check');return;
   }
   if(action==='add'){const b=r.bbox;selected=crypto.randomUUID();items.push({id:selected,kind:'unknown',label:'Block '+(items.length+1),x:b[0]+b[2]/2,y:b[1]+b[3]/2,width:b[2]*.2,depth:b[3]*.15,angle:0,seat_count:null});dirty=true;render();await call('check');return}

   if(action==='duplicate'){if(!v)return;if(items.length>=40)return toast('Use up to 40 objects in a section.');const copy=FurnitureLibrary.duplicate(v,plan(),crypto.randomUUID());items.push(copy);selected=copy.id;popupOpen=false;dirty=true;await call('check');if(v.asset_id)toast('Copy created. Choose a furniture reference for the new block.');return}

   if(action==='scale'){if(!v)return;const scaled=FurnitureLibrary.scale(v,Number($('#block-scale-percent').value)/100);Object.assign(v,scaled);dirty=true;await call('check');return}

   if(action==='split'){if(v){if(v.chair_modules&&v.chair_modules.columns*v.chair_modules.rows>1)return toast('Resize the group to change its chair count.');delete v.chair_modules;delete v.sofa_modules;const second={...v,id:crypto.randomUUID(),asset_id:null,label:v.label+' B',seat_count:null};const alongWidth=v.width*plan().width>=v.depth*plan().height;const key=alongWidth?'width':'depth';v[key]*=.47;second[key]=v[key];const t=v.angle*Math.PI/180,offset=v[key]*.55;const dx=alongWidth?offset*Math.cos(t):-offset*plan().height/plan().width*Math.sin(t),dy=alongWidth?offset*plan().width/plan().height*Math.sin(t):offset*Math.cos(t);v.x-=dx;v.y-=dy;second.x+=dx;second.y+=dy;items.push(second);dirty=true;await call('check')}return}

   if(action==='fetch-product')return await fetchProduct();

   if(action==='choose-product')return await chooseProduct(Number(button.dataset.photo));

   if(action==='remove-reference'){v.asset_id=null;dirty=true;await call('check');return;}
   if(action==='precise-size'||action==='apply-dimensions'){
    if(!v)return;const next=structuredClone(v),factor=unitFactor(),product=action==='apply-dimensions',prefix=product?'product-size-':'selected-',d=ctx.dimensions;
    const width=Number($('#'+prefix+'width').value)*factor,depth=Number($('#'+prefix+'depth').value)*factor,height=Number($('#'+prefix+'height').value)*factor;
    if(!d||![width,depth,height].every(x=>Number.isFinite(x)&&x>0)||height>5)throw Error('Enter positive dimensions using the selected units; height must be at most 5 m.');
    retainFloorAttachment(next);delete next.sofa_modules;delete next.chair_modules;next.width=width/d.width_m*r.bbox[2];next.depth=depth/d.depth_m*r.bbox[3];next.height_m=height;
    if(product){next.physical_size={width,depth,height,unit:'m'};next.dimension_status='reviewed';}
    else {const angle=Number($('#selected-angle').value);if(!Number.isFinite(angle))throw Error('Enter a finite rotation.');if(next.host_attachment?.kind==='wall'&&Math.abs(angle-v.angle)>.01)throw Error('Wall objects keep the host wall orientation.');next.angle=(angle%360+360)%360;
     const x=Number($('#selected-x').value)*factor,y=Number($('#selected-y').value)*factor;if(![x,y].every(Number.isFinite))throw Error('Enter finite position values.');next.x=r.bbox[0]+x/d.width_m*r.bbox[2];next.y=r.bbox[1]+y/d.depth_m*r.bbox[3];
     if($('#selected-elevation'))next.elevation_m=Number($('#selected-elevation').value)*factor;
     if($('#selected-drop')){next.host_attachment.drop=Number($('#selected-drop').value)*factor;if(!Number.isFinite(next.host_attachment.drop)||next.host_attachment.drop<0)throw Error('Ceiling drop must be zero or positive.');}
    }
    if(next.host_attachment?.kind==='wall'){const n=next.host_attachment.normal,shift=(next.depth-v.depth)*plan().height/2;next.x+=n[0]*shift/plan().width;next.y+=n[1]*shift/plan().height;}if(next.host_attachment?.kind==='ceiling')next.elevation_m=(modelFloor()?.scene.height||2.8)-next.height_m-next.host_attachment.drop;
    const error=validObjectPosition(next);if(error)throw Error(error);Object.assign(v,next);dirty=true;await call('check');return;
   }

   if(action==='upload'){const input=document.createElement('input');input.type='file';input.accept='image/png,image/jpeg,image/webp';input.onchange=()=>attach(input.files?.[0]).catch(err=>toast(err.message));input.click();return}

   if(action==='remove'){items=items.filter(x=>x.id!==selected);dirty=true;await call('check');return}

   if(['rotate','rotate-left','rotate-right','flip-x','flip-y'].includes(action)){if(v){if(action.startsWith('flip-')){const key=action==='flip-x'?'flip_x':'flip_y';v[key]=!v[key]}else v.angle=(v.angle+(action==='rotate-left'?-90:90)+360)%360;dirty=true;await call('check')}return}

   if(action==='suggest'&&!v)return toast('Add or select a block first.');

   if(action==='propose'&&items.length&&!confirm('Replace these draft blocks with detected furniture symbols?'))return;

   const result=await call(action,action==='save'?{reviewed:$('#block-reviewed').checked}:{});

   if(action==='save')toast(`Plan saved · ${result.saved_sections||1} section(s).`);

   if(action==='propose'&&!result.items.length)toast('No reliable object bounds were found. Add plain blocks over the visible symbols.');

  }catch(err){toast(err.message)}finally{button.disabled=false}

 });

 document.addEventListener('keydown',e=>{if(ctx&&modalType==='blocks'&&($('#modal').open||window.InlinePlan?.active())&&e.key==='Delete'&&!e.isComposing&&!e.target.closest('input,textarea,select,[contenteditable=true]')){e.preventDefault();if(multi.size){selectionAction('remove').catch(err=>toast(err.message));return}if(walls.selected){try{walls.action('remove')}catch(err){toast(err.message)}}else if(active())document.querySelector('[data-block=remove]')?.click()}});

 document.addEventListener('click',e=>{
  if(modalType!=='blocks'||!walls||busy)return;
  const tool=e.target.closest('[data-wall-tool]'),action=e.target.closest('[data-wall-action]');
  try{if(tool){walls.tool=tool.dataset.wallTool;walls.first=null;selected=null;popupOpen=false;draw()}if(action){const key=action.dataset.wallAction;if(key==='undo'||key==='redo')travelHistory(key==='redo').catch(err=>toast(err.message));else walls.action(key)}}catch(err){toast(err.message)}
 });
 document.addEventListener('keydown',e=>{if(e.target.closest('input,textarea,select,[contenteditable=true]'))return;if(e.key==='Escape'&&multi.size){multi.clear();render();return}if(e.key==='Escape'&&placement){placement=null;$('#placement-ghost')?.remove();walkControls();return}if(e.key==='Escape'&&catalogueOpen){closeCatalogue();return}if(modalType==='blocks'&&walls&&e.key==='Escape'&&(walls.first||walls.tool!=='select')){e.preventDefault();walls.clear();draw()}});
 document.addEventListener('input',e=>{
  if(modalType!=='blocks'||e.target.id!=='block-product-url'||!active())return;
  active().product_url=e.target.value;dirty=true;$('#block-reviewed').checked=false;
  if(productLookup?.block_id===selected){productLookup=null;if($('#block-product-result'))$('#block-product-result').innerHTML=''}
  if($('#block-product-status'))$('#block-product-status').textContent='';
 });
 document.addEventListener('input',e=>{if(e.target.id==='block-variant'&&active()){active().variant=e.target.value;dirty=true}});
 document.addEventListener('input',e=>{if(e.target.id==='block-prompt'&&active()){active().prompt=e.target.value;dirty=true;$('#block-reviewed').checked=false}});

 document.addEventListener('change',async e=>{

  if(e.target.id==='wall-snapping'&&walls){walls.snapping=e.target.checked;walls.guides=[];walls.drawGuides();return}
  if(!ctx||!e.target.id.startsWith('block-'))return;

  if(e.target.id==='block-product-url')return;
  if(e.target.id==='block-object-labels'){PlanLabels.setObjects(e.target.checked);return}
  if(e.target.id==='block-original-map'){ctx.showOriginal=e.target.checked;draw();return}

  if(e.target.id==='block-room'){try{await switchSection(e.target.value)}catch(err){toast(err.message)}return}

  if(e.target.id.startsWith('model-')||e.target.id.startsWith('product-size-'))return;
  const v=active();if(!v||['block-reviewed','block-scale-percent'].includes(e.target.id))return;

  const key=e.target.id.slice(6),b=room().bbox,value=e.target.value;

  if(key==='asset'){v.asset_id=value||null;dirty=true;await call('check');return}

  if(key==='dimension_status'){v.dimension_status=value;dirty=true;return}
  if(key==='variant'){v.variant=value;dirty=true;return}
  if(key==='prompt'){v.prompt=value;dirty=true;return}

  if(key==='kind'||key==='shape'){delete v.sofa_modules;delete v.chair_modules;}

  if(key==='label'||key==='kind'||key==='shape'||key==='return_side')v[key]=value;

  if(key==='width'||key==='depth')delete v.physical_size;

  if(key==='width'||key==='depth'){

   const size=Number(value)*b[key==='width'?2:3]/100;

   if(!Number.isFinite(size)||size<=0)return toast('Enter a positive size.');

    const a=v.angle*Math.PI/180,delta=(size-v[key])*plan()[key==='width'?'width':'height'];

    const point=key==='width'?[delta*Math.cos(a),delta*Math.sin(a)]:[-delta*Math.sin(a),delta*Math.cos(a)];

    const next=FurnitureLibrary.transform(v,plan(),key==='width'?'e':'s',[0,0],point);next.x=v.x;next.y=v.y;Object.assign(v,next);



  }

  if(key==='angle')v.angle=Number(value);

  if(key==='height_m')v.height_m=Number(value);
  if(key==='elevation_m')v.elevation_m=Number(value);

  if(key==='seats')FurnitureLibrary.seats(v,value);

  dirty=true;try{await call('check')}catch(err){toast(err.message)}

 });

 document.addEventListener('click',e=>{
  if(modalType!=='blocks'||!e.target.closest('[data-action="close-modal"]'))return;
  if(busy||pendingChanges()&&!confirm('Discard unsaved furniture changes in this window?')){e.preventDefault();e.stopImmediatePropagation()}
 },true);
 document.querySelector('#modal').addEventListener('cancel',e=>{if(modalType==='blocks'&&(busy||pendingChanges()&&!confirm('Discard unsaved furniture changes in this window?')))e.preventDefault()});
 window.FurnitureEditor={syncSaved,redraw:()=>draw(),fitFloor:()=>{ctx.focus='whole';ctx.view=InlinePlan.planView(room().floor);if(!modelView.walk)modelView={...BlockModelViewer.defaults(),projection:modelView.projection,transparent:modelView.transparent,edges:modelView.edges,cutaway:modelView.cutaway};render()},reload:()=>ctx&&openFurnitureBlocks(ctx.pid,ctx.rid,{reload:true,inline:true,view:ctx.view}),pending:()=>!!ctx&&pendingChanges(),roomId:()=>ctx?.rid,switchSection,dispose(){closeCatalogue();modelViewer?.dispose();modelViewer=null;if(zoomFrame)cancelAnimationFrame(zoomFrame);zoomFrame=null;zoomTarget=null;ctx=null;walls=null;history=null;dirty=false}};
})();

