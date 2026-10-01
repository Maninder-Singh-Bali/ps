'use strict';
(() => {
 let session=null,viewer=null;
 const button=(name,action)=>`<button class="btn small" data-construct="${action}">${name}</button>`;
 const route=()=>`/api/projects/${pid}/plans/${planId}/construction-selection`;
 const samePage=()=>session?.pid===pid&&session?.aid===planId&&tab==='plan';
 const valid=a=>a?.construction_selection?.confirmed&&a.construction_selection.source_sha256===a.sha256;
 function needed(){const a=A(planId);return tab==='plan'&&!!a&&a.construction_selection_required&&!valid(a)}
 function preserve(){return samePage()&&!!$('#construction-workspace')}
 const pointIn=(p,poly)=>{let yes=false;for(let i=0,j=poly.length-1;i<poly.length;j=i++){const a=poly[i],b=poly[j],cross=(b[0]-a[0])*(p[1]-a[1])-(b[1]-a[1])*(p[0]-a[0]);if(Math.abs(cross)<1e-10&&p[0]>=Math.min(a[0],b[0])-1e-10&&p[0]<=Math.max(a[0],b[0])+1e-10&&p[1]>=Math.min(a[1],b[1])-1e-10&&p[1]<=Math.max(a[1],b[1])+1e-10)return true;if((a[1]>p[1])!==(b[1]>p[1])&&p[0]<(b[0]-a[0])*(p[1]-a[1])/(b[1]-a[1])+a[0])yes=!yes}return yes};
 function includesBlock(v,a,s){
  const t=(v.angle||0)*Math.PI/180,c=Math.cos(t),sn=Math.sin(t),poly=[[-1,-1],[1,-1],[1,1],[-1,1]].map(([x,y])=>[v.x+(x*v.width*a.width*c-y*v.depth*a.height*sn)/2/a.width,v.y+(x*v.width*a.width*sn+y*v.depth*a.height*c)/2/a.height]);
  const inside=p=>s.regions.some(r=>pointIn(p,r))&&!s.exclusions.some(h=>pointIn(p,h));
  // Server also filters complete rotated footprints; use its allowed IDs below.
  return poly.every(inside)&&inside([v.x,v.y]);
 }
 function outlineMarkup(s,a,handles=false){if(!s)return '';return ['regions','exclusions'].map(key=>s[key].map((p,i)=>`<g><polygon points="${p.map(q=>`${q[0]*a.width},${q[1]*a.height}`).join(' ')}" fill="${key==='regions'?'#d6af3526':'#ffffffbb'}" stroke="${key==='regions'?'#a77b13':'#b54f46'}" stroke-width="2" vector-effect="non-scaling-stroke" ${handles?'':'pointer-events="none"'}/>${handles?p.map((q,j)=>`<circle data-vertex="${key}:${i}:${j}" cx="${q[0]*a.width}" cy="${q[1]*a.height}" r="${session.view[2]/180}" fill="${session.selected===key+':'+i+':'+j?'#bc513c':'#fff'}" stroke="#8e6f20" stroke-width="1.5" vector-effect="non-scaling-stroke"/>`).join(''):''}</g>`).join('')).join('')}
 function overlay(svg,a){svg.querySelector('#construction-outline')?.remove();const s=valid(a)?a.construction_selection:null;if(s)svg.insertAdjacentHTML('beforeend',`<g id="construction-outline" pointer-events="none">${outlineMarkup(s,a)}</g>`)}
 function payload(){for(const key of ['name','floor','kind']){const input=$('#construction-'+key);if(input)session.draft[key]=input.value}return {...structuredClone(session.draft),revision:session.data.revision}}
 function record(){session.undo.push(structuredClone(session.draft));session.undo=session.undo.slice(-40)}
 function changed(){session.preview=null;session.dirty=true;$('#construction-confirm').disabled=true;$('#construction-checked').checked=false;$('#construction-status').textContent='Outline changed · preview before confirming';viewer?.update([]);$('#construction-model-note').textContent='Unsaved outline · previous construction remains saved.';paint()}
 function paint(){
  const svg=$('#construction-map'),a=A(planId);if(!svg)return;svg.setAttribute('viewBox',session.view.join(' '));
  svg.innerHTML=`<image href="${url(planId)}" width="${a.width}" height="${a.height}"/>${outlineMarkup(session.draft,a,true)}${session.path.length?`<polyline points="${session.path.map(p=>`${p[0]*a.width},${p[1]*a.height}`).join(' ')}" fill="none" stroke="#8a5f08" stroke-width="2" vector-effect="non-scaling-stroke"/>`:''}${(session.preview?.issues||[]).map(i=>i.polygon?`<polygon points="${i.polygon.map(p=>`${p[0]*a.width},${p[1]*a.height}`).join(' ')}" fill="#d7503033" stroke="#bf432a" vector-effect="non-scaling-stroke"/>`:i.points?`<polyline points="${i.points.map(p=>`${p[0]*a.width},${p[1]*a.height}`).join(' ')}" stroke="#bf432a" stroke-width="4" vector-effect="non-scaling-stroke"/>`:'').join('')}`;
 }
 async function model(){
  if(session.dirty||!valid(A(planId)))return;
  const captured=session,s=A(planId).construction_selection,r=P().rooms.find(r=>r.plan_id===planId&&r.floor===s.floor&&r.bbox);
  const response=await fetch(`/api/projects/${pid}/plans/${planId}/${r?'shared-scene?room_id='+encodeURIComponent(r.id):'raster-draft'}`);const data=await response.json();if(!response.ok)throw Error(data.error);
  if(session!==captured||!preserve()||session.dirty||A(planId).construction_selection?.revision!==s.revision)return;
  const canvas=$('#construction-model');
  if(!viewer||viewer.canvas!==canvas){viewer?.dispose();viewer=new BlockModelViewer.Viewer(canvas,BlockModelViewer.defaults(),()=>{})}
  viewer.update(data.surfaces.map(f=>({points:f.points,color:`rgb(${f.color.join(',')})`,architecture:!['floor','block','furniture'].includes(f.kind),floor:f.kind==='floor',ceiling:f.kind==='ceiling'})));
  $('#construction-model-note').textContent=`Saved draft · ${Number(data.height||0).toFixed(2)} m walls · ${data.lines.length} wall/opening spans · ${data.products.length} fixture/furniture assets${!data.lines.length?' · No classified architecture yet; the outline is not a wall.':''}`;
  $('#construction-model').dataset.segmentCount=String(data.lines.length);session.scene=data;
 }
 async function open(){
  if(window.FurnitureEditor?.pending()||window.CameraEditor?.pending())return toast('Save your current edits before changing the construction area.');
  viewer?.dispose();window.InlinePlan?.reset();
  const project=pid,aid=planId;if(!aid)return toast('Upload a plan first.');
  $('#main').innerHTML='<p role="status">Loading construction selection…</p>';
  const response=await fetch(route());const data=await response.json();if(!response.ok)throw Error(data.error);if(project!==pid||aid!==planId)return;
  const a=A(aid);session={pid:project,aid,data,draft:structuredClone(data.saved||{regions:[],exclusions:[],floor:P().rooms.find(r=>r.plan_id===aid)?.floor||'Selected floor',name:'Selected area',kind:'manual'}),view:[0,0,a.width,a.height],path:[],mode:'edit',dirty:false,preview:null,undo:[]};
  render();await model();
 }
 function render(){
  $('#main').innerHTML=`<section id="construction-workspace" class="panel"><header class="review-top"><h1>Select area to construct</h1><div>${button('Review & edit model','close')}${button('Walls & openings','walls')}${button('Rooms & dimensions','rooms')}</div></header><div class="construction-controls"><label>Name<input id="construction-name" value="${esc(session.draft.name)}"></label><label>Floor<input id="construction-floor" value="${esc(session.draft.floor)}"></label><label>Selection type<select id="construction-kind"><option value="manual">Manual area</option><option value="rooms">Rooms</option><option value="apartment">Apartment</option></select></label><label>Saved boundaries<select id="construction-candidate"><option value="">Choose reviewed room or apartment…</option>${session.data.candidates.map((c,i)=>`<option value="${i}">${esc(c.floor+' · '+c.name)}</option>`).join('')}</select></label>${button('Add boundary','candidate')}</div><div class="construction-controls">${button('Rectangle','rectangle')}${button('Polygon','polygon')}${button('Open-to-sky void','void')}${button('Finish polygon','finish')}${button('Edit corners','edit')}${button('Remove corner','remove-vertex')}${button('Remove outline','remove')}${button('Undo outline','undo')}${button('Fit drawing','fit')}${button('Fit selection','fit-selection')}${button('Restore previous selection','restore')}</div><p class="help">Drag a rectangle, or click polygon corners. Drag corners to adjust; double-click an edge to add a corner. Wheel to zoom; Shift-drag to pan. Only saved room polygons are offered; otherwise select manually.</p><div class="construction-split"><section><h3>Original drawing · selected source outline</h3><svg id="construction-map" role="img" aria-label="Select construction area on original drawing"></svg></section><section><h3>Selected 3D model</h3><canvas id="construction-model" tabindex="0" aria-label="Confirmed selection 3D model"></canvas><p id="construction-model-note" class="help">Confirm the source outline before constructing.</p></section></div><div class="construction-review"><div id="construction-status" role="status">${session.data.saved?'Saved selection loaded':'No area confirmed'}</div><ul id="construction-issues"></ul><label><input type="checkbox" id="construction-checked"> I checked the outline, boundary cuts, balcony ownership and open-to-sky voids against the original.</label><div>${button('Preview selection','preview')}<button id="construction-confirm" class="btn primary" data-construct="confirm" disabled>Confirm & construct selection</button></div></div></section>`;
  $('#construction-kind').value=session.draft.kind;paint();bind();
 }
 function bind(){
  const svg=$('#construction-map'),a=A(planId);
  const pt=e=>{const p=new DOMPoint(e.clientX,e.clientY).matrixTransform(svg.getScreenCTM().inverse());return [Math.max(0,Math.min(1,p.x/a.width)),Math.max(0,Math.min(1,p.y/a.height))]};
  svg.onpointerdown=e=>{
   e.preventDefault();const start=pt(e),vertex=e.target.dataset.vertex;
   if(e.shiftKey){const v=[...session.view],origin=[e.clientX,e.clientY],box=svg.getBoundingClientRect();svg.setPointerCapture(e.pointerId);svg.onpointermove=q=>{session.view=[v[0]-(q.clientX-origin[0])*v[2]/box.width,v[1]-(q.clientY-origin[1])*v[3]/box.height,v[2],v[3]];paint()};svg.onpointerup=svg.onpointercancel=()=>{svg.onpointermove=null};return}
   if(vertex){record();session.selected=vertex;const [key,i,j]=vertex.split(':');svg.setPointerCapture(e.pointerId);svg.onpointermove=q=>{session.draft[key][i][j]=pt(q);changed()};svg.onpointerup=svg.onpointercancel=()=>{svg.onpointermove=null;paint()};paint();return}
   if(['polygon','void'].includes(session.mode)){session.path.push(start);paint();return}
   if(session.mode!=='rectangle')return;
   record();const i=session.draft.regions.length;session.draft.regions.push([start,start,start,start]);svg.setPointerCapture(e.pointerId);
   svg.onpointermove=q=>{const end=pt(q),x=Math.min(start[0],end[0]),y=Math.min(start[1],end[1]),xx=Math.max(start[0],end[0]),yy=Math.max(start[1],end[1]);session.draft.regions[i]=[[x,y],[xx,y],[xx,yy],[x,yy]];changed()};
   svg.onpointerup=svg.onpointercancel=()=>{svg.onpointermove=null;session.mode='edit';paint()};
  };
  svg.ondblclick=e=>{if(session.mode!=='edit'||e.target.dataset.vertex)return;const p=pt(e);let best=null;for(const key of ['regions','exclusions'])session.draft[key].forEach((poly,i)=>poly.forEach((v,j)=>{const q=poly[(j+1)%poly.length],dx=q[0]-v[0],dy=q[1]-v[1],t=Math.max(0,Math.min(1,((p[0]-v[0])*dx+(p[1]-v[1])*dy)/(dx*dx+dy*dy))),dist=Math.hypot(p[0]-v[0]-t*dx,p[1]-v[1]-t*dy);if(!best||dist<best.dist)best={key,i,j,dist}}));if(best&&best.dist<session.view[2]/a.width*.02){record();session.draft[best.key][best.i].splice(best.j+1,0,p);changed()}};
  svg.onwheel=e=>{e.preventDefault();const p=pt(e),f=e.deltaY>0?1.15:1/1.15,v=session.view;session.view=[p[0]*a.width+(v[0]-p[0]*a.width)*f,p[1]*a.height+(v[1]-p[1]*a.height)*f,v[2]*f,v[3]*f];paint()};
  for(const [id,key] of [['name','name'],['floor','floor'],['kind','kind']])$('#construction-'+id).oninput=e=>{record();session.draft[key]=e.target.value;changed()};
 }
 document.addEventListener('click',async e=>{
  if(e.target.closest('[data-action="construction-area"]')){await open().catch(err=>toast(err.message));return}
  const b=e.target.closest('[data-construct]');if(!b||!preserve())return;const action=b.dataset.construct;
  try{
   if(['rectangle','polygon','void','edit'].includes(action)){session.mode=action;session.path=[];$('#construction-status').textContent=action==='rectangle'?'Drag the selected area on the original':action==='edit'?'Drag corners; double-click an edge to add one':'Click corners, then Finish polygon';return}
   if(action==='finish'){if(session.path.length<3)return toast('Choose at least three corners.');record();session.draft[session.mode==='void'?'exclusions':'regions'].push(session.path);session.path=[];session.mode='edit';changed();return}
   if(action==='remove-vertex'){if(!session.selected)return toast('Select a corner first.');const [key,i,j]=session.selected.split(':');if(session.draft[key][i].length<=3)return toast('Keep at least three corners.');record();session.draft[key][i].splice(j,1);session.selected=null;changed();return}
   if(action==='remove'){record();if(session.selected){const [key,i]=session.selected.split(':');session.draft[key].splice(i,1);session.selected=null}else session.draft.regions.pop();changed();return}
   if(action==='undo'){const old=session.undo.pop();if(old){session.draft=old;session.selected=null;changed()}return}
   if(action==='candidate'){const c=session.data.candidates[$('#construction-candidate').value];if(!c)return toast('Choose a reviewed boundary.');if(session.draft.regions.length&&c.floor!==session.draft.floor)return toast('Choose boundaries from the same floor.');record();session.draft.regions.push(...structuredClone(c.regions));session.draft.exclusions.push(...structuredClone(c.exclusions||[]));session.draft.floor=c.floor;$('#construction-floor').value=c.floor;changed();return}
   if(action==='fit'){session.view=[0,0,A(planId).width,A(planId).height];paint();return}
   if(action==='fit-selection'){const p=session.draft.regions.flat();if(!p.length)return;const a=A(planId),xs=p.map(p=>p[0]*a.width),ys=p.map(p=>p[1]*a.height),x=Math.min(...xs),y=Math.min(...ys),w=Math.max(...xs)-x,h=Math.max(...ys)-y,pad=Math.max(w,h)*.06;session.view=[x-pad,y-pad,w+2*pad,h+2*pad];paint();return}
   if(action==='walls'||action==='rooms'){if(session.dirty)return toast('Confirm or undo the changed selection first.');if(action==='walls')await window.openDrawingEditor({planId,full:true});else await window.openPlanAreas();return}
   if(action==='close'){if(session.dirty)return toast('Confirm or undo the changed selection first.');session=null;viewer?.dispose();$('#main').innerHTML='';window.StructureReview.closed=false;renderMain();return}
   b.disabled=true;
   if(action==='preview'){session.preview=await api(route(),{...payload(),action:'preview'});paint();$('#construction-issues').innerHTML=session.preview.issues.map(i=>`<li>${esc((i.label||i.kind)+': '+i.message)}</li>`).join('');$('#construction-status').textContent=`${session.preview.unknown_geometry?'Boundary checks incomplete: unclassified geometry needs original-drawing review. ':''}${session.preview.issues.length} known boundary warnings. ${session.preview.note}`;$('#construction-confirm').disabled=false;return}
   if(action==='confirm'){if(!session.preview)return;await api(route(),{...payload(),preview_key:session.preview.preview_key,checked:$('#construction-checked').checked});}
   if(action==='restore')await api(route(),{revision:session.data.revision,action:'undo'});
   session.dirty=false;await refresh(false);await open();toast('Construction selection saved. Previous geometry and edits retained.');
  }catch(err){toast(err.message)}finally{b.disabled=false}
 });
 document.addEventListener('close',()=>{if(preserve()&&!session.dirty)model().catch(err=>toast(err.message))},true);
 window.ConstructionArea={open,needed,preserve,includesBlock,overlay};
})();
