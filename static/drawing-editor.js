'use strict';
(() => {
 let d=null,solarTimer=null,solarSeq=0;
 const control=(label,key,cls='')=>`<button type="button" class="btn small ${cls}" data-drawing="${key}">${label}</button>`;
 const clone=v=>structuredClone(v);
 const newId=()=> 'new'+crypto.randomUUID().replaceAll('-','');
 function validateRequired(){
  const missing=[];
  document.querySelectorAll('#modal [aria-invalid=true]').forEach(el=>el.removeAttribute('aria-invalid'));
  if(document.querySelector('[data-site="sun_enabled"]')?.checked){
   for(const [selector,label,check] of [
    ['#site-coordinates','Location coordinates',el=>el.value.trim()],
    ['[data-site="date"]','Scene date',el=>el.value],
    ['[data-site="time"]','Scene time',el=>el.value],
    ['[data-site="north_confirmed"]','Confirmed north direction',el=>el.checked],
    ['[data-site="north_angle"]','North angle',el=>el.value!==''&&Number.isFinite(Number(el.value))]
   ]){const el=document.querySelector(selector);if(!el||!check(el)){missing.push({el,label});el?.setAttribute('aria-invalid','true')}}
  }
  const alert=$('#drawing-validation');
  if(missing.length){const message='Not saved. Complete: '+missing.map(v=>v.label).join(', ')+'.';alert.textContent=message;alert.hidden=false;$('#drawing-status').textContent=message;toast(message);missing[0].el?.focus();return false}
  alert.hidden=true;alert.textContent='';return true;
 }
 function editableWall(requireWall=true){
  const f=d.features.find(v=>v.id===d.selected);
  if(f){if(requireWall&&f.kind!=='wall')throw Error('Select a wall first.');return clone(f)}
  const source=d.elements.find(v=>v.id===d.selected),el=document.querySelector(`[data-element="${d.selected}"]`);
  if(source?.kind!=='wall'||!el)throw Error('Select a straight wall. Use Add wall to trace an unclassified scanned outline first.');
  const box=el.getBBox();if(Math.max(box.width,box.height)<4*Math.max(.1,Math.min(box.width,box.height)))throw Error('This outline contains more than one direction. Trace the intended wall with Add wall first.');
  const m=el.transform.baseVal.consolidate()?.matrix;
  const points=(box.width>=box.height?[[box.x,box.y+box.height/2],[box.x+box.width,box.y+box.height/2]]:[[box.x+box.width/2,box.y],[box.x+box.width/2,box.y+box.height]]).map(([x,y])=>{const p=m?new DOMPoint(x,y).matrixTransform(m):{x,y};return[p.x,p.y]});
  return {id:d.selected,kind:'wall',points,thickness:Math.max(.1,Math.min(50,Math.min(box.width,box.height)||1.5)),flip:false};
 }
 function selectionFields(f){
  const picker=$('#drawing-element-picker');if(picker)picker.value=d.selected||'';
  const holder=$('#drawing-size-fields');if(!holder)return;
  try{f=f||editableWall(false)}catch{f=null}
  holder.innerHTML=f?`<div class="drawing-tools"><label>Length (drawing units) <input id="drawing-length" type="number" min=".2" step=".1" value="${Math.hypot(f.points[1][0]-f.points[0][0],f.points[1][1]-f.points[0][1]).toFixed(2)}"></label><label>Wall thickness <input id="drawing-thickness" type="number" min=".1" max="50" step=".1" value="${f.thickness}"></label>${control('Apply size','resize')}</div>`:'';
 }
 function hitAreas(){
  const picker=$('#drawing-element-picker');if(picker)picker.innerHTML='<option value="">Choose a wall, opening or object…</option>'+[...d.elements.filter(v=>!v.absorbed_by&&!d.edits[v.id]?.hidden),...d.features.filter(v=>v.kind!=='floor_opening')].map((v,i)=>`<option value="${v.id}" ${v.id===d.selected?'selected':''}>${i+1} · ${esc(v.native_rectangle?'Filled vector rectangle · '+typeName(d.edits[v.id]?.kind||v.kind):typeName(v.kind))}</option>`).join('');
  document.querySelectorAll('#drawing-svg [data-element]').forEach(el=>{
   if(el.dataset.element===d.selected)el.classList.add('drawing-active');
   if(d.elements.find(v=>v.id===el.dataset.element)?.kind==='wall')solidWall(el);
   for(const path of [...el.querySelectorAll('path,line,polyline,polygon,rect,circle,ellipse')]){const hit=path.cloneNode(false);hit.removeAttribute('id');hit.setAttribute('class','drawing-hit');hit.setAttribute('style','fill:none!important;stroke:transparent!important;stroke-width:12px!important;vector-effect:non-scaling-stroke;pointer-events:stroke');path.parentNode.insertBefore(hit,path)}
  });
 }
 function solidWall(el){
  const b=el.getBBox();if(Math.max(b.width,b.height)>=4*Math.max(.1,Math.min(b.width,b.height))){
   const horizontal=b.width>=b.height,t=Math.min(b.width,b.height)||1.5;
   el.innerHTML=`<rect class="wall wall-solid" x="${b.x-(horizontal?0:(t-b.width)/2)}" y="${b.y-(horizontal?(t-b.height)/2:0)}" width="${horizontal?b.width:t}" height="${horizontal?t:b.height}"/>`;
  }
 }
 // Inline geometry shares the editor's screen-sized strokes; an SVG <image>
 // scales its own viewport (and its strokes) again when the outer plan zooms.
 window.DrawingPreview={
  markup(doc,editable=false){return `<g class="drawing-art" pointer-events="${editable?'auto':'none'}">${doc.elements.filter(e=>!e.absorbed_by&&!doc.edits[e.id]?.hidden).map(e=>`<g data-plan-kind="${esc(e.kind)}" ${editable?`data-plan-element="${esc(e.id)}"`:''} transform="${trans(doc.edits[e.id])}">${e.svg}</g>`).join('')}${doc.features.map(e=>`<g data-plan-feature="true" ${editable?`data-plan-element="${esc(e.id)}"`:''} data-plan-kind="${esc(e.kind)}">${feature(e)}</g>`).join('')}</g>`},
  finish(root){root.querySelectorAll('[data-plan-kind="wall"]:not([data-plan-feature])').forEach(solidWall)}
 };
 function snapshot(){return {edits:clone(d.edits),features:clone(d.features),site:clone(d.site)}}
 function record(){d.undo.push(snapshot());if(d.undo.length>60)d.undo.shift();d.redo=[]}
 function changed(){d.dirty=true;$('#drawing-status').textContent='Unsaved corrections';$('#drawing-save').disabled=false}
 function trans(v={}){return `translate(${v.dx||0} ${v.dy||0}) translate(${v.cx||0} ${v.cy||0}) rotate(${v.rotation||0}) scale(${v.sx||1} ${v.sy||1}) translate(${-v.cx||0} ${-v.cy||0})`}
 function feature(v){if(v.kind==='floor_opening')return '';const [[x,y],[xx,yy]]=v.points,len=Math.hypot(xx-x,yy-y),a=Math.atan2(yy-y,xx-x)*180/Math.PI,t=v.thickness/2,s=v.flip?-1:1;let path=v.kind==='wall'?`M0 ${-t} H${len} V${t} H0 Z`:v.kind==='door'?`M0 0 V${s*len} M${len} 0 A${len} ${len} 0 0 ${s>0?1:0} 0 ${s*len}`:v.kind==='sliding_door'?`M0 ${-t} H${len*.58} M${len*.42} ${t} H${len} M0 0 H${len}`:v.kind==='line'?`M0 0 H${len}`:`M0 ${-t} H${len} M0 ${t} H${len}`+(v.kind==='window'?` M0 0 H${len} M0 ${-t} V${t} M${len} ${-t} V${t}`:'');return `<g transform="translate(${x} ${y}) rotate(${a})"><path class="${v.kind==='door'?'opening':v.kind==='wall'?'wall wall-solid':v.kind}" d="${path}"/></g>`}
 function libraryMarkup(){
  return P().rooms.filter(r=>r.plan_id===d.plan.id).flatMap(r=>r.block_layout?.items||[]).map(v=>`<g class="drawing-library-furniture" pointer-events="none" transform="translate(${v.x*d.width} ${v.y*d.height}) rotate(${v.angle}) translate(${-v.width*d.width/2} ${-v.depth*d.height/2}) scale(${v.width*d.width/100} ${v.depth*d.height/100})"><title>${esc(v.label)} · edit in Furniture library</title>${FurnitureLibrary.symbol(v)}</g>`).join('');
 }
 async function replaceTracedFurniture(){
  if(d.dirty)return toast('Save your current drawing corrections first.');
  const probes=[];
  for(const item of d.elements){
   if(item.kind!=='furniture'||d.edits[item.id]?.hidden)continue;
   const el=document.querySelector(`[data-element="${item.id}"]`);if(!el)continue;
   const box=el.getBBox(),m=el.transform.baseVal.consolidate()?.matrix;
   const pts=[[box.x,box.y],[box.x+box.width,box.y],[box.x+box.width,box.y+box.height],[box.x,box.y+box.height]].map(([x,y])=>m?new DOMPoint(x,y).matrixTransform(m):{x,y});
   const xs=pts.map(p=>p.x),ys=pts.map(p=>p.y),xml=new DOMParser().parseFromString('<svg xmlns="http://www.w3.org/2000/svg">'+item.svg+'</svg>','image/svg+xml');
   probes.push({id:item.id,kind:item.kind,box:[Math.min(...xs),Math.min(...ys),Math.max(...xs)-Math.min(...xs),Math.max(...ys)-Math.min(...ys)],closed:!!xml.querySelector('rect,circle,ellipse,polygon'),atomic:xml.documentElement.firstElementChild?.tagName==='g',rounded:Number(xml.querySelector('rect')?.getAttribute('rx'))>.6});
  }
  const rs=P().rooms.filter(r=>r.plan_id===d.plan.id),result=TracedFurniture.convert(probes,rs,d.plan);
  if(!result.hide_ids.length)return toast('No recognised furniture traces remain in mapped sections.');
  if(!validateRequired())return;readSite();
  $('#drawing-status').textContent='Replacing furniture across the full plan…';
  const groups=new Map();for(const row of result.replacements){if(!groups.has(row.room_id))groups.set(row.room_id,[]);groups.get(row.room_id).push(row.item)}
  try{
   for(const [rid,items] of groups){const r=P().rooms.find(r=>r.id===rid);await api(`/api/projects/${d.project}/rooms/${rid}/blocks`,{action:'save',revision:r.revision,items,reviewed:false});await refresh(false)}
   const next=snapshot();result.hide_ids.forEach(id=>next.edits[id]={...next.edits[id],hidden:true});
   await api(`/api/projects/${d.project}/plans/${d.plan.id}/drawing`,{revision:d.revision,map_revision:d.map_revision,...next});
   const context={planId:d.plan.id,roomId:d.room?.id,full:true};await refresh(true);await openDrawingEditor(context);d.original=false;$('#drawing-original').checked=false;draw();
   $('#drawing-status').textContent=`${result.replacements.length} library shapes added across ${groups.size} sections. Existing layouts preserved.`+(result.unassigned.length?` ${result.unassigned.length} unmapped objects still need a section.`:'');
   toast('Furniture replaced across the plan. Library shapes remain editable; review suggested types.');
  }catch(err){$('#drawing-status').textContent='Replacement paused: '+err.message;toast(err.message)}
 }
 function markup(){return d.elements.filter(e=>!e.absorbed_by&&!d.edits[e.id]?.hidden).map(e=>`<g class="drawing-element" data-element="${e.id}" transform="${trans(d.edits[e.id])}">${e.svg}</g>`).join('')+d.features.map(e=>`<g class="drawing-element" data-element="${e.id}">${feature(e)}</g>`).join('')}
 function fit(section=true){const b=section&&d.room?.bbox;d.view=b?[Math.max(0,b[0]*d.width-d.width*.025),Math.max(0,b[1]*d.height-d.height*.025),Math.min(d.width,b[2]*d.width+d.width*.05),Math.min(d.height,b[3]*d.height+d.height*.05)]:[0,0,d.width,d.height]}
 function compass(site,solar){const n=site.north_angle||0;return `<svg class="site-compass" viewBox="0 0 140 140" role="img" aria-label="${site.north_confirmed?'Plan compass, north '+n+' degrees clockwise from up':'Compass preview; north is not set'}"><circle cx="70" cy="70" r="47" fill="none" stroke="#deddd0"/>${['N','E','S','W'].map((l,i)=>{let a=(n+i*90)*Math.PI/180;return `<text x="${70+59*Math.sin(a)}" y="${74-59*Math.cos(a)}" text-anchor="middle" fill="${l==='N'?'#b87c00':'#5f6d59'}">${l}${!site.north_confirmed?'?':''}</text>`}).join('')}<g transform="rotate(${n} 70 70)"><path d="M70 30 L65 75 L70 69 L75 75 Z" fill="#b7871f"/><path d="M70 76 V103" stroke="#84927b"/></g>${solar&&site.north_confirmed?`<g transform="rotate(${solar.plan_angle} 70 70)"><circle cx="70" cy="25" r="5" fill="#e7b52c"/><path d="M70 33 V49" stroke="#d4a326" stroke-dasharray="3 2"/></g>`:''}<circle cx="70" cy="70" r="3" fill="#475b46"/></svg>`}
 window.planCompassMarkup=function(plan){const site=plan?.drawing?.site;if(!site)return '<span class="help">North not set</span>';return `<span class="mini-compass">${compass(site,null)}<span>${site.north_confirmed?'North set':'North not set'}${site.sun_enabled?'<br>'+esc(site.date+' · '+site.time):''}</span></span>`};
 function draw(){const svg=$('#drawing-svg');if(!svg)return;svg.setAttribute('viewBox',d.view.join(' '));svg.innerHTML=`<rect class="drawing-paper" x="0" y="0" width="${d.width}" height="${d.height}" fill="white"/>${d.original||!d.elements.length?`<image href="${url(d.plan.id)}" width="${d.width}" height="${d.height}" opacity="${d.original?.45:1}"/>`:''}<g class="drawing-art">${markup()}</g>${libraryMarkup()}${(d.nativePreview||[]).map(id=>{const r=d.elements.find(v=>v.id===id)?.native_rectangle;return r?`<rect x="${r[0]}" y="${r[1]}" width="${r[2]}" height="${r[3]}" fill="#edbe3344" stroke="#bc8700" stroke-width="2" pointer-events="none"/>`:""}).join("")}<g id="drawing-handles"></g>`;hitAreas();selection();$('#drawing-hint').textContent=d.tool==='split-wall'?'Click where you want to split the wall.':d.tool==='insert-window'?'Click the two ends of the window on the selected wall. The remaining wall is kept on both sides.':d.tool==='select'?'':d.tool==='pan'?'':`Click two points for the ${d.tool}. ${d.tool==='door'?'First point is the hinge; second is the closed leaf end.':''} Escape cancels.`;document.querySelectorAll('[data-drawing-tool]').forEach(b=>{b.classList.toggle('selected',b.dataset.drawingTool===d.tool);b.setAttribute('aria-pressed',String(b.dataset.drawingTool===d.tool))});if(d.first){const c=document.createElementNS('http://www.w3.org/2000/svg','circle');c.setAttribute('cx',d.first[0]);c.setAttribute('cy',d.first[1]);c.setAttribute('r',d.view[2]/150);c.setAttribute('fill','#d9a722');svg.append(c)}}
 function selectedGeometry(){try{return d.features.find(f=>f.id===d.selected)||editableWall()}catch{return null}}
 function nativeReview(){
  const host=$('#drawing-native-review');if(!host)return;
  const item=d.elements.find(e=>e.id===d.selected),group=item?.native_fill_group;
  if(!group){host.innerHTML='';return}
  const matches=d.elements.filter(e=>e.native_fill_group===group&&!d.edits[e.id]?.hidden);
  host.innerHTML=`<strong>Native filled shapes · ${matches.length}</strong><p class="help">Matching fill is a selection aid, not wall detection. Check every highlighted shape against the original; openings still require review.</p>${control('Highlight matching fill','preview-native')}${d.nativePreview?.length?control('Classify highlighted shapes as walls','classify-native'):''}${control('Leave selected unclassified','unclassify-native')}`;
 }
 function selection(){
  nativeReview();
  document.querySelectorAll('#drawing-svg [data-element]').forEach(el=>el.classList.toggle('drawing-active',el.dataset.element===d.selected));
  const group=$('#drawing-handles');group.innerHTML='';const el=document.querySelector(`[data-element="${d.selected}"]`);
  if(!el){$('#drawing-shape-label').hidden=true;$('#drawing-selected').textContent='';selectionFields(null);return}
  const f=selectedGeometry(),kind=f?.kind||d.elements.find(x=>x.id===d.selected)?.kind||'detail';
  $('#drawing-selected').textContent=typeName(kind);const badge=$('#drawing-shape-label');badge.textContent=typeName(kind);badge.hidden=false;
  const svg=$('#drawing-svg'),r=7/Math.max(.01,svg.getScreenCTM().a),bb=el.getBoundingClientRect(),inv=svg.getScreenCTM().inverse(),p1=new DOMPoint(bb.left,bb.top).matrixTransform(inv),p2=new DOMPoint(bb.right,bb.bottom).matrixTransform(inv);
  let handles='';
  if(f){handles=f.points.map((p,i)=>`<circle data-draw-handle="${i}" cx="${p[0]}" cy="${p[1]}" r="${r}"/>`).join('');
   if(f.kind==='wall'){const [a,b]=f.points,L=Math.hypot(b[0]-a[0],b[1]-a[1]),x=(a[0]+b[0])/2-(b[1]-a[1])/L*f.thickness/2,y=(a[1]+b[1])/2+(b[0]-a[0])/L*f.thickness/2;
    handles+=`<rect data-draw-handle="thickness" x="${x-r}" y="${y-r}" width="${2*r}" height="${2*r}" class="wall-thickness-handle"><title>Wall thickness</title></rect>`;}
  }else{const raw=el.getBBox(),m=el.transform.baseVal.consolidate()?.matrix,p=m?new DOMPoint(raw.x+raw.width,raw.y+raw.height).matrixTransform(m):{x:raw.x+raw.width,y:raw.y+raw.height};handles=`<circle data-draw-handle="resize" cx="${p.x}" cy="${p.y}" r="${r}"/>`;}
  group.innerHTML=`<rect class="drawing-selection" x="${p1.x}" y="${p1.y}" width="${Math.max(p2.x-p1.x,.2)}" height="${Math.max(p2.y-p1.y,.2)}"/>`+handles;
  const canvas=svg.parentElement.getBoundingClientRect();badge.style.left=Math.max(8,Math.min(bb.left-canvas.left,canvas.width-badge.offsetWidth-8))+'px';badge.style.top=Math.max(8,Math.min(bb.top-canvas.top-30,canvas.height-30))+'px';
  d.selectionBox={x:p1.x,y:p1.y,width:p2.x-p1.x,height:p2.y-p1.y};selectionFields(f);
 }
 function replaceWall(wall,features,selected){
  if(d.features.some(f=>f.id===wall.id))d.features=d.features.filter(f=>f.id!==wall.id);
  else d.edits[wall.id]={...d.edits[wall.id],hidden:true};
  d.features.push(...features);d.selected=selected;
 }
 function point(e,snap=false){const svg=$('#drawing-svg'),p=new DOMPoint(e.clientX,e.clientY).matrixTransform(svg.getScreenCTM().inverse());let out=[Math.max(0,Math.min(d.width,p.x)),Math.max(0,Math.min(d.height,p.y))];if(snap&&d.first&&$('#drawing-snap').checked){if(Math.abs(out[0]-d.first[0])<Math.abs(out[1]-d.first[1]))out[0]=d.first[0];else out[1]=d.first[1]}return out}
 function bind(){const svg=$('#drawing-svg');let drag=null,wheelFrame=null,wheelTarget=null;
  function stopZoom(){if(wheelFrame)cancelAnimationFrame(wheelFrame);wheelFrame=null;wheelTarget=null}
  function splitPoint(e){const wall=editableWall(),p=point(e),cut=DrawingGeometry.project(wall.points,p),scale=svg.getScreenCTM().a;
   if(Math.hypot(cut.point[0]-p[0],cut.point[1]-p[1])*scale>Math.max(12,wall.thickness*scale/2+5))throw Error('Click on the selected wall to split it.');
   return {wall,point:cut.point};
  }
  svg.onpointerdown=e=>{
   if(e.button!==0&&e.button!==1)return;e.preventDefault();stopZoom();svg.focus({preventScroll:true});
   const p=point(e,d.tool!=='insert-window');
   if(e.button===1||d.tool==='pan'){drag={pan:clone(d.view),start:[e.clientX,e.clientY],matrix:svg.getScreenCTM().inverse()};svg.setPointerCapture(e.pointerId);return}
   if(d.tool==='split-wall'){
    try{const {wall,point:cut}=splitPoint(e),parts=DrawingGeometry.split(wall,cut,newId);record();replaceWall(wall,parts,parts[1].id);d.tool='select';changed();draw();toast('Wall split. Each part can be edited separately.')}catch(err){toast(err.message)}return;
   }
   if(d.tool==='insert-window'){
    try{const wall=editableWall(),projected=DrawingGeometry.project(wall.points,p);if(projected.t<0||projected.t>1)return toast('Click within the selected wall.');
     if(!d.first){d.first=projected.point;draw();return}const result=DrawingGeometry.insert(wall,d.first,projected.point,'window',newId);record();replaceWall(wall,result.features,result.openingId);d.first=null;d.tool='select';changed();draw();
    }catch(err){toast(err.message)}return;
   }
   if(d.tool!=='select'){
    if(!d.first){d.first=p;draw();return}if(Math.hypot(p[0]-d.first[0],p[1]-d.first[1])<.2)return;
    record();const f={id:newId(),kind:d.tool,points:[d.first,p],thickness:1.5,flip:false};d.features.push(f);d.selected=f.id;d.first=null;d.tool='select';changed();draw();return;
   }
   const handle=e.target.closest('[data-draw-handle]'),el=e.target.closest('[data-element]');
   if(!handle&&!el){d.selected=null;selection();return}if(el)d.selected=el.dataset.element;selection();
   const element=document.querySelector(`[data-element="${d.selected}"]`),b=element.getBBox();
   drag={client:[e.clientX,e.clientY],matrix:svg.getScreenCTM().inverse(),id:d.selected,handle:handle?.dataset.drawHandle,feature:clone(handle?selectedGeometry():d.features.find(f=>f.id===d.selected)||null),edit:clone(d.edits[d.selected]||{}),localBox:{x:b.x,y:b.y,width:b.width,height:b.height},before:snapshot(),dirty:d.dirty,status:$('#drawing-status').textContent,saveDisabled:$('#drawing-save').disabled,redo:clone(d.redo),moved:false};
   svg.setPointerCapture(e.pointerId);
  };
  svg.onpointermove=e=>{
   if(!drag){if(d.tool==='split-wall'){svg.querySelector('#wall-split-preview')?.remove();try{const {point:p}=splitPoint(e),r=5/svg.getScreenCTM().a;svg.insertAdjacentHTML('beforeend',`<circle id="wall-split-preview" cx="${p[0]}" cy="${p[1]}" r="${r}" fill="#e7af19" stroke="#644b11" style="pointer-events:none"/>`)}catch{}}return}
   const client=drag.pan?drag.start:drag.client,xx=e.clientX-client[0],yy=e.clientY-client[1],m=drag.matrix,delta=[m.a*xx+m.c*yy,m.b*xx+m.d*yy];
   if(drag.pan){d.view=[drag.pan[0]-delta[0],drag.pan[1]-delta[1],...drag.pan.slice(2)];svg.setAttribute('viewBox',d.view.join(' '));selection();return}
   if(!drag.moved&&Math.hypot(xx,yy)<3)return;
   if(!drag.moved){record();drag.moved=true;if(drag.feature&&!d.features.some(f=>f.id===drag.id)){const f={...clone(drag.feature),id:newId()};replaceWall(drag.feature,[f],f.id);drag.id=f.id;drag.feature=f}}
   if(drag.feature){let f=clone(drag.feature);
    if(drag.handle==='thickness'){const [a,b]=f.points,L=Math.hypot(b[0]-a[0],b[1]-a[1]);f.thickness=Math.max(.1,Math.min(50,drag.feature.thickness+2*(-(b[1]-a[1])*delta[0]+(b[0]-a[0])*delta[1])/L))}
    else if(drag.handle!==undefined)f=DrawingGeometry.dragEndpoint(f,Number(drag.handle),delta,d.width,d.height,$('#drawing-snap').checked);
    else {const dx=Math.max(-Math.min(...f.points.map(p=>p[0])),Math.min(d.width-Math.max(...f.points.map(p=>p[0])),delta[0])),dy=Math.max(-Math.min(...f.points.map(p=>p[1])),Math.min(d.height-Math.max(...f.points.map(p=>p[1])),delta[1]));f.points=f.points.map(p=>[p[0]+dx,p[1]+dy])}
    d.features[d.features.findIndex(v=>v.id===drag.id)]=f;
   }else d.edits[drag.id]=drag.handle==='resize'?DrawingGeometry.resizeOutline(drag.edit,drag.localBox,delta):{...drag.edit,dx:(drag.edit.dx||0)+delta[0],dy:(drag.edit.dy||0)+delta[1]};
   changed();draw();
  };
  svg.addEventListener('wheel',e=>{e.preventDefault();if(drag)return;const p=new DOMPoint(e.clientX,e.clientY).matrixTransform(svg.getScreenCTM().inverse());const delta=e.deltaY*(e.deltaMode===1?16:e.deltaMode===2?300:1);wheelTarget=DrawingGeometry.zoom(wheelTarget||d.view,[p.x,p.y],delta,d.width);if(!wheelFrame){const tick=()=>{if(!$('#drawing-svg')||modalType!=='drawing'){stopZoom();return}d.view=d.view.map((v,i)=>v+(wheelTarget[i]-v)*.35);const done=Math.max(...d.view.map((v,i)=>Math.abs(v-wheelTarget[i])))<.001;if(done)d.view=wheelTarget;svg.setAttribute('viewBox',d.view.join(' '));selection();wheelFrame=done?null:requestAnimationFrame(tick);if(done)wheelTarget=null};wheelFrame=requestAnimationFrame(tick)}},{passive:false});
  function finish(e,cancel=false){if(!drag)return;if(cancel&&drag.moved){Object.assign(d,drag.before);d.undo.pop();d.redo=drag.redo;d.dirty=drag.dirty;$('#drawing-status').textContent=drag.status;$('#drawing-save').disabled=drag.saveDisabled;d.selected=drag.feature?.id.startsWith('base')?drag.feature.id:null;draw()}drag=null;if(svg.hasPointerCapture(e.pointerId))svg.releasePointerCapture(e.pointerId)}
  svg.onauxclick=e=>{if(e.button===1)e.preventDefault()};svg.onpointerup=e=>finish(e);svg.onpointercancel=e=>finish(e,true);
 }
 function readSite(){document.querySelectorAll('[data-site]').forEach(el=>{const k=el.dataset.site;d.site[k]=el.type==='checkbox'?el.checked:el.type==='number'?(el.value===''?null:Number(el.value)):el.value});Object.assign(d.site,parseCoordinates($('#site-coordinates').value))}
 async function sun(){
  const captured=d,id=++solarSeq;
  try{readSite();const r=await api(`/api/projects/${d.project}/plans/${d.plan.id}/sun-preview`,{site:d.site});if(d!==captured||id!==solarSeq)return;
   d.solar=r.solar;Object.assign(d.site,{timezone:r.site.timezone,utc_offset:r.site.utc_offset});
   $('#site-compass').innerHTML=compass(d.site,r.solar);
   const offset=r.site.utc_offset,minutes=Math.round(Math.abs(offset)*60);
   $('#site-timezone').textContent=r.site.timezone?`UTC${offset<0?'−':'+'}${String(Math.floor(minutes/60)).padStart(2,'0')}:${String(minutes%60).padStart(2,'0')} · Auto`:'';
   $('#site-timezone').title=r.site.timezone||'';
   $('#sun-results').innerHTML=r.solar?`<div class="sun-presets">${['sunrise','sunset'].map(k=>`<button type="button" class="btn small" data-drawing="${k}" ${r.solar[k]?'':'disabled'}>${k==='sunrise'?'Sunrise':'Sunset'} <strong>${r.solar[k]?.time||'—'}</strong></button>`).join('')}</div>`:'';
  }catch(err){if(d===captured&&id===solarSeq){d.solar=null;$('#site-timezone').textContent='';$('#site-compass').innerHTML=compass(d.site,null);$('#sun-results').textContent=err.message}}
 }
 function siteFields(){const s=d.site;$('#drawing-site').innerHTML=`
  <div class="north-controls"><div id="site-compass">${compass(s,d.solar)}</div><div><label class="drawing-check"><input type="checkbox" data-site="north_confirmed" ${s.north_confirmed?'checked':''}> North set</label><label class="north-angle">Angle <input aria-label="North angle clockwise from page-up" type="number" min="0" max="360" step="1" data-site="north_angle" value="${s.north_angle??0}">°</label></div></div>
  <div class="north-presets">${[0,90,180,270].map((a,i)=>`<button type="button" class="btn small" title="North ${['up','right','down','left'][i]}" data-north="${a}">${['↑','→','↓','←'][i]} N</button>`).join('')}</div>
  <label class="field"><span>Coordinates / Maps link</span><div class="location-entry"><input id="site-coordinates" placeholder="Latitude, longitude or Maps link" value="${s.latitude!=null&&s.longitude!=null?s.latitude+', '+s.longitude:''}"><button type="button" class="btn small" title="Read Google Maps link" aria-label="Read Google Maps link" data-drawing="maps-link">↵</button></div></label><div id="maps-link-status" role="status"></div>
  <label class="drawing-check sunlight-toggle"><input type="checkbox" data-site="sun_enabled" ${s.sun_enabled?'checked':''}> Scene sunlight</label>
  <div class="row-two"><label class="field"><span>Date</span><input type="date" data-site="date" value="${esc(s.date||'')}"></label><label class="field"><span>Time</span><input type="time" data-site="time" value="${esc(s.time||'12:00')}"></label></div>
  <div id="site-timezone" role="status"></div><div id="sun-results" role="status"></div>`;sun()
 }
 const typeName=kind=>({wall:'Wall',window:'Window',door:'Door',sliding_door:'Sliding door',opening:'Opening',furniture:'Furniture',line:'Detail line',detail:'Unclassified'})[kind]||'Unclassified';
 const toolIcons={
  select:'<path d="m5 3 14 10-7 1-3 7z"/>',
  wall:'<path d="M3 5h18v14H3zM3 12h18M9 5v7m7 0v7"/>',
  door:'<path d="M4 20V4h4m0 16V4l10 3v13zM14 12h1"/>',
  window:'<path d="M3 4h18v16H3zM5 6h14v12H5zM12 6v12M5 12h14"/>',
  sliding_door:'<path d="M3 4h18v16H3zM4 6h9v12H4m9-12h7v12h-7M8 10l2 2-2 2m8-4-2 2 2 2"/>',
  line:'<path d="m5 19 14-14"/><circle cx="5" cy="19" r="2"/><circle cx="19" cy="5" r="2"/>',
  'split-wall':'<circle cx="6" cy="6" r="3"/><circle cx="6" cy="18" r="3"/><path d="m8 8 12 12M8 16 20 4"/>',
  pan:'<path d="M7 12V7a1.5 1.5 0 0 1 3 0v5-8a1.5 1.5 0 0 1 3 0v8-6a1.5 1.5 0 0 1 3 0v6-3a1.5 1.5 0 0 1 3 0v6c0 4-2 6-6 6H11c-2 0-3-1-4-3l-3-5c-1-2 1-3 2-2l1 1z"/>',
  undo:'<path d="m8 5-5 5 5 5M3 10h11a6 6 0 0 1 0 12"/>',
  redo:'<path d="m16 5 5 5-5 5m5-5H10a6 6 0 0 0 0 12"/>',
  remove:'<path d="M4 6h16M9 6V3h6v3M6 6l1 15h10l1-15M10 10v7m4-7v7"/>'
 };
 function iconButton(k,label,action=false){return `<button type="button" class="btn drawing-icon" ${action?'data-drawing':'data-drawing-tool'}="${k}" title="${label}" aria-label="${label}" ${action?'':'aria-pressed="false"'}><svg viewBox="0 0 24 24" aria-hidden="true">${toolIcons[k]}</svg></button>`}
 function toolRail(){return `<div class="drawing-tool-rail" role="toolbar" aria-label="Drawing tools" aria-orientation="vertical">${[['select','Select / move'],['wall','Add wall'],['door','Add door'],['window','Add window'],['sliding_door','Add sliding door'],['line','Detail line'],['split-wall','Split wall'],['pan','Pan']].map(([k,v])=>iconButton(k,v)).join('')}<span class="tool-divider"></span>${[['undo','Undo'],['redo','Redo'],['remove','Delete selected']].map(([k,v])=>iconButton(k,v,true)).join('')}</div>`}
 function render(){showModal('Refine drawing · '+esc(d.room?.name||'Floor plan'),`<div id="drawing-validation" role="alert" hidden></div><div class="drawing-mode-tabs"><strong>Walls, doors & windows</strong>${control('Room boundaries & areas','areas')}${control('Furniture library','furniture')}${control('Replace furniture · full plan','replace-furniture')}</div><div class="drawing-layout"><section><div class="drawing-tools">${control('Fit section','fit')}${control('Full plan','full')}${control('＋','zoom-in')}${control('−','zoom-out')}<label><input type="checkbox" id="drawing-original" ${d.original?'checked':''}> Original map</label><label><input type="checkbox" id="drawing-snap" checked> Straight lines</label></div><label class="field"><span>Select drawing element</span><select id="drawing-element-picker"></select></label><div id="drawing-native-review"></div><div class="drawing-workspace">${toolRail()}<div class="drawing-canvas"><div id="drawing-shape-label" class="drawing-shape-label" role="status" hidden></div><svg id="drawing-svg" tabindex="0" role="img" aria-label="Editable walls, doors and windows"></svg></div></div><div class="drawing-tools drawing-selected-tools"><span id="drawing-selected"></span>${control('Insert window in wall','insert-window')}${control('Rotate 15°','rotate')}${control('Flip door swing','flip')}${control('Delete selected','remove')}</div><div id="drawing-size-fields"></div><p id="drawing-hint" class="help"></p></section><aside class="drawing-aside"><h3>Location & light</h3><div id="drawing-site"></div></aside></div>`,`<span id="drawing-status" class="area-status">Saved drawing loaded</span>${control('Cancel','cancel')}<button type="button" id="drawing-save" class="btn primary" data-drawing="save">Save drawing & lighting</button>`,'drawing');$('#modal').classList.add('drawing-dialog');draw();bind();siteFields()}
 window.openDrawingEditor=async function(options={}){const plan=A(options.planId||(tab==='plan'?planId||R()?.plan_id:R()?.plan_id||planId));if(!plan)return toast('Upload and select a floor plan first.');try{const response=await fetch(`/api/projects/${pid}/plans/${plan.id}/drawing`),doc=await response.json();if(!response.ok)throw Error(doc.error);d={...doc,project:pid,plan,room:clone(options.roomId?P().rooms.find(r=>r.id===options.roomId):(R()?.plan_id===plan.id?R():null)),selected:null,tool:'select',first:null,original:true,undo:[],redo:[],dirty:false,site:{...doc.site}};if(d.room?.block_layout?.items?.length&&d.elements.some(e=>e.kind==='furniture'&&d.edits[e.id]?.hidden))d.original=false;fit(!options.full);render()}catch(err){toast(err.message)}};
 document.addEventListener('click',async e=>{if(e.target.closest('[data-action="refine-drawing"]')){openDrawingEditor();return}if(!d||modalType!=='drawing'||!$('#modal').open)return;const t=e.target.closest('[data-drawing-tool]');if(t){if(t.dataset.drawingTool==='split-wall'){try{editableWall()}catch(err){toast(err.message);return}}d.tool=t.dataset.drawingTool;d.first=null;draw();return}const north=e.target.closest('[data-north]');if(north){try{readSite()}catch{}record();d.site.north_angle=Number(north.dataset.north);d.site.north_confirmed=true;changed();siteFields();return}const b=e.target.closest('[data-drawing]');if(!b)return;const a=b.dataset.drawing;
  if(a==='preview-native'){const item=d.elements.find(v=>v.id===d.selected);d.nativePreview=d.elements.filter(v=>item?.native_fill_group&&v.native_fill_group===item.native_fill_group&&!d.edits[v.id]?.hidden).map(v=>v.id);draw();return}
  if(a==='classify-native'||a==='unclassify-native'){const ids=a==='classify-native'?d.nativePreview:[d.selected];if(!ids?.length)return;record();for(const id of ids){const e=d.elements.find(v=>v.id===id);if(e?.native_rectangle)d.edits[id]={...d.edits[id],kind:a==='classify-native'?'wall':'detail'}}d.nativePreview=null;changed();draw();$('#drawing-status').textContent=`${ids.length} native shapes classified. Save to update 3D.`;return}
  if(a==='maps-link'){const input=$('#site-coordinates');b.disabled=true;try{$('#maps-link-status').textContent='Reading Google Maps location…';const result=await api('/api/location-from-map',{url:input.value});input.value=result.latitude+', '+result.longitude;record();Object.assign(d.site,{latitude:result.latitude,longitude:result.longitude});changed();$('#maps-link-status').textContent=result.warning||'Place coordinates found. Save to apply.';sun()}catch(err){$('#maps-link-status').textContent=err.message;toast(err.message)}finally{b.disabled=false}return}
  if(a==='insert-window'){try{editableWall();d.tool='insert-window';d.first=null;draw()}catch(err){toast(err.message)}return}
  if(a==='resize'){try{const f=editableWall(false),out=DrawingGeometry.resize(f,Number($('#drawing-length').value),Number($('#drawing-thickness').value),d.width,d.height);record();const i=d.features.findIndex(v=>v.id===d.selected);if(i>=0)d.features[i]=out;else{d.edits[d.selected]={...d.edits[d.selected],hidden:true};out.id=newId();d.features.push(out);d.selected=out.id}changed();draw()}catch(err){toast(err.message)}return}
  if(a==='cancel'){$('#modal').close();d=null;return}
  if(a==='replace-furniture'){b.disabled=true;try{await replaceTracedFurniture()}finally{b.disabled=false}return}
  if(a==='furniture'){if(d.dirty)return toast('Save drawing changes before opening the furniture library.');if(!d.room)return toast('Select a room section first.');return openFurnitureBlocks(d.project,d.room.id)}
  if(a==='areas'){if(d.dirty)return toast('Save your drawing corrections before opening room boundaries.');openPlanAreas(d.room?.id);return}
  if(a==='fit'){fit();draw()}if(a==='full'){fit(false);draw()}
  if(a==='zoom-in'||a==='zoom-out'){const scale=a==='zoom-in'?.75:1.333;d.view=[d.view[0]+d.view[2]*(1-scale)/2,d.view[1]+d.view[3]*(1-scale)/2,d.view[2]*scale,d.view[3]*scale];draw()}
  if(a==='undo'||a==='redo'){const from=d[a],to=d[a==='undo'?'redo':'undo'];if(from.length){to.push(snapshot());Object.assign(d,from.pop());changed();draw();siteFields()}}
  if(['rotate','flip','remove'].includes(a)&&d.selected){record();const f=d.features.find(f=>f.id===d.selected);if(a==='remove'){if(f)d.features=d.features.filter(v=>v!==f);else d.edits[d.selected]={...d.edits[d.selected],hidden:true};d.selected=null}else if(f){if(a==='flip')f.flip=!f.flip;else{const [p,q]=f.points,ang=Math.PI/12,x=q[0]-p[0],y=q[1]-p[1];f.points[1]=[Math.max(0,Math.min(d.width,p[0]+x*Math.cos(ang)-y*Math.sin(ang))),Math.max(0,Math.min(d.height,p[1]+x*Math.sin(ang)+y*Math.cos(ang)))]}}else{const v=d.edits[d.selected]||{},el=document.querySelector(`[data-element="${d.selected}"]`),box=el.getBBox();d.edits[d.selected]={...v,cx:v.cx??(box.x+box.width/2),cy:v.cy??(box.y+box.height/2),rotation:((v.rotation||0)+(a==='flip'?180:15))%360}}changed();draw()}
  if(a==='sunrise'||a==='sunset'){const event=d.solar?.[a];if(!event)return toast('Enter coordinates and date first. This date may not have that event.');record();d.site.time=event.time;changed();siteFields()}
  if(a==='save'){if(!validateRequired())return;if(d.first)return toast('Finish the current line or press Escape.');b.disabled=true;$('#drawing-status').textContent='Saving corrections…';try{readSite();const context={planId:d.plan.id,roomId:d.room?.id};const res=await api(`/api/projects/${d.project}/plans/${d.plan.id}/drawing`,{revision:d.revision,map_revision:d.map_revision,...snapshot()});await refresh(true);await openDrawingEditor(context);d.dirty=false;$('#drawing-save').disabled=true;$('#drawing-status').textContent=res.map_changed?'Corrections saved · review and confirm the room map':'Drawing and scene lighting saved';toast('Saved in the project’s drawing folder.')}catch(err){$('#drawing-validation').textContent='Not saved: '+err.message;$('#drawing-validation').hidden=false;$('#drawing-status').textContent='Not saved: '+err.message;toast('Not saved: '+err.message);b.disabled=false}}
 });
 document.addEventListener('change',e=>{if(!d||modalType!=='drawing'||!$('#modal').open)return;if(e.target.id==='drawing-element-picker'){d.selected=e.target.value||null;d.tool='select';d.first=null;selection();return}if(e.target.id==='drawing-original'){d.original=e.target.checked;draw()}if(e.target.dataset.site||e.target.id==='site-coordinates'){record();const k=e.target.dataset.site;if(k)d.site[k]=e.target.type==='checkbox'?e.target.checked:e.target.type==='number'?(e.target.value===''?null:Number(e.target.value)):e.target.value;try{readSite()}catch{}changed();clearTimeout(solarTimer);solarTimer=setTimeout(sun,150)}});
 document.addEventListener('input',e=>{if(d&&modalType==='drawing'&&(e.target.dataset.site||e.target.id==='site-coordinates')){changed();clearTimeout(solarTimer);solarTimer=setTimeout(sun,350)}});
 document.addEventListener('keydown',e=>{if(!d||modalType!=='drawing'||!$('#modal').open)return;if(e.key==='Delete'&&!e.isComposing&&!e.target.closest('input,textarea,select,[contenteditable=true]')){e.preventDefault();if(d.selected)document.querySelector('[data-drawing=remove]')?.click();return}if(e.key==='Escape'&&(d.first||d.tool==='split-wall'||d.tool==='insert-window')){e.preventDefault();d.first=null;d.tool='select';draw()}});
})();
