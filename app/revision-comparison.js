'use strict';
(()=>{
 window.openRevisionComparison=async function(id){
  const d=await api('/api/assets/'+id+'/revision-comparison',undefined,'GET');let closeup=!!d.crop;
  const state=d.status==='approved'?'Approved':d.status==='rejected'?'Discarded candidate — preserved in history':d.review_decision==='kept'?'Already kept for review — not approved':'Awaiting review — not approved';
  const version=v=>v?.version?'v'+v.version:v?'saved image':'unavailable';
  const heading=`Parent ${version(d.parent)} → Result ${version(d.result)}`;
  const scene=(v,name)=>v?`<figure><svg data-compare-scene data-full="0 0 ${v.width} ${v.height}" viewBox="0 0 ${v.width} ${v.height}" aria-label="${name}" role="img"><image href="${v.url}" width="${v.width}" height="${v.height}"/>${d.outline?`<polygon class="comparison-mask" hidden points="${d.outline.map(p=>p.join(',')).join(' ')}"/>`:''}</svg><figcaption>${name} · ${version(v)}</figcaption></figure>`:`<figure><p>Parent unavailable: ${esc(d.parent_note)}</p></figure>`;
  const ref=d.reference?`<svg role="img" aria-label="Exact historical conditioning reference" viewBox="${d.reference.crop.join(' ')}"><image href="${d.reference.url}" width="${d.reference.width}" height="${d.reference.height}"/></svg>`:`<p>${esc(d.reference_note)}</p>`;
  showModal('Compare revision',`${d.phase?.status==='paused'?`<p class="generation-phase-notice">${GenerationPhase.message}</p>`:''}<p class="comparison-heading"><strong>${heading}</strong> · ${esc(state)}</p><p class="help">Parent provenance: ${esc(d.parent_note)}. Keeping a candidate does not approve it.</p><div class="actions"><button class="btn small" id="comparison-mode" ${!d.crop?'disabled':''}>${closeup?'Full room':'Close-up'}</button><label><input type="checkbox" id="comparison-mask" ${!d.outline?'disabled':''}> Show saved mask outline</label></div><p class="help">${d.crop?'Matched fixed crops with context: parent and result use identical coordinates and scale.':' '+esc(d.fallback_reason)}</p><div class="revision-comparison matched-comparison"><figure class="comparison-reference">${ref}<figcaption>${d.reference?esc(d.reference.label)+' · ':''}${esc(d.reference_note)}</figcaption></figure>${scene(d.parent,'Parent')}${scene(d.result,'Result')}</div>`,`<button class="btn" data-action="close-modal">Close</button><button class="btn" data-revision-discard="${id}" ${d.status==='rejected'?'disabled':''}>Discard candidate</button><button class="btn primary" data-revision-keep="${id}" ${d.review_decision==='kept'?'disabled':''}>${d.review_decision==='kept'?'Already kept for review':'Keep for review'}</button>`,'revision-compare');
  const body=document.querySelector('#modal-body');
  function draw(){const scenes=[...body.querySelectorAll('[data-compare-scene]')];const sharedWidth=Math.floor(Math.min(...scenes.map(svg=>svg.parentElement.getBoundingClientRect().width)));scenes.forEach(svg=>{const box=closeup?d.crop:svg.dataset.full.split(' ').map(Number);svg.setAttribute('viewBox',box.join(' '));svg.style.aspectRatio=box[2]+'/'+box[3];svg.style.width=sharedWidth+'px'});body.querySelector('#comparison-mode').textContent=closeup?'Full room':'Close-up';}
  body.querySelector('#comparison-mode').onclick=()=>{closeup=!closeup;draw()};
  body.querySelector('#comparison-mask').onchange=e=>body.querySelectorAll('.comparison-mask').forEach(p=>p.toggleAttribute('hidden',!e.target.checked));
  window.addEventListener('resize',draw);document.querySelector('#modal').addEventListener('close',()=>window.removeEventListener('resize',draw),{once:true});
  draw();
 };
})();
