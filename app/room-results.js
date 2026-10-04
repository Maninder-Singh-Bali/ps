'use strict';

function generatedRoomResults(room,assets,jobs) {
  const ids=new Set([...(room.reference_candidates||[]),...(room.images||[])]);
  return [...ids].map(id=>assets[id]).filter(a=>{
    if(!a||a.room_id!==room.id||a.project_id!==room.project_id&&room.project_id)return false;
    if(a.kind==='reference_candidate')return !a.job_id||jobs[a.job_id]?.status==='completed';
    return a.kind==='image'&&!a.imported&&jobs[a.job_id]?.status==='completed';
  }).sort((a,b)=>b.created-a.created);
}
function roomPreviewResult(room,assets,jobs) {
  const anchor=assets[room.anchor_id];
  return generatedRoomResults(room,assets,jobs).find(a=>
    (a.kind==='image'||a.reference_purpose==='environment')&&a.status!=='rejected'&&
    a.input_revision===room.revision&&a.created>=(anchor?.created||0))||null;
}
if(typeof module!=='undefined')module.exports={generatedRoomResults,roomPreviewResult};

if(typeof document!=='undefined'){
  const previewChoices=new Map();
  function resultsMarkup(r,results){
    return `<summary class="section-line"><h3>Generated references <span class="room-count">${results.length}</span></h3><span class="tag">${results.length?'Newest first':'Create from a prompt'}</span></summary>${results.length?`<div class="cards">${results.map(a=>{
      const roomImage=a.kind==='image',selected=r.anchor_id===a.id||r.references.includes(a.id);
      const name=roomImage?'Room image':a.reference_purpose==='environment'?'Room environment':a.category||'Furniture reference';
      return `<article class="ref-card" data-result-asset="${a.id}"><img class="candidate-image" src="${url(a.id)}" alt="Generated ${esc(name)}" data-action="view" data-id="${a.id}"><div class="ref-body"><div class="ref-meta"><strong>${esc(name)}</strong>${badge(selected?'selected':a.input_revision!==r.revision?'earlier inputs':a.status||'review')}</div><p class="help">${esc(a.reference_prompt||(a.status==='rejected'?'Needs revision · saved image preserved.':'Native 1080 · saved room image · awaiting your review.'))}</p><div class="actions">${roomImage?btn('Review image','review-room-result',`data-id="${a.id}"`,'small dark'):btn(selected?'Selected ✓':a.reference_purpose==='environment'?'Use as room reference':'Use as furniture reference','use-prompt-reference',`data-id="${a.id}" ${selected?'disabled':''}`,'small dark')}${btn('View full size','view',`data-id="${a.id}"`,'small ghost')}${roomImage?'':btn('Discard','discard-prompt-reference',`data-id="${a.id}" ${selected?'disabled':''}`,'small ghost')}</div></div></article>`;
    }).join('')}</div>`:'<p class="help">Generated room images and prompt references appear here automatically. Review each result before using it.</p>'}`;
  }
  window.updateGeneratedReferences=function(){
    if(tab!=='references'||!R())return;
    const drawer=document.querySelector('.generated-reference-drawer');if(!drawer)return;
    const r=R(),results=generatedRoomResults(r,state.assets,state.jobs);
    const signature=JSON.stringify([r.id,r.revision,r.anchor_id,r.references,results.map(a=>[a.id,a.status])]);
    if(drawer.dataset.results===signature)return;
    const newest=results[0]?.id,previous=drawer.dataset.newest,wasOpen=drawer.open;
    drawer.innerHTML=resultsMarkup(r,results);drawer.dataset.results=signature;drawer.dataset.newest=newest||'';
    drawer.open=Boolean(results.length)&&(wasOpen||previous!==newest);
  };
  window.updateRoomPreview=function(){
    if(tab!=='references'||!R())return;
    updateGeneratedReferences();
    const r=R(),result=roomPreviewResult(r,state.assets,state.jobs),preview=document.querySelector('.anchor-preview');
    if(!preview)return;
    let choice=previewChoices.get(r.id);
    if(!choice||choice.latest!==result?.id){choice={latest:result?.id,original:false};previewChoices.set(r.id,choice)}
    const a=result&&!choice.original?result:A(r.anchor_id),layout=preview.closest('.anchor-layout');
    let controls=layout.querySelector('.room-preview-switch');
    if(result&&r.anchor_id&&result.id!==r.anchor_id){
      if(!controls){controls=document.createElement('div');controls.className='room-preview-switch';preview.before(controls)}
      controls.innerHTML=`<button type="button" class="btn small ${choice.original?'':'selected'}" data-room-preview="latest" aria-pressed="${!choice.original}">Latest generated image</button><button type="button" class="btn small ${choice.original?'selected':''}" data-room-preview="original" aria-pressed="${choice.original}">Original reference</button>`;
    }else controls?.remove();
    if(a&&preview.dataset.id!==a.id){
      preview.dataset.id=a.id;preview.dataset.action='view';
      preview.innerHTML=`<img src="${url(a.id)}" alt="${esc(r.name)} ${a.id===result?.id?'latest generated image':'environment reference'}"><span class="drop-label">Drop a room reference here</span>`;
    }
    const caption=layout.querySelector('.anchor-copy p');
    if(caption)caption.textContent=a&&a.id===result?.id?'Latest generated image · click for full-size review.':'Environment reference · click the image for full-size review.';
    const copy=layout.querySelector('.anchor-copy');let note=copy.querySelector('.room-preview-note');
    if(result){if(!note){note=document.createElement('p');note.className='help room-preview-note';copy.append(note)}note.textContent=r.approved_image_id===result.id?'Approved for video. Original reference preserved.':'Awaiting your review. Original reference and video approval are unchanged.'}else note?.remove();
  };
  document.addEventListener('click',e=>{
    const switcher=e.target.closest('[data-room-preview]');
    if(switcher){const choice=previewChoices.get(rid);if(choice){choice.original=switcher.dataset.roomPreview==='original';updateRoomPreview()}return}
    const review=e.target.closest('[data-action="review-room-result"]');
    if(review){versions[rid+'image']=review.dataset.id;tab='images';renderShell();renderMain()}
  });
}
