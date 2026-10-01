'use strict';
(() => {
 let context=null,panels=[],drawing=false,dirty=false;
 const types=[['plan','Top-down plan'],['mixed','Mixed sheet'],['perspective_or_photo','Perspective / photograph'],['uncertain','Uncertain']];
 function panel(d){
  if(A(planId)?.plan_source?.vector)return '';
  const s=d.source_review;
  return `<details class="source-panel-review" ${!s||!s.reviewed?'open':''}><summary>Source & plan panels</summary><p class="help">${s?esc(types.find(t=>t[0]===s.kind)?.[1]||s.kind):'Not classified'} · ${s?.reviewed?'reviewed':'estimated'}. Crops select evidence, never walls.</p><label>Source type<select id="source-kind">${types.map(([v,n])=>`<option value="${v}" ${s?.kind===v?'selected':''}>${n}</option>`).join('')}</select></label><p class="help">Drag around each top-down plan on the original. Exclude façades, titles, vegetation and borders.</p><button class="btn small" data-source-panel="draw">Draw plan crop</button><button class="btn small" data-source-panel="remove">Remove last crop</button><button class="btn small" data-source-panel="clear">Clear crops</button><div id="source-panel-count"></div><label class="help"><input id="source-panels-checked" type="checkbox"> I checked the source type and every crop against the original.</label><button class="btn small" data-source-panel="save">Save source review</button><button class="btn small" data-source-panel="undo">Undo crop edit</button></details>`;
 }
 function paint(){
  if(!context)return;const {svg}=context,a=A(planId);svg.querySelector('#source-crops')?.remove();
  svg.insertAdjacentHTML('beforeend',`<g id="source-crops" pointer-events="none">${panels.map((p,i)=>{const [x,y,w,h]=p.bbox;return `<rect x="${x*a.width}" y="${y*a.height}" width="${w*a.width}" height="${h*a.height}" fill="#3064ab" fill-opacity=".04" stroke="#3064ab" stroke-width="2" stroke-dasharray="6 4" vector-effect="non-scaling-stroke"><title>Plan crop ${i+1}</title></rect>`}).join('')}</g>`);
  const count=document.querySelector('#source-panel-count');if(count)count.textContent=`${panels.length} plan crops${dirty?' · unsaved':''}${drawing?' · drag on the original':''}`;
 }
 function attach(svg,d,save){
  context={svg,d,save};panels=structuredClone(d.source_review?.panels||[]);drawing=false;dirty=false;paint();
  svg.addEventListener('pointerdown',e=>{
   if(!drawing)return;e.preventDefault();e.stopImmediatePropagation();const a=A(planId),point=q=>{const p=new DOMPoint(q.clientX,q.clientY).matrixTransform(svg.getScreenCTM().inverse());return [Math.max(0,Math.min(1,p.x/a.width)),Math.max(0,Math.min(1,p.y/a.height))]},start=point(e),draft={bbox:[...start,0,0]};
   panels.push(draft);svg.setPointerCapture(e.pointerId);
   const move=q=>{const end=point(q);draft.bbox=[Math.min(start[0],end[0]),Math.min(start[1],end[1]),Math.abs(end[0]-start[0]),Math.abs(end[1]-start[1])];paint()};
   const finish=q=>{svg.removeEventListener('pointermove',move);svg.removeEventListener('pointerup',finish);svg.removeEventListener('pointercancel',finish);if(q.type==='pointercancel'||Math.min(draft.bbox[2],draft.bbox[3])<.02)panels.pop();else dirty=true;drawing=false;if(svg.hasPointerCapture(q.pointerId))svg.releasePointerCapture(q.pointerId);paint()};
   svg.addEventListener('pointermove',move);svg.addEventListener('pointerup',finish);svg.addEventListener('pointercancel',finish);
  },true);
 }
 document.addEventListener('click',async e=>{
  const b=e.target.closest('[data-source-panel]');if(!b||!context||context.d.plan_id!==planId)return;
  const action=b.dataset.sourcePanel;
  if(action==='draw'){drawing=true;paint();return}
  if(action==='remove'||action==='clear'){if(action==='remove')panels.pop();else panels=[];dirty=true;paint();return}
  b.disabled=true;try{await context.save({source:true,action:action==='undo'?'undo':'save',kind:document.querySelector('#source-kind').value,panels,checked:document.querySelector('#source-panels-checked').checked})}catch(err){toast(err.message)}finally{b.disabled=false}
 });
 window.SourcePanels={panel,attach,pending:()=>context?.d.plan_id===planId&&(dirty||drawing)};
})();
