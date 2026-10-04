'use strict';
// Surface assignments extend the existing room and reference records.
(() => {
 let session=null;
 const root=()=>document.querySelector('#surface-panel');
 const draft=()=>session.rows[session.target]||(session.rows[session.target]={image_ids:[],dimension_status:'missing'});
 function capture(){if(!root())return;for(const el of root().querySelectorAll('[data-surface-field]'))draft()[el.dataset.surfaceField]=el.value;}
 function draw(){
  if(!root())return;const v=draft();
  root().innerHTML=`<header><strong>Surfaces</strong><button class="btn small" data-surface="close" aria-label="Close surfaces">×</button></header><label class="field">Surface<select id="surface-target">${['floor','walls','ceiling'].map(t=>`<option ${session.target===t?'selected':''}>${t}</option>`).join('')}</select></label><label class="field">Product link<input data-surface-field="product_url" type="url" value="${esc(v.product_url||'')}" placeholder="https://…"></label><button class="btn small" data-surface="inspect">Read product</button><p role="status" id="surface-status"></p><div id="surface-extracted"></div><label class="field">Finish name<input data-surface-field="name" value="${esc(v.name||'')}"></label><label class="field">Variant<input data-surface-field="variant" value="${esc(v.variant||'')}" placeholder="Unspecified"></label><label class="field">Published size / coverage<input data-surface-field="dimensions" value="${esc(v.dimensions||'')}" placeholder="Missing — enter if known"></label><label class="field">Dimensions<select data-surface-field="dimension_status">${['missing','estimated','extracted','reviewed'].map(t=>`<option ${v.dimension_status===t?'selected':''}>${t}</option>`).join('')}</select></label><div class="surface-images">${(v.image_ids||[]).map(id=>`<label><input type="radio" name="surface-image" value="${id}" ${v.asset_id===id?'checked':''}><img src="${url(id)}" alt="Finish reference"></label>`).join('')}</div><button class="btn small" data-surface="upload">Upload images</button><label class="field">Use saved room image<select id="surface-existing"><option value="">Choose image…</option>${R().references.map(id=>`<option value="${id}">${esc(A(id)?.category||A(id)?.display_name||id)}</option>`).join('')}</select></label><label class="field">Placement / finish notes<textarea data-surface-field="notes">${esc(v.notes||'')}</textarea></label><p class="help">Proposed finish. The selected primary image guides generation; extra photos remain saved for review. Texture scale is not verified.</p><button class="btn primary" data-surface="save">Save finishes</button>`;
 }
 function open(){
  if(!R())return toast('Select a room first.');
  if(FurnitureEditor.pending())return toast('Save object changes before opening Surfaces.');
  const dock=document.querySelector('.block-left-panel');if(!dock)return toast('Open Style and select a mapped room first.');
  session={pid,rid,revision:R().revision,rows:structuredClone(R().surfaces||{}),target:'floor',dirty:false};
  for(const child of dock.children)child.hidden=true;
  const panel=document.createElement('section');panel.id='surface-panel';dock.append(panel);draw();
 }
 async function close(){session=null;root()?.remove();await FurnitureEditor.reload();}
 async function addImage(file){
  const error=validateReferenceFile(file,'reference');if(error)throw Error(error);
  const response=await fetch(`/api/projects/${session.pid}/upload?kind=reference&room_id=${session.rid}`,{method:'POST',headers:{'Content-Type':'application/octet-stream','X-Filename':encodeURIComponent(file.name)},body:file});
  const result=await response.json();if(!response.ok)throw Error(result.error);await refresh(false);session.revision=R().revision;
  const v=draft();v.image_ids.push(result.assets[0].id);v.asset_id ||= result.assets[0].id;session.dirty=true;
 }
 document.addEventListener('input',e=>{if(e.target.closest('#surface-panel')){capture();session.dirty=true}});
 document.addEventListener('change',e=>{
  if(!session)return;
  if(e.target.id==='surface-target'){capture();session.target=e.target.value;draw()}
  if(e.target.name==='surface-image'){draft().asset_id=e.target.value;session.dirty=true}
  if(e.target.id==='surface-existing'&&e.target.value){capture();const v=draft();v.image_ids=[...new Set([...v.image_ids,e.target.value])];v.asset_id ||= e.target.value;session.dirty=true;draw()}
 });
 document.addEventListener('click',async e=>{
  if(e.target.closest('[data-surfaces-open]'))return open();
  const b=e.target.closest('[data-surface]');if(!b||!session)return;capture();b.disabled=true;
  try{
   if(b.dataset.surface==='close'){if(session.dirty&&!confirm('Discard unsaved finish changes?'))return;await close();return}
   if(b.dataset.surface==='save'){await api(`/api/projects/${session.pid}/rooms/${session.rid}/surfaces`,{revision:session.revision,surfaces:session.rows});session.dirty=false;await refresh(false);toast('Finishes saved. Existing images are retained; changed inputs need a new review.');await close();return}
   if(b.dataset.surface==='upload'){const input=document.createElement('input');input.type='file';input.multiple=true;input.accept='image/png,image/jpeg,image/webp';input.onchange=async()=>{try{for(const file of input.files)await addImage(file);draw()}catch(err){toast(err.message)}};input.click();return}
   if(b.dataset.surface==='inspect'){
    const p=await api('/api/products/inspect',{url:draft().product_url});session.product=p;const v=draft();v.name ||= p.title;v.dimensions ||= p.dimensions||'';if(v.dimensions)v.dimension_status='extracted';session.dirty=true;draw();
    document.querySelector('#surface-extracted').innerHTML=`<p>${esc(p.title)}</p>${(p.dimension_notes||[]).map(t=>`<p class="help">${esc(t)}</p>`).join('')}<p class="help">Variant needs your review.</p>${(p.images||[]).map((_,i)=>`<button class="btn small" data-surface="photo" data-photo="${i}"><img width="80" src="/product-photo/${p.id}?image=${i}" alt="Product photo ${i+1}"></button>`).join('')}`;
   }
   if(b.dataset.surface==='photo'){const result=await api(`/api/projects/${session.pid}/rooms/${session.rid}/add-product`,{product_id:session.product.id,image_index:Number(b.dataset.photo)});await refresh(false);session.revision=R().revision;const v=draft();v.image_ids.push(result.assets[0].id);v.asset_id=result.assets[0].id;session.dirty=true;draw()}
  }catch(err){const status=document.querySelector('#surface-status');if(status)status.textContent=err.message+' You can enter the details manually.';else toast(err.message)}finally{b.disabled=false}
 });
 document.addEventListener('click',e=>{if(!session||e.target.closest('#surface-panel'))return;if(e.target.closest('[data-action="tab"],[data-action="room"],[data-workspace-floor],.workspace-modes,[data-furniture-preset],#block-plan,#block-preview')){e.preventDefault();e.stopImmediatePropagation();toast('Save or close Surfaces first.')}},true);
 document.addEventListener('change',e=>{if(session&&['project-select','plan-select','workspace-floor'].includes(e.target.id)){e.stopImmediatePropagation();e.target.value=e.target.id==='project-select'?session.pid:e.target.id==='plan-select'?planId:R().floor;toast('Save or close Surfaces first.')}},true);
 window.addEventListener('beforeunload',e=>{if(session?.dirty){e.preventDefault();e.returnValue=''}});
})();

(() => {
 const legacyImages=renderImages,legacyVideos=renderVideos,chosen={};
 const guideCache=new Map();
 function guideKey(r,v){return JSON.stringify([pid,r.id,r.revision,P().map_revision,v.id,v.revision]);}
 function guideMarkup(r,v,video,approved){const source=video?A(approved.approved_image_id):null,key=guideKey(r,v),cached=guideCache.get(key);return `<figure class="camera-input-preview" data-input-guide="${esc(v.id)}">${source?`<img class="output-media" src="${url(source.id)}" alt="Approved video source"><figcaption>Approved source image · ${imageRevisionCurrent(source,r)&&source.view_revision===v.revision?'current':'outdated — approve a current source before video'}</figcaption>`:video?'<p class="notice">Video needs an explicitly approved, current image from this camera.</p>':cached?`<img class="output-media" src="${cached}" alt="Saved camera geometry guide"><figcaption>Saved camera guide · geometry and product proxies</figcaption>`:`<div class="video-empty"><button class="btn" data-camera-guide="${esc(v.id)}">Preview saved camera guide</button></div>`}</figure>`;}
 document.addEventListener('click',async e=>{const b=e.target.closest('[data-camera-guide]');if(!b)return;const r=R(),v=r?.camera_views?.[b.dataset.cameraGuide],project=pid;if(!v)return;const box=b.closest('[data-input-guide]'),key=guideKey(r,v);b.disabled=true;b.textContent='Preparing guide…';try{const result=await api(`/api/projects/${project}/plans/${r.plan_id}/camera-preview`,{room_id:r.id,revision:r.revision,...v.camera});guideCache.set(key,result.image);if(box.isConnected&&pid===project&&guideKey(R(),v)===key)box.innerHTML=`<img class="output-media" src="${result.image}" alt="Saved camera geometry guide"><figcaption>Saved camera guide · geometry and product proxies</figcaption>`;}catch(err){if(box.isConnected)box.textContent=err.message;}});
 function selector(){return `<label class="field">Room<select id="planner-room">${P().rooms.filter(r=>r.plan_id===planId&&r.bbox&&(!A(planId)?.construction_selection?.confirmed||r.floor===A(planId).construction_selection.floor)).map(r=>`<option value="${r.id}" ${r.id===rid?'selected':''}>${esc(r.name)}</option>`).join('')}</select></label>`}
 function cameraSelector(){const vs=Object.values(R()?.camera_views||{});return vs.length?`<label class="field">Camera<select id="planner-camera">${vs.map(v=>`<option value="${v.id}" ${WorkspaceSelection.cameraId===v.id?'selected':''}>${esc(v.name)}</option>`).join('')}</select></label>`:''}
 function selectedViews(){const vs=Object.values(R()?.camera_views||{});return vs.filter(v=>v.id===WorkspaceSelection.cameraId)}
 function assets(r,view,kind){return r[kind==='image'?'images':'videos'].map(A).filter(a=>a?.view_id===view.id)}
 function card(r,v,kind){
  const list=assets(r,v,kind),key=v.id+kind,a=list.find(a=>a.id===(chosen[key]||r.preferred_images?.[v.id]))||list.at(-1),approved=r.view_approvals?.[v.id]||{};
  const stale=a&&(!imageRevisionCurrent(a,r)||a.view_revision!==v.revision),video=kind==='video';
  return `<article class="output-card">${a?(video?`<video class="output-media" src="${url(a.id)}" controls preload="metadata"></video>`:`<img class="output-media" src="${url(a.id)}" alt="${esc(v.name)} generated image" data-action="view" data-id="${a.id}">`):guideMarkup(r,v,video,approved)}<div class="output-body"><h3>${esc(v.name)}</h3>${badge(stale?'outdated':approved['approved_'+kind+'_id']===a?.id&&a?'approved':a?.status||'not generated')}${video&&a?`<p>${esc(VideoPresets.describe(a))}</p>`:''}${video?VideoPresets.controls('view-'+v.id):'<p class="help">FLUX image · configured worker workflow</p>'}${!P().map_confirmed?'<p class="notice">Review and confirm the room map before generation.</p>':''}${!state.engine?.connected?'<p class="help">Renderer offline. Generation requires the paired PC.</p>':''}${list.length?`<label class="field">Saved versions<select data-planner-version="${key}">${list.map((x,i)=>`<option value="${x.id}" ${a.id===x.id?'selected':''}>${i+1} · ${esc(x.status)}${video?' · '+esc(VideoPresets.describe(x)):''}</option>`).join('')}</select></label>`:''}<div class="actions">${!video?`<button class="btn small" data-planner="camera" data-view="${v.id}">Edit camera</button>`:''}<button class="btn small primary" data-planner="${video?'video':'image'}" data-view="${v.id}" ${video&&!approved.approved_image_id?'disabled':''}>Generate ${video?'clip':'image'}</button>${a&&!video?`<button class="btn small" data-scene="open" data-source="${a.id}">Revise object</button><button class="btn small" data-revision-compare="${a.id}">Compare revision</button><button class="btn small" data-product-review="${a.id}">Measure products</button>`:''}${a?`<button class="btn small" data-action="approve-${kind}" data-room="${r.id}" data-id="${a.id}" ${stale?'disabled':''}>Approve ${kind}</button><button class="btn small" data-action="reject-${kind}" data-room="${r.id}" data-id="${a.id}">Request revision</button><a class="btn small" href="${url(a.id)}" download>Save output</a>`:''}</div>${a?.review_note?`<p>${esc(a.review_note)}</p>`:''}<div data-job-room="${r.id}" data-job-kind="${kind}" data-job-view="${v.id}" data-job-id="${a?.job_id||''}"></div></div></article>`;
 }
 renderImages=function(){
  if(!R())return legacyImages();
  return heading('','Images','Layout and product references guide FLUX; review geometry and product fidelity.',`<button class="btn" data-planner="camera">Add camera view</button>`)+selector()+cameraSelector()+`<div class="cards">${selectedViews().map(v=>card(R(),v,'image')).join('')||'<p>Save a named camera view to begin.</p>'}</div><details class="subsection"><summary>Advanced · image edits and previous outputs</summary><button class="btn small" data-scene="open">Edit a saved image</button>${legacyImages()}</details>`;
 };
 renderVideos=function(){
  if(!R())return legacyVideos();
  return heading('','Video','A short locked-camera clip from one approved image. No multi-view transition is implied.')+selector()+cameraSelector()+`<div class="cards">${selectedViews().map(v=>card(R(),v,'video')).join('')||'<p>Save and approve an image in Images first.</p>'}</div><details class="subsection"><summary>Advanced · previous room clips</summary>${legacyVideos()}</details>`;
 };
 document.addEventListener('change',e=>{if(e.target.id==='planner-room'){rid=e.target.value;renderMain()}if(e.target.id==='planner-camera'){WorkspaceSelection.selectCamera(e.target.value);renderMain()}if(e.target.dataset.plannerVersion){chosen[e.target.dataset.plannerVersion]=e.target.value;renderMain()}});
 document.addEventListener('click',async e=>{
  const b=e.target.closest('[data-planner]');if(!b)return;
  try{if(b.dataset.view)WorkspaceSelection.selectCamera(b.dataset.view);if(b.dataset.planner==='camera'){await openCameraView(pid,rid,{viewId:b.dataset.view});return}
   b.disabled=true;const job=await api(roomUrl(R(),'generate-'+b.dataset.planner),{view_id:b.dataset.view,...(b.dataset.planner==='video'?VideoPresets.read('view-'+b.dataset.view):{})});openGenerationProgress(job);await refresh(false);
  }catch(err){toast(err.message)}finally{b.disabled=false}
 });
})();
