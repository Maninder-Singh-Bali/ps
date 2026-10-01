'use strict';
(() => {
 let ed=null, previewTimer=null, sequence=0;
 const rectPoly=b=>[[b[0],b[1]],[b[0]+b[2],b[1]],[b[0]+b[2],b[1]+b[3]],[b[0],b[1]+b[3]]];
 const polyBounds=p=>{const x=p.map(v=>v[0]),y=p.map(v=>v[1]);return [Math.min(...x),Math.min(...y),Math.max(...x)-Math.min(...x),Math.max(...y)-Math.min(...y)]};
 const same=(a,b)=>JSON.stringify(a)===JSON.stringify(b);
 const button=(text,key,extra='')=>`<button type="button" class="btn small" data-area="${key}" ${extra}>${text}</button>`;
 function dirty(){ed.dirty=true;$('#area-save-state').textContent='Unsaved changes';ed.summary=null;$('#area-save').disabled=true;clearTimeout(previewTimer);sequence++;previewTimer=setTimeout(preview,180)}
 function payload(){return {floor:ed.floor,outline:ed.outline,sections:ed.sections.map(s=>({room_id:s.room_id||null,name:s.name,polygon:s.polygon,kind:s.kind})),exclusions:ed.holes,scale:ed.scale,map_revision:ed.mapRevision,area_revision:ed.areaRevision}}
 function target(){return ed.selected===-1?ed.outline:ed.selected<-1?ed.holes[-2-ed.selected]:ed.sections[ed.selected]?.polygon}
 function setTarget(p){if(ed.selected===-1)ed.outline=p;else if(ed.selected<-1)ed.holes[-2-ed.selected]=p;else ed.sections[ed.selected].polygon=p}
 function display(){return ed.original?ed.plan.id:ed.plan.cad_redraw_id||ed.plan.vector_preview_id||ed.plan.clear_preview_id||ed.plan.id}
 function hints(){
  $('#area-hint').textContent=ed.mode==='line'?'Click the two ends of a known length. Enter its real measurement on the right.':ed.mode==='draw'?`Click around ${ed.selected===-1?'the floor outline':ed.selected<-1?'the excluded area':ed.sections[ed.selected]?.name}. Follow the walls, then choose Finish outline. Undo removes the last corner.`:'Select a section to edit it. Drag its corner points or choose Redraw selected. Percentages update automatically.';
  document.querySelectorAll('[data-area="finish"],[data-area="undo"]').forEach(b=>b.hidden=!ed.mode);
  $('#area-selected-name').textContent=ed.selected===-1?'Floor outline':ed.selected<-1?'Excluded area':ed.sections[ed.selected]?.name||'';
 }
 function draw(){
  const w=ed.plan.width,h=ed.plan.height,view=ed.view;
  const svg=$('#area-svg');svg.setAttribute('viewBox',view.map((n,i)=>n*(i%2?h:w)).join(' '));
  const points=p=>p.map(v=>`${v[0]*w},${v[1]*h}`).join(' ');
  const physicalWidth=Math.max(1,svg.getBoundingClientRect().width),radius=view[2]*w/physicalWidth*5;
  const activePoly=target()||[];
  svg.innerHTML=(ed.cadMarkup&&!ed.original?`<g class="cad-redraw">${ed.cadMarkup}</g>`:`<image href="${url(display())}" x="0" y="0" width="${w}" height="${h}"/>`)+
   `<polygon class="area-outline" points="${points(ed.outline)}" data-area-region="-1"/>`+
   ed.sections.map((s,i)=>`<polygon class="area-region ${ed.selected===i?'selected':''}" points="${points(s.polygon)}" data-area-region="${i}"/>${s.polygon.length?`<text class="area-label" x="${(s.polygon.reduce((a,p)=>a+p[0],0)/s.polygon.length)*w}" y="${(s.polygon.reduce((a,p)=>a+p[1],0)/s.polygon.length)*h}">${i+1}</text>`:''}`).join('')+
   ed.holes.map((p,i)=>`<polygon class="area-void" points="${points(p)}" data-area-region="${-2-i}"/>`).join('')+
   (ed.scale.points?.length?`<polyline class="area-measure" points="${points(ed.scale.points)}"/>`:'')+
   (!ed.mode?activePoly.map((p,i)=>`<circle class="area-corner" cx="${p[0]*w}" cy="${p[1]*h}" r="${radius}" data-area-corner="${i}"/>`).join(''):'')+
   (ed.draft?.length?`<polyline class="area-measure" points="${points(ed.draft)}"/>`+ed.draft.map(p=>`<circle class="area-corner" cx="${p[0]*w}" cy="${p[1]*h}" r="${radius*.8}"/>`).join(''):'');
  document.querySelectorAll('[data-area-select]').forEach(el=>el.closest('tr')?.classList.toggle('selected',Number(el.dataset.areaSelect)===ed.selected));hints();
 }
 function fit(){const b=polyBounds(ed.outline),pad=.018;ed.view=[Math.max(0,b[0]-pad),Math.max(0,b[1]-pad),Math.min(1,b[0]+b[2]+pad)-Math.max(0,b[0]-pad),Math.min(1,b[1]+b[3]+pad)-Math.max(0,b[1]-pad)]}
 function fmt(n){return Number.isFinite(n)?n.toLocaleString(undefined,{maximumFractionDigits:2}):'—'}
 function areaText(n){return ed.scale.unit==='ft'?`${fmt(n/.09290304)} ft²`:`${fmt(n)} m²`}
 function list(){
  const result=ed.summary;
  $('#area-section-list').innerHTML=`<table class="area-list"><thead><tr><th>Section</th><th>Share</th><th>Area</th></tr></thead><tbody>${ed.sections.map((s,i)=>`<tr class="${i===ed.selected?'selected':''}"><td><button data-area-select="${i}">${i+1}. ${esc(s.name)}</button>${s.proposed?'<small>Boundary estimate</small>':''}</td><td>${result?fmt(result.percentages[i])+'%':'—'}</td><td>${result?.area_m2?areaText(result.area_m2.sections[i]):'—'}</td></tr>`).join('')}</tbody></table>`+ed.holes.map((p,i)=>`<p class="area-row-note"><button class="link-button" data-area-select="${-2-i}">Excluded area ${i+1}</button> · not counted</p>`).join('');
  $('#area-metrics').innerHTML=`<div class="area-metric"><small>Measured footprint</small><strong>${result?.area_m2?areaText(result.area_m2.total):result?'100%':'—'}</strong></div><div class="area-metric"><small>Unassigned area</small><strong>${result?fmt(result.remaining_percent)+'%':'—'}</strong>${result?.area_m2?`<small>${areaText(result.area_m2.remaining)}</small>`:''}</div>`;
  $('#area-warnings').innerHTML=result?`${result.overlap>1e-7?`<div class="area-notice">Sections overlap by ${fmt(result.overlap/result.total*100)}% of the footprint. The unassigned total counts shared space only once. Adjust the highlighted boundaries before treating the room totals as a division.</div>`:''}${result.outside>1e-7?'<div class="area-notice">Some section outlines extend outside the floor. Only the area inside the floor outline is counted.</div>':''}`:'';
 }
 async function preview(){
  const e=ed,id=++sequence;$('#area-error').textContent='Calculating from the outlines…';
  try{const result=await api(`/api/projects/${e.project}/plans/${e.plan.id}/area-preview`,payload());if(ed!==e||id!==sequence)return;ed.summary=result;$('#area-error').textContent='';$('#area-save').disabled=false;list()}
  catch(error){if(ed!==e||id!==sequence)return;ed.summary=null;$('#area-error').textContent=error.message;$('#area-save').disabled=true;list()}
 }
 function scaleFields(){
  const s=ed.scale;
  $('#area-scale-fields').innerHTML=s.mode==='percent'?'<p class="help">No measurements needed. Areas are shown as a share of this floor’s outline.</p>':
   s.mode==='dimensions'?`<div class="row-two"><label class="field"><span>Length · across drawing</span><input type="number" min="0.001" step="any" data-area-field="width" value="${s.width||''}" placeholder="e.g. 20"></label><label class="field"><span>Breadth · top to bottom</span><input type="number" min="0.001" step="any" data-area-field="height" value="${s.height||''}" placeholder="e.g. 15"></label></div><p class="help">Enter the full horizontal and vertical spans of this floor outline. Irregular floor shapes are measured within those spans.</p>`:
   `<label class="field"><span>${s.mode==='line'?'Known line length':'Known area of this outlined floor'}</span><input type="number" min="0.001" step="any" data-area-field="value" value="${s.value||''}" placeholder="Enter measurement"></label>${s.mode==='line'?button(s.points?.length===2?'Redraw measured line':'Mark measured line','line'):''}<p class="help">${s.mode==='line'?'One real length sets a uniform drawing scale. Use a straight, undistorted plan.':'This known area is distributed using each section’s proportion of the floor outline.'}</p>`;
 }
 document.addEventListener('click',e=>{if(!e.target.closest('[data-area="cad-units"]')||!ed?.plan.plan_source?.metres_per_pixel)return;ed.scale={mode:'line',unit:'m',points:[[.1,.5],[.9,.5]],value:ed.plan.width*.8*ed.plan.plan_source.metres_per_pixel};$('#area-method').value='line';$('#area-unit').value='m';scaleFields();dirty();toast('Declared DXF scale applied. Check a known dimension before relying on the areas.');});
 function loadFloor(floor){
  const p=P(),rec=p.measurements?.find(m=>m.plan_id===ed.plan.id&&m.floor===floor);
  const rooms=p.rooms.filter(r=>r.plan_id===ed.plan.id&&r.floor===floor&&r.bbox);
  ed.floor=floor;ed.sections=rooms.map(r=>({room_id:r.id,name:r.name,kind:r.kind,polygon:structuredClone(r.area_polygon&&same(r.area_bbox,r.bbox)?r.area_polygon:rectPoly(r.bbox)),proposed:!(r.area_polygon&&same(r.area_bbox,r.bbox))}));
  const construction=ed.plan.construction_selection?.confirmed&&ed.plan.construction_selection.floor===floor?ed.plan.construction_selection:null;
  ed.holes=structuredClone(rec?.exclusions||construction?.exclusions||[]);
  const suggestion=ed.plan.floor_outlines?.find(f=>f.floor===floor)?.polygon;
  ed.outline=structuredClone(rec?.outline||suggestion||(construction?.regions.length===1?construction.regions[0]:null)||rectPoly(rooms.length?polyBounds(ed.sections.flatMap(r=>r.polygon)):[.05,.05,.9,.85]));
  ed.scale=structuredClone(rec?.scale||{mode:'percent',unit:'m'});ed.selected=-1;ed.mode=null;ed.draft=[];ed.summary=null;ed.dirty=false;ed.mapRevision=p.map_revision;ed.areaRevision=p.area_revision||0;fit();
 }
 function render(){
  const floors=[...new Set([...P().rooms.filter(r=>r.plan_id===ed.plan.id).map(r=>r.floor),...P().measurements?.filter(m=>m.plan_id===ed.plan.id).map(m=>m.floor)||[],ed.floor])];
  showModal('Area & section ratios',`<div class="area-top">${button('Walls, doors & sunlight','drawing')}<label>Floor <select id="area-floor" class="control">${floors.map(f=>`<option ${f===ed.floor?'selected':''}>${esc(f)}</option>`).join('')}</select></label><label><input type="checkbox" id="area-original" ${ed.original?'checked':''}> Show original plan</label><span class="area-summary-chip">Measured from drawing proportions · estimate</span></div><div class="area-editor"><section><div class="area-tools">${button('Fit floor','fit')}${button('Full page','full')}${button('Redraw selected','redraw')}${button('Exclude void','void')}${button('Remove draft / exclusion','remove')}${button('Finish outline','finish','hidden')}${button('Undo point','undo','hidden')}<span id="area-selected-name" class="help"></span></div><div class="area-canvas"><svg id="area-svg" role="img" aria-label="Editable floor and room area outlines"></svg></div><p id="area-hint" class="area-hint"></p><div class="area-new"><input id="area-new-name" placeholder="New section name, e.g. Bathroom" aria-label="New section name">${button('Draw new section','add')}</div><p class="help">Follow walls to divide the unassigned parts. Existing mapped sections are starting estimates; drag corners to refine them. Use Exclude void for courtyards or openings that must not count toward floor area.</p></section><aside class="area-aside"><div class="area-scale"><h3>Measurement method</h3>${ed.plan.plan_source?.metres_per_pixel?button('Use declared DXF units','cad-units'):''}<label class="field"><span>Calculate using</span><select id="area-method">${[['percent','Proportions only (%)'],['dimensions','Known length & breadth'],['line','One known line length'],['area','Known total floor area']].map(([v,l])=>`<option value="${v}" ${ed.scale.mode===v?'selected':''}>${l}</option>`).join('')}</select></label><label class="field"><span>Measurement units</span><select id="area-unit"><option value="m" ${ed.scale.unit==='m'?'selected':''}>Metres / m²</option><option value="ft" ${ed.scale.unit==='ft'?'selected':''}>Feet / ft²</option></select></label><div id="area-scale-fields"></div></div><div id="area-metrics" class="area-metrics"></div>${button('Select floor outline','outline')}<div id="area-section-list"></div><div id="area-warnings"></div><p id="area-error" class="area-error" role="status"></p><p class="help">This is an estimate from the drawing. Each floor has its own scale; whitespace, legends and other floors are outside its outline.</p></aside></div>`,`<span id="area-save-state" class="area-status">${P().measurements?.some(m=>m.plan_id===ed.plan.id&&m.floor===ed.floor)?'Saved measurement loaded':'Review the suggested boundaries'}</span>${btn('Cancel','close-modal','','ghost')}<button type="button" id="area-save" class="btn primary" data-area="save" disabled>Save areas & sections</button>`,'area');
  $('#modal').classList.add('area-dialog');scaleFields();draw();list();bindPointer();preview();
 }
 window.openPlanAreas=async function(selectedRoomId){
  const plan=A(tab==='plan'?planId||R()?.plan_id:R()?.plan_id||planId);if(!plan)return toast('Upload a floor plan first.');
  ed={project:pid,plan,original:false};const opened=ed;
  if(plan.cad_redraw_id){try{const raw=await (await fetch(url(plan.cad_redraw_id))).text();if(ed!==opened)return;const doc=new DOMParser().parseFromString(raw,'image/svg+xml');const allowed=new Set(['g','path','rect','circle','ellipse','text','polyline','line']),attrs=new Set(['class','d','x','y','width','height','rx','ry','cx','cy','r','transform','font-size','points','x1','x2','y1','y2']);const clean=node=>{if(!allowed.has(node.localName)||node.localName==='text'&&/^\d+$/.test(node.textContent.trim())||node.localName==='rect'&&node.getAttribute('style')?.includes('fill:white'))return '';return '<'+node.localName+' '+[...node.attributes].filter(a=>attrs.has(a.name)).map(a=>a.name+'="'+esc(a.value)+'"').join(' ')+'>'+(node.localName==='text'?esc(node.textContent):[...node.children].map(clean).join(''))+'</'+node.localName+'>'};ed.cadMarkup=[...doc.documentElement.children].map(clean).join('');}catch{}}
  loadFloor(!selectedRoomId&&plan.construction_selection?.confirmed?plan.construction_selection.floor:R()?.plan_id===plan.id?R().floor:P().rooms.find(r=>r.plan_id===plan.id)?.floor||'Ground floor');if(selectedRoomId){ed.selected=ed.sections.findIndex(s=>s.room_id===selectedRoomId);const b=R()?.bbox;if(b)ed.view=[Math.max(0,b[0]-.02),Math.max(0,b[1]-.02),b[2]+.04,b[3]+.04]}render();
 };
 function pointer(e){
  const svg=$('#area-svg'),r=svg.getBoundingClientRect(),vb=ed.view,w=ed.plan.width,h=ed.plan.height;
  // SVG preserves its aspect ratio and may have letterboxing inside its element.
  const ratio=Math.min(r.width/(vb[2]*w),r.height/(vb[3]*h)),ox=(r.width-vb[2]*w*ratio)/2,oy=(r.height-vb[3]*h*ratio)/2;
  return [Math.max(0,Math.min(1,vb[0]+(e.clientX-r.left-ox)/ratio/w)),Math.max(0,Math.min(1,vb[1]+(e.clientY-r.top-oy)/ratio/h))];
 }
 function bindPointer(){
  const svg=$('#area-svg');let drag=null;
  svg.onpointerdown=e=>{
   if(e.button!==0)return;const point=pointer(e);e.preventDefault();
   if(ed.mode){ed.draft.push(point);if(ed.mode==='line'&&ed.draft.length===2){ed.scale.points=ed.draft;ed.draft=[];ed.mode=null;scaleFields();dirty()}draw();return}
   const handle=e.target.closest('[data-area-corner]'),region=e.target.closest('[data-area-region]');
   if(handle){drag={index:Number(handle.dataset.areaCorner),before:structuredClone(target())};svg.setPointerCapture(e.pointerId)}
   else if(region){ed.selected=Number(region.dataset.areaRegion);draw()}
  };
  svg.onpointermove=e=>{if(drag){target()[drag.index]=pointer(e);draw();dirty()}};
  svg.onpointerup=e=>{if(drag){drag=null;if(ed.selected>=0)ed.sections[ed.selected].proposed=false;svg.releasePointerCapture(e.pointerId);dirty()}};
  svg.onpointercancel=()=>{if(drag){setTarget(drag.before);drag=null;draw();dirty()}};
 }
 document.addEventListener('click',async e=>{
  if(e.target.closest('[data-action="plan-areas"]')){openPlanAreas();return}
  if(!ed||!$('#modal').open||modalType!=='area')return;
  const sel=e.target.closest('[data-area-select]');if(sel){ed.selected=Number(sel.dataset.areaSelect);ed.mode=null;ed.draft=[];draw();return}
  const b=e.target.closest('[data-area]');if(!b)return;
  const action=b.dataset.area;
  if(action==='drawing'){if(ed.dirty)return toast('Save your area changes before opening drawing details.');openDrawingEditor();return}
  if(action==='fit'){fit();draw()}
  if(action==='full'){ed.view=[0,0,1,1];draw()}
  if(action==='outline'){ed.selected=-1;ed.mode=null;ed.draft=[];draw()}
  if(action==='redraw'){ed.mode='draw';ed.draft=[];draw()}
  if(action==='line'){ed.mode='line';ed.draft=[];draw()}
  if(action==='undo'){ed.draft.pop();draw()}
  if(action==='finish'){
   if(ed.mode==='line'){ed.mode=null;ed.draft=[];draw();return}
   if(ed.draft.length<3)return toast('Choose at least three outline corners.');
   setTarget(ed.draft);if(ed.selected>=0)ed.sections[ed.selected].proposed=false;ed.draft=[];ed.mode=null;draw();dirty();
  }
  if(action==='void'){ed.holes.push([]);ed.selected=-1-ed.holes.length;ed.mode='draw';ed.draft=[];list();draw();dirty()}
  if(action==='remove'){if(ed.selected<-1){ed.holes.splice(-2-ed.selected,1)}else if(ed.selected>=0&&!ed.sections[ed.selected].room_id){ed.sections.splice(ed.selected,1)}else return toast('Only unsaved new sections or exclusions can be removed here.');ed.selected=-1;ed.mode=null;ed.draft=[];list();draw();dirty()}
  if(action==='add'){
   const name=$('#area-new-name').value.trim();if(!name)return toast('Enter a name for the new section.');
   ed.sections.push({room_id:null,name,kind:'room',polygon:[],proposed:false});ed.selected=ed.sections.length-1;ed.mode='draw';ed.draft=[];ed.summary=null;$('#area-new-name').value='';list();draw();dirty();
  }
  if(action==='save'){
   if(ed.mode)return toast('Finish the outline before saving.');
   b.disabled=true;const captured=ed;
   try{await api(`/api/projects/${ed.project}/plans/${ed.plan.id}/area`,payload());await refresh(true);if(ed===captured){loadFloor(captured.floor);render();$('#area-save-state').textContent='Areas and sections saved';toast('Areas saved. Updated section boundaries need room-map review.')}}
   catch(error){toast(error.message);b.disabled=false}
  }
 });
 document.addEventListener('change',e=>{
  if(!ed||modalType!=='area'||!$('#modal').open)return;
  if(e.target.id==='area-floor'){
   if(ed.dirty){e.target.value=ed.floor;return toast('Save this floor’s changes before switching floors.')}
   loadFloor(e.target.value);render();
  }
  if(e.target.id==='area-method'){ed.scale={mode:e.target.value,unit:ed.scale.unit};ed.mode=null;ed.draft=[];scaleFields();draw();dirty()}
  if(e.target.id==='area-unit'){const f=ed.scale.unit===e.target.value?1:e.target.value==='m'?.3048:1/.3048;if(ed.scale.width)ed.scale.width*=f;if(ed.scale.height)ed.scale.height*=f;if(ed.scale.value)ed.scale.value*=ed.scale.mode==='area'?f*f:f;ed.scale.unit=e.target.value;scaleFields();dirty()}
  if(e.target.id==='area-original'){ed.original=e.target.checked;draw()}
 });
 document.addEventListener('input',e=>{if(ed&&e.target.dataset.areaField){ed.scale[e.target.dataset.areaField]=Number(e.target.value);dirty()}});
})();
