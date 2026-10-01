'use strict';
(() => {
 const planOriginalModes=new Map();
 let study=null,selected=null,view=[0,0,1,1],drawing=false,drag=null,dirty=false,original=true,showRejected=false;
 const rect=b=>[[b[0],b[1]],[b[0]+b[2],b[1]],[b[0]+b[2],b[1]+b[3]],[b[0],b[1]+b[3]]];
 const bounds=p=>{let x=p.map(q=>q[0]),y=p.map(q=>q[1]);return [Math.min(...x),Math.min(...y),Math.max(...x)-Math.min(...x),Math.max(...y)-Math.min(...y)]};
 const current=()=>study.doc.features.find(f=>f.id===selected);
 const button=(text,action,cls='')=>`<button type="button" class="btn small ${cls}" data-study="${action}">${text}</button>`;
 const endpoint=action=>`/api/projects/${study.pid}/plans/${study.aid}/${action}`;
 function changed(){dirty=true;study.doc.reviewed=false;$('#study-state').textContent='Unsaved corrections';}
 function options(rows,value){return rows.map(([v,l])=>`<option value="${esc(v)}" ${v===value?'selected':''}>${esc(l)}</option>`).join('')}
 window.augmentPlanReading=function(){
  if(tab!=='plan'||!planId)return;
  const a=A(planId),doc=a?.plan_reading,head=$('.plan-toolbar');if(!head||$('#study-summary'))return;
  const confirmed=doc?.features.filter(f=>f.review_status==='confirmed').length||0,pending=doc?.features.filter(f=>f.review_status==='pending').length||0;
  head.insertAdjacentHTML('afterend',`<div id="study-summary" class="study-summary"><div><strong>Architectural study</strong><small>${doc?`${confirmed} confirmed · ${pending} to review`:'Read the structure, then confirm what the symbols mean.'}${doc?.reviewed?' · Reviewed':''}</small></div>${button('Study structure','open','primary')}</div><div class="study-source-line">${a?.plan_source?`${esc(a.plan_source.format)} · ${a.plan_source.vector?'Native vector geometry':'Scanned page'} · ${esc(a.plan_source.units||'Scale not set')}`:'Image plan · ratios only until calibrated'}${a?.cad_redraw_id||a?.vector_preview_id?'<label><input type="checkbox" id="plan-original-toggle" checked> Show original</label>':''}</div>`);
  const stage=$('#plan-stage'),pageId=planId,projectId=pid;
  let renderVersion=0;
  const savedFurniture=()=>P().rooms.filter(r=>r.plan_id===pageId).flatMap(r=>(r.block_layout?.items||[]).map(v=>({v,roomId:r.id})));
  async function showPlan(original){
   const version=++renderVersion;planOriginalModes.set(pageId,original);
   const image=stage.querySelector('img');image.style.visibility='';image.src=url(original?pageId:a.cad_redraw_id||a.vector_preview_id||pageId);
   stage.querySelector('#plan-library-overlay')?.remove();stage.querySelector('#plan-corrected-overlay')?.remove();
   const furniture=savedFurniture();
   if(original)return;
   if(window.FurnitureLibrary)stage.insertAdjacentHTML('beforeend',`<svg id="plan-library-overlay" aria-label="Library furniture across the whole plan" viewBox="0 0 ${a.width} ${a.height}" style="position:absolute;inset:0;width:100%;height:100%;pointer-events:none">${furniture.map(({v,roomId})=>`<g data-plan-block-id="${v.id}" data-plan-block-room="${roomId}" class="drawing-library-furniture" transform="translate(${v.x*a.width} ${v.y*a.height}) rotate(${v.angle}) translate(${-v.width*a.width/2} ${-v.depth*a.height/2}) scale(${v.width*a.width/100} ${v.depth*a.height/100})">${FurnitureLibrary.symbol(v)}</g>`).join('')}</svg>`);
   try{
    const drawing=await api(`/api/projects/${projectId}/plans/${pageId}/drawing`,{},'GET');
    if(version!==renderVersion||stage!==$('#plan-stage')||!window.DrawingPreview||!(drawing.elements.length||drawing.features.length))return;
    image.style.visibility='hidden';
    image.insertAdjacentHTML('afterend',`<svg id="plan-corrected-overlay" aria-label="Current corrected floor plan" viewBox="0 0 ${a.width} ${a.height}" style="position:absolute;inset:0;width:100%;height:100%;pointer-events:none"><rect width="${a.width}" height="${a.height}" fill="white"/>${DrawingPreview.markup(drawing)}</svg>`);
    DrawingPreview.finish(stage.querySelector('#plan-corrected-overlay'));
   }catch(err){if(stage===$('#plan-stage'))toast('Could not refresh the corrected plan: '+err.message)}
  }
  $('#plan-original-toggle')?.addEventListener('change',e=>showPlan(e.target.checked));
  const useOriginal=planOriginalModes.get(pageId)??!savedFurniture().length;
  if($('#plan-original-toggle'))$('#plan-original-toggle').checked=useOriginal;
  showPlan(useOriginal);

 };
 window.openPlanStudy=()=>open();
 async function open(){
  const aid=tab==='plan'?planId||R()?.plan_id:R()?.plan_id||planId;if(!aid)return toast('Upload a floor plan first.');
  const project=pid,doc=await api(`/api/projects/${project}/plans/${aid}/reading`,{},'GET');
  study={pid:project,aid,doc};selected=doc.features.find(f=>f.review_status==='confirmed')?.id||doc.features[0]?.id;view=[0,0,1,1];drawing=false;dirty=false;original=true;showRejected=false;render();
 }
 function render(){
  const d=study.doc,a=A(study.aid);showModal('Read the architecture',`<div class="study-top"><p>Study each symbol in context. Confirm, correct or reject proposals before approving the room map.</p><div class="actions">${button('Enhance & detect','detect')}${button('Scan structure','scan')}${button('Mark a feature','mark')}${button('Fit page','fit')}${button('Zoom +','in')}${button('Zoom −','out')}${button('Refine lines','lines')}${button('Area & sections','areas')}</div></div><div class="study-grid"><section class="study-drawing"><div class="study-view-options"><label><input id="study-original" type="checkbox" ${original?'checked':''}> Original drawing</label><label><input id="study-rejected" type="checkbox" ${showRejected?'checked':''}> Rejected proposals</label><span>Green: confirmed · Amber: needs review</span></div><div class="study-canvas"><svg id="study-svg" role="img" aria-label="Architectural symbols on the floor plan"></svg></div><p id="study-hint" class="help"></p><details class="study-key"><summary>Architectural symbol guide</summary><div>${d.rules.map(r=>`<article><strong>${esc(r.title)}</strong><p>${esc(r.evidence)}</p></article>`).join('')}</div></details></section><aside><div id="study-list" class="study-list"></div><div id="study-feature"></div><details class="study-checks"><summary>Review completeness</summary>${[['walls','Walls, curves and openings match the drawing'],['openings','Door swings and glazing are distinguished'],['rooms','Room divisions and floor assignments checked'],['stairs','Stairs checked; missing connections recorded']].map(([k,t])=>`<label><input type="checkbox" data-study-check="${k}" ${d.checks[k]?'checked':''}> ${t}</label>`).join('')}</details><div class="study-limits">${d.elapsed_seconds!=null?`Last scan: ${d.elapsed_seconds.toFixed(2)} seconds.<br>`:''}Automatic outlines are proposals. Review against the original; scale and connections may be unknown.</div></aside></div><p id="study-error" role="status"></p>`,`<span id="study-state">${d.reviewed?'Study reviewed':dirty?'Unsaved corrections':'Saved plan study'}</span>${button('Save corrections','save')}${button('Mark study reviewed','review','primary')}`,'plan-study');
  $('#modal').classList.add('plan-study-dialog');draw();list();editor();bindCanvas();
  $('#study-original').onchange=e=>{original=e.target.checked;draw()};$('#study-rejected').onchange=e=>{showRejected=e.target.checked;draw();list()};
 }
 function draw(){
  const d=study.doc,a=A(study.aid),w=d.width,h=d.height,svg=$('#study-svg');if(!svg)return;
  svg.setAttribute('viewBox',view.map((v,i)=>v*(i%2?h:w)).join(' '));
  const pixels=Math.max(.01,svg.getScreenCTM()?.a||1),font=12/pixels,pad=4/pixels;
  svg.innerHTML=`<rect width="${w}" height="${h}" fill="white"/><image href="${url(original?study.aid:a?.cad_redraw_id||a?.vector_preview_id||study.aid)}" width="${w}" height="${h}"/>`+
   d.features.filter(f=>(showRejected||f.review_status!=='rejected')&&!(f.kind==='space'&&f.connection_room_id)).map((f,i)=>{let b=f.bbox,p=f.polygon||rect(b);return `<g data-study-feature="${f.id}" class="study-symbol ${f.review_status} ${selected===f.id?'selected':''}"><polygon points="${p.map(q=>q[0]*w+','+q[1]*h).join(' ')}"/><text x="${b[0]*w+pad}" y="${b[1]*h+font+pad}" font-size="${font}">${selected===f.id?esc(f.label):i+1}</text></g>`}).join('');
  if(drag){let b=bounds([drag.start,drag.end]);svg.innerHTML+=`<rect class="study-draft" x="${b[0]*w}" y="${b[1]*h}" width="${b[2]*w}" height="${b[3]*h}"/>`}
  $('#study-hint').textContent=drawing?'Drag a box around one symbol. Then choose its meaning and floor.':'Open-space connections are listed at the right without lines across the plan. Coloured boxes mark review areas, not walls.';
 }
 function list(){
  $('#study-list').innerHTML=study.doc.features.filter(f=>showRejected||f.review_status!=='rejected').map(f=>`<button class="study-row ${f.review_status} ${f.id===selected?'selected':''}" data-study-select="${f.id}"><span>${f.review_status==='confirmed'?'✓':f.review_status==='rejected'?'×':'?'}</span><div><strong>${esc(f.label)}</strong><small>${esc(f.floor||'Floor not assigned')} · ${f.review_status}</small></div></button>`).join('')||'<p class="help">Scan this drawing or mark a missed symbol. No features have been confirmed.</p>';
 }
 function editor(){
  const f=current(),el=$('#study-feature');if(!f){el.innerHTML='';return}
  const rooms=state.projects[study.pid].rooms,local=rooms.filter(r=>r.plan_id===study.aid);
  el.innerHTML=`<form id="study-form"><label class="field"><span>Feature meaning</span><select data-study-field="kind">${options(Object.entries(study.doc.kinds),f.kind)}</select></label><label class="field"><span>Name</span><input data-study-field="label" value="${esc(f.label)}"></label><div class="row-two"><label class="field"><span>Floor</span><input data-study-field="floor" list="study-floors" value="${esc(f.floor)}" placeholder="e.g. Lower floor"><datalist id="study-floors">${[...new Set(rooms.map(r=>r.floor))].map(s=>`<option value="${esc(s)}">`).join('')}</datalist></label><label class="field"><span>Review</span><select data-study-field="review_status">${options([['pending','Needs review'],['confirmed','Confirmed'],['rejected','Rejected']],f.review_status)}</select></label></div><label class="field"><span>Belongs to section</span><select data-study-field="room_id">${options([['','Use location on plan'],...local.map(r=>[r.id,r.name])],f.room_id||'')}</select></label>${f.kind==='stair'?`<label class="field"><span>Stair form</span><select data-study-field="shape">${options(['unspecified','straight','L-shaped','U-shaped','curved','spiral'].map(v=>[v,v]),f.shape)}</select></label>`:''}<label class="field"><span>${f.kind==='stair'?'Connected landing / section':'Shared with section'}</span><select data-study-field="connection_room_id">${options([['','Not linked — exterior or unresolved'],...(f.kind==='stair'?rooms:local.filter(r=>!f.floor||r.floor===f.floor)).filter(r=>r.id!==f.room_id).map(r=>[r.id,r.floor+' · '+r.name])],f.connection_room_id||'')}</select></label><p class="help">${f.kind==='space'&&f.connection_room_id?'Open connection — no dividing wall. The saved bounds locate the relationship; they are not construction lines.':'Link adjoining sections to one shared feature on the full plan. Both views use its position and meaning.'}</p><label class="field"><span>Object type (for furniture)</span><input data-study-field="object_type" value="${esc(f.object_type||'')}" placeholder="Sofa, side table, armchair..."></label><label class="field"><span>Seat count (leave blank if unknown)</span><input data-study-field="seat_count" type="number" min="1" max="12" value="${f.seat_count||''}"></label><label class="field"><span>Correction / connection notes</span><textarea data-study-field="notes" rows="2">${esc(f.notes)}</textarea></label><p class="study-evidence"><strong>Evidence</strong><br>${esc(f.evidence)}</p><div class="actions">${f.kind==='space'&&!f.room_id?button('Add as room section','section'):''}${button('Focus','focus')}${button('Redraw bounds','redraw')}${button('Reject','reject')}</div></form>`;
 }
 function point(e){let svg=$('#study-svg'),q=new DOMPoint(e.clientX,e.clientY).matrixTransform(svg.getScreenCTM().inverse());return [Math.max(0,Math.min(1,q.x/study.doc.width)),Math.max(0,Math.min(1,q.y/study.doc.height))]}
 function bindCanvas(){
  const svg=$('#study-svg');svg.onpointerdown=e=>{if(e.button!==0)return;if(drawing){drag={start:point(e),end:point(e)};svg.setPointerCapture(e.pointerId);e.preventDefault()}else{const f=e.target.closest('[data-study-feature]');if(f){selected=f.dataset.studyFeature;list();editor();draw()}}};
  svg.onpointermove=e=>{if(drag){drag.end=point(e);draw()}};
  svg.onpointercancel=()=>{drag=null;draw()};
  svg.onpointerup=e=>{if(!drag)return;drag.end=point(e);const b=bounds([drag.start,drag.end]);drag=null;if(Math.min(b[2],b[3])<.002)return draw();
   if(drawing==='redraw'&&current()){current().bbox=b;current().polygon=null;current().review_status='pending'}else{const f={id:crypto.randomUUID().replaceAll('-',''),kind:'unknown',label:'New feature',bbox:b,floor:'',room_id:null,connection_room_id:null,review_status:'pending',source:'manual',notes:'',evidence:'User-marked symbol',shape:'unspecified'};study.doc.features.push(f);selected=f.id}drawing=false;changed();draw();list();editor()};
  svg.ondblclick=e=>{if(!drawing&&current())focus()};
 }
 function focus(){const b=current()?.bbox;if(!b)return;view=[Math.max(0,b[0]-.04),Math.max(0,b[1]-.04),Math.min(1,b[2]+.08),Math.min(1,b[3]+.08)];draw()}
 async function save(reviewed=false){
  const result=await api(endpoint('reading'),{revision:study.doc.revision,map_revision:study.doc.map_revision,features:study.doc.features,checks:study.doc.checks,reviewed});study.doc=result;dirty=false;await refresh(true);render();
 }
 document.addEventListener('input',e=>{const el=e.target;if(!el.dataset.studyField||!current())return;current()[el.dataset.studyField]=el.value||null;changed();if(el.dataset.studyField==='room_id'&&el.value){current().floor=state.projects[study.pid].rooms.find(r=>r.id===el.value)?.floor||current().floor;editor()}if(el.dataset.studyField==='kind'){current().label=study.doc.kinds[el.value];editor()}list();draw()});
 document.addEventListener('change',e=>{if(e.target.dataset.studyCheck){study.doc.checks[e.target.dataset.studyCheck]=e.target.checked;changed()}});
 document.addEventListener('click',async e=>{
  const row=e.target.closest('[data-study-select]');if(row){selected=row.dataset.studySelect;list();editor();draw();return}
  const b=e.target.closest('[data-study]');if(!b)return;const action=b.dataset.study;b.disabled=true;
  try{
   if(action==='open')return await open();
   $('#study-error').textContent='';
   if(action==='save'||action==='review')await save(action==='review');
   else if(action==='detect'){if(dirty)await save(false);await window.openStructureCheck()}
   else if(action==='scan'){if(dirty)await save(false);$('#study-state').textContent='Reading the drawing locally…';study.doc=await api(endpoint('study'),{revision:study.doc.revision});selected=study.doc.features[0]?.id;await refresh(true);render()}
   else if(action==='mark'||action==='redraw'){drawing=action==='redraw'?'redraw':true;draw()}
   else if(action==='section'){if(dirty)await save(false);const result=await api(endpoint('study-section'),{revision:study.doc.revision,map_revision:study.doc.map_revision,feature_id:selected});study.doc=result.reading;await refresh(true);render();toast('Section added. Refine its boundary in Area & sections.')}
   else if(action==='focus')focus();
   else if(action==='fit'){view=[0,0,1,1];draw()}
   else if(action==='in'||action==='out'){let k=action==='in'?.75:1.333;view=[Math.max(0,view[0]+view[2]*(1-k)/2),Math.max(0,view[1]+view[3]*(1-k)/2),Math.min(1,view[2]*k),Math.min(1,view[3]*k)];draw()}
   else if(action==='reject'&&current()){current().review_status='rejected';changed();draw();list();editor()}
   else if(action==='lines'||action==='areas'){if(dirty)await save(false);$('#modal').close();planId=study.aid;if(action==='lines')window.openDrawingEditor?.();else window.openPlanAreas?.()}
  }catch(err){if($('#study-error'))$('#study-error').textContent=err.message;else toast(err.message)}finally{b.disabled=false}
 });
})();

