'use strict';
(()=>{
 let session=null;
 const root=()=>document.querySelector('#product-review');
 const obj=()=>session.data.objects.find(o=>o.id===session.object);
 const key=()=> 'pixeloid-product-review-v1:'+session.data.review_key;
 const points=()=>session.marks[session.object]||(session.marks[session.object]=[]);
 const svg=()=>root().querySelector('svg');
 const visibleAnchors=()=>session.data.anchors.filter(a=>session.filter==='selected'?a.id===session.focus:session.filter==='all'||a.label.includes(session.filter));
 function remember(){try{localStorage.setItem(key(),JSON.stringify({marks:session.marks,pairs:session.pairs,tolerance:session.tolerance,notes:session.notes}))}catch(_){root().querySelector('#pr-storage').textContent='Browser storage unavailable. Export review to retain selections.'}}
 function draw(){
  const o=obj(),p=points(),alignment=session.mode==='alignment',plot=svg();
  let box=[0,0,1920,1080];
  if(session.zoom&&!alignment&&o?.outline){const all=o.outline,xs=all.map(p=>p[0]),ys=all.map(p=>p[1]),x=(Math.min(...xs)+Math.max(...xs))/2,y=(Math.min(...ys)+Math.max(...ys))/2,w=Math.max(300,Math.max(...xs)-Math.min(...xs)+160),h=Math.max(250,Math.max(...ys)-Math.min(...ys)+160);box=[x-w/2,y-h/2,w,h]}
  if(alignment&&session.zoom){const a=session.data.anchors.find(a=>a.id===session.focus);if(a)box=[Math.max(0,Math.min(1320,a.point[0]-300)),Math.max(0,Math.min(630,a.point[1]-225)),600,450]}
  plot.setAttribute('viewBox',box.join(' '));
  const r=box[2]/160;
  const poly=(points,cls)=>`<polyline class="${cls}" points="${points.map(p=>p.join(',')).join(' ')}"/>`;
  let marks='';
  if(alignment){
   if(root().querySelector('#pr-show').checked){
   if(session.filter==='all')marks+=session.data.edges.map(p=>poly(p,'expected')).join('');
   marks+=visibleAnchors().map(a=>`<g data-anchor="${a.id}" role="button" aria-label="${esc(a.label)} ${a.id}"><circle class="landmark" cx="${a.point[0]}" cy="${a.point[1]}" r="${r*1.5}"/><text class="landmark-label" x="${a.point[0]+r*2}" y="${a.point[1]}" style="font-size:${r*3}px">${a.id}</text></g>`).join('');}
   session.pairs.forEach(p=>{marks+=poly([p.expected,p.observed],'observed')+`<circle class="picked" cx="${p.observed[0]}" cy="${p.observed[1]}" r="${r}"/><text class="landmark-label" x="${p.observed[0]+r*2}" y="${p.observed[1]-r}" style="font-size:${r*3}px">${p.id} image</text>`});
  }else{
   if(o?.available&&root().querySelector('#pr-show').checked)marks+=poly([...o.outline,o.outline[0]],'expected');
   if(p.length)marks+=poly(p.length===4?[...p,p[0]]:p,'observed');
   p.forEach((q,i)=>{marks+=`<circle class="picked" cx="${q[0]}" cy="${q[1]}" r="${r}"/><text class="landmark-label" x="${q[0]+r*1.5}" y="${q[1]-r}" style="font-size:${r*3}px">${i+1}</text>`});
  }
  root().querySelector('#pr-marks').innerHTML=marks;results();
 }
 function results(){
  const o=obj(),p=points(),n=o?.kind==='artwork'?4:2,alignment=session.mode==='alignment';
  root().querySelector('#pr-object-info').innerHTML=o?`<strong>${esc(o.label)}</strong><p>${o.available?(o.kind==='artwork'?`${o.dimensions.width_m*100} × ${o.dimensions.height_m*100} cm confirmed`:`${o.dimensions.diameter_m*100} cm diameter confirmed`):esc(o.reason)}</p><p class="help">${esc(o.source)}</p><ul class="help">${o.assumptions.map(s=>`<li>${esc(s)}</li>`).join('')}</ul>`:'';
  root().querySelector('#pr-instruction').textContent=alignment?(session.anchor?'Now click the corresponding visible image corner.':'Choose a numbered model corner, then its corresponding image corner. Use at least three spread-out, non-collinear landmarks.'):(o?.kind==='artwork'?`Mark visible poster FACE corners (exclude frame and shadow): 1 top-left, 2 top-right, 3 bottom-right, 4 bottom-left. ${p.length}/4 selected.`:`Mark opposite left/right edges of the visible circular shade rim. ${p.length}/2 selected. Height and drop are not measured.`);
  const a=ProductReviewMath.alignment(session.pairs);
  root().querySelector('#pr-alignment').textContent=a.count?`Camera alignment: ${a.count} manually matched landmarks; RMS ${a.rms_px.toFixed(1)} px, max ${a.max_px.toFixed(1)} px. Model-point span ${a.span_px.map(v=>v.toFixed(0)).join(' × ')} px across a 1920 × 1080 image. ${a.spatially_distributed?'Distributed sample only; not a camera calibration.':'Insufficient spatial coverage; alignment unverified.'}`:'Camera alignment UNVERIFIED. Metric product dimensions INCONCLUSIVE.';
  if(a.count)root().querySelector('#pr-alignment').textContent+=' Camera alignment UNVERIFIED; metric product dimensions INCONCLUSIVE. Three points are a minimum diagnostic, not whole-image certification.';
  root().querySelector('#pr-pairs').innerHTML=session.pairs.length?'<table><thead><tr><th>Corner</th><th>Model → image (native px)</th><th>Residual</th></tr></thead><tbody>'+session.pairs.map(p=>`<tr><td>${esc(p.id)}</td><td>${p.expected.map(v=>v.toFixed(1)).join(', ')} → ${p.observed.map(v=>v.toFixed(1)).join(', ')}</td><td>${Math.hypot(p.expected[0]-p.observed[0],p.expected[1]-p.observed[1]).toFixed(1)} px</td></tr>`).join('')+'</tbody></table>':'No architectural matches recorded.';
  let report='No visible-product measurement yet. The blue outline is intended placement only.';
  if(o?.available&&p.length===n){try{
   const m=ProductReviewMath.measure(o,p),u=ProductReviewMath.uncertainty(o,p,session.tolerance);
   if(o.kind==='artwork')report=`INCONCLUSIVE. Conditional wall-plane size: ${(m.width_m*100).toFixed(1)} × ${(m.height_m*100).toFixed(1)} cm. Width ${m.width_error_percent.toFixed(1)}%, height ${m.height_error_percent.toFixed(1)}% versus confirmed size. Rectified aspect ${m.ratio.toFixed(3)}; expected ${m.target_ratio.toFixed(3)}. Corner offsets (1–4): ${m.corner_errors_px.map(v=>v.toFixed(1)).join(', ')} px; RMS ${m.corner_rms_px.toFixed(1)} px. Opposite plane widths: ${m.widths_m.map(v=>(v*100).toFixed(1)).join(' / ')} cm; heights: ${m.heights_m.map(v=>(v*100).toFixed(1)).join(' / ')} cm.`;
   else report=`INCONCLUSIVE. Conditional rim-plane diameter: ${(m.diameter_m*100).toFixed(1)} cm (${m.diameter_error_percent.toFixed(1)}% versus ${o.dimensions.diameter_m*100} cm). Actual rim elevation, shade height and suspension length are unknown. Apparent width does not establish physical size. This selected chord represents diameter only if the points are opposite rim edges.`;
   if(u)report+=o.kind==='artwork'?` Sampling ±${session.tolerance} px click perturbations gives aspect ${u.low.toFixed(3)}–${u.high.toFixed(3)}.`:` Sampling ±${session.tolerance} px click perturbations gives diameter ${(u.low*100).toFixed(1)}–${(u.high*100).toFixed(1)} cm.`;
   report+=' Camera, depth, plane pose and product identification errors are additional and unbounded. No pass/fail or approval is inferred.';
  }catch(e){report=e.message}}
  root().querySelector('#pr-results').textContent=report;
  root().querySelector('#pr-points').textContent=alignment?session.pairs.map(p=>`Corner ${p.id}: expected (${p.expected.map(v=>v.toFixed(1)).join(', ')}), observed (${p.observed.map(v=>v.toFixed(1)).join(', ')})`).join(' · '):p.map((p,i)=>`${i+1}: (${p[0].toFixed(1)}, ${p[1].toFixed(1)})`).join(' · ');
 }
 function addPoint(p){
  if(!p.every(Number.isFinite)||p[0]<0||p[0]>1920||p[1]<0||p[1]>1080)return toast('Choose a point within the image.');
  if(session.mode==='alignment'){
   const anchor=session.data.anchors.find(a=>a.id===session.anchor);if(!anchor)return toast('Choose the corresponding model landmark first.');
   session.pairs=session.pairs.filter(p=>p.id!==anchor.id);session.pairs.push({id:anchor.id,expected:anchor.point,observed:p});session.anchor=null;
  }else{const o=obj();if(!o?.available)return toast(o?.reason||'Choose a supported object.');if(points().length===(o.kind==='artwork'?4:2))return toast('Undo or clear points before selecting again.');points().push(p)}
  remember();draw();
 }
 async function open(aid){
  const data=await api('/api/assets/'+aid+'/product-review',undefined,'GET');
  session={data,object:data.objects[0]?.id,marks:{},pairs:[],mode:'object',zoom:false,tolerance:2,anchor:null,focus:null,filter:'top',large:false,notes:''};
  try{const saved=JSON.parse(localStorage.getItem(key())||'null');if(saved){session.marks=saved.marks||{};session.pairs=saved.pairs||[];session.tolerance=saved.tolerance||2;session.notes=saved.notes||''}}catch(_){}
  showModal('Product placement review',`<div id="product-review"><p class="help">Review overlay only · ${esc(aid)}. Blue: intended scene. Orange: manually identified visible image. Camera alignment is an assumption to check.</p><div class="product-review-grid"><section><div class="actions"><label>Object <select id="pr-object">${data.objects.map(o=>`<option value="${o.id}">${esc(o.label)}</option>`).join('')}</select></label><button class="btn small" id="pr-mode">Check camera alignment</button><button class="btn small" id="pr-zoom">Focus object</button><label><input id="pr-show" type="checkbox" checked> Expected outline</label></div><div class="product-review-legend"><b>Dashed blue · expected</b><b>Solid orange · visible selection</b></div><svg class="product-review-canvas" viewBox="0 0 1920 1080" role="img" aria-label="Saved image with intended product outline and manual image measurements"><image href="${data.image_url}" width="1920" height="1080"/><g id="pr-marks"></g></svg><p id="pr-instruction" role="status"></p><div class="review-points"><label>X px <input id="pr-x" type="number" min="0" max="1920" step="0.1"></label><label>Y px <input id="pr-y" type="number" min="0" max="1080" step="0.1"></label><button class="btn small" id="pr-add">Add point</button><button class="btn small" id="pr-undo">Undo point</button><button class="btn small" id="pr-clear">Clear selections</button></div><label id="pr-anchor-wrap" hidden>Model corner <select id="pr-anchor"><option value="">Choose corner</option>${data.anchors.map(a=>`<option value="${a.id}">${a.id} · ${esc(a.label)}</option>`).join('')}</select></label><p class="help" id="pr-points"></p><div id="pr-architecture" hidden><label>Show landmarks <select id="pr-filter"><option value="top">Wall tops only</option><option value="base">Wall bases only</option><option value="selected">Selected corner only</option><option value="all">All</option></select></label> <button class="btn small" id="pr-large">Larger architectural view</button><div id="pr-pairs"></div><label>Bounded check notes / exclusions<textarea id="pr-notes" rows="3" placeholder="Record ambiguous or occluded corners; do not guess correspondences.">${esc(session.notes)}</textarea></label><p class="help">Stop if reliable, distributed correspondences cannot be established. Model wall endpoints are centreline projections; visible-face/thickness offsets are unresolved. No fitting, warping or camera changes. Product and furniture edges cannot validate this camera.</p></div></section><aside><div id="pr-object-info"></div><p id="pr-alignment" class="review-results"></p><label>Click uncertainty ± px <input id="pr-tolerance" type="number" min="0.5" max="20" step="0.5" value="${session.tolerance}"></label><p id="pr-results" class="review-results" aria-live="polite"></p><p class="help">${data.calibrated?'Saved floor scale is calibrated.':'Floor scale is estimated; metric placement has additional uncertainty.'} No occlusion or automatic edge recognition is assumed.</p><p id="pr-storage" class="help">Selections are browser-local and tied to this image, scene and dimension evidence. They do not edit your project.</p><button class="btn small" id="pr-export">Export review measurements</button></aside></div></div>`,btn('Close','close-modal'),'product-review');
  document.querySelector('#modal').classList.add('product-review-dialog');
  root().querySelector('#pr-object').onchange=e=>{session.object=e.target.value;session.anchor=null;draw()};
  root().querySelector('#pr-show').onchange=draw;
  root().querySelector('#pr-zoom').onclick=e=>{session.zoom=!session.zoom;e.target.textContent=session.zoom?'Full image':session.mode==='alignment'?'Focus selected corner':'Focus object';draw()};
  root().querySelector('#pr-mode').onclick=e=>{session.mode=session.mode==='object'?'alignment':'object';session.zoom=false;session.anchor=null;e.target.textContent=session.mode==='alignment'?'Measure product':'Check camera alignment';root().querySelector('#pr-anchor-wrap').hidden=session.mode!=='alignment';root().querySelector('#pr-architecture').hidden=session.mode!=='alignment';root().classList.toggle('architecture-large',session.large&&session.mode==='alignment');root().querySelector('#pr-zoom').textContent=session.mode==='alignment'?'Focus selected corner':'Focus object';draw()};
  root().querySelector('#pr-anchor').onchange=e=>{session.anchor=e.target.value;session.focus=e.target.value;draw()};
  root().querySelector('#pr-filter').onchange=e=>{session.filter=e.target.value;draw()};
  root().querySelector('#pr-large').onclick=e=>{session.large=!session.large;root().classList.toggle('architecture-large',session.large);e.target.textContent=session.large?'Compact architectural view':'Larger architectural view';draw()};
  root().querySelector('#pr-notes').oninput=root().querySelector('#pr-notes').onchange=e=>{session.notes=e.target.value;remember()};
  root().querySelector('#pr-add').onclick=()=>{const x=root().querySelector('#pr-x'),y=root().querySelector('#pr-y');if(!x.value||!y.value)return toast('Enter both coordinates.');addPoint([Number(x.value),Number(y.value)])};
  root().querySelector('#pr-undo').onclick=()=>{(session.mode==='alignment'?session.pairs:points()).pop();remember();draw()};
  root().querySelector('#pr-clear').onclick=()=>{if(session.mode==='alignment'){session.pairs=[];session.anchor=null}else session.marks[session.object]=[];remember();draw()};
  root().querySelector('#pr-tolerance').onchange=e=>{const v=Number(e.target.value);if(v<.5||v>20||!Number.isFinite(v)){e.target.value=session.tolerance;return}session.tolerance=v;remember();results()};
  svg().onclick=e=>{const anchor=e.target.closest('[data-anchor]');if(session.mode==='alignment'&&!session.anchor&&anchor){session.anchor=anchor.dataset.anchor;session.focus=session.anchor;root().querySelector('#pr-anchor').value=session.anchor;draw();return}const p=new DOMPoint(e.clientX,e.clientY).matrixTransform(svg().getScreenCTM().inverse());addPoint([p.x,p.y])};
  root().querySelector('#pr-export').onclick=()=>{
   const report=ProductReviewMath.buildReport(data,session);
   const href=URL.createObjectURL(new Blob([JSON.stringify(report,null,2)],{type:'application/json'})),a=document.createElement('a');a.href=href;a.download='product-review-'+data.asset_id+'.json';a.click();setTimeout(()=>URL.revokeObjectURL(href),1000);
  };
  draw();
 }
 document.addEventListener('click',e=>{const b=e.target.closest('[data-product-review]');if(b)open(b.dataset.productReview).catch(e=>toast(e.message))});
 document.querySelector('#modal').addEventListener('close',()=>{document.querySelector('#modal').classList.remove('product-review-dialog');session=null});
})();
