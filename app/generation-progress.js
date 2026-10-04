'use strict';

function progressTime(seconds) {
  seconds=Math.max(1,Math.ceil(seconds));
  return seconds>=60?Math.floor(seconds/60)+'m '+seconds%60+'s':seconds+'s';
}
function generationProgressModel(job, asset, nowSeconds = Date.now()/1000) {
  const busy=['queued','waiting','running'].includes(job.status);
  const ready=job.status==='completed'&&(['analysis','plan_setup','vision_study'].includes(job.kind)||Boolean(asset?.url));
  const sampling=job.progress_scope==='sampling';
  const measured=Number.isFinite(job.progress)?job.progress:null;
  const percent=ready?100:measured===null?null:Math.max(0,Math.min(100,measured));
  const elapsed=Math.max(0,Math.round((job.finished||nowSeconds)-(job.created||nowSeconds)));
  const start=job.started||job.submission_intent;
  const renderElapsed=start?Math.max(0,Math.round((job.finished||nowSeconds)-start)):null;
  const steps=job.steps,finishedSteps=sampling&&percent===100;
  let remaining=ready?'Completed':busy?'Remaining time: estimating…':'Remaining time: —';
  if(['queued','waiting'].includes(job.status))remaining='Remaining time: available when rendering starts';
  if(job.status==='completed'&&!ready)remaining='Loading the saved preview…';
  if(busy&&job.status==='running'&&job.eta&&Number.isFinite(job.eta.seconds)&&Number.isFinite(job.eta.at)){
    const left=job.eta.seconds-Math.max(0,nowSeconds-job.eta.at);
    remaining=left>0?'About '+progressTime(left)+(job.eta.scope==='sampling'?' of rendering left · finishing time not yet known':' remaining'):'Remaining time: recalculating…';
  }else if(busy&&finishedSteps)remaining='Remaining time: finishing estimate not yet available';
  const stage=ready&&asset?.status==='rejected'?(job.kind==='video'?'Video needs revision':'Image needs revision'):ready?(job.kind==='video'?'Video ready for review':['analysis','plan_setup','vision_study'].includes(job.kind)?job.stage:'Image ready for review'):job.status==='completed'?'Loading finished image…':job.stage||'Queued';
  const checked=job.consistency_check;
  const verifiedHint=checked?.outside_exact_match?`Protected background: ${checked.outside_pixels.toLocaleString()} pixels checked; no changes outside the edit area. Review the edited object.`:job.kind==='video'&&job.scene_manifest?.approved_image?job.video_preset==='ltx-preview-768x432-2s-v1'?'Approved image downsampled for a 768 × 432 preview; no output upscaling. Review the full clip.':'Exact approved image supplied. Review the full clip for motion and detail changes.':null;
  return {busy,ready,percent,elapsed,renderElapsed,stage,remaining,
    hint:ready?(asset?.status==='rejected'?'Rejected in review. Correct the result before approving video.':verifiedHint||'Saved and ready for review.'):busy?(finishedSteps?'SIMULATED steps complete. Decoding and saving must finish before the image is ready.':sampling?'Bar advances only when the simulator advances a step.':'Waiting for measured progress; the bar will hold.'):job.error||'Generation stopped.',
    percentLabel:ready?'100% · complete':sampling&&percent!==null?(steps?.[1]?`${steps[0]} / ${steps[1]} steps · `:'')+Math.round(percent)+'% simulated':percent!==null?Math.round(percent)+'%':busy?'Waiting for progress':job.status==='completed'?'Loading preview':job.status==='failed'?'Needs attention':'Cancelled'};
}
if(typeof module!=='undefined')module.exports={generationProgressModel,progressTime};

if(typeof document!=='undefined'){
  let monitoredJob=null;
  window.generationProgressMarkup=function(job,asset,compact=false){
    const m=generationProgressModel(job,asset),time=m.elapsed?progressTime(m.elapsed):'0s';
    return `<div class="generation-progress-copy"><strong>${esc(m.stage)}</strong><span>${esc(m.percentLabel)}</span></div><div class="generation-meter ${m.ready?'complete':''} ${job.status==='failed'?'failed':''}" role="progressbar" aria-label="${['analysis','plan_setup','vision_study'].includes(job.kind)?'Floor plan':'SIMULATED steps'}" aria-valuemin="0" aria-valuemax="100" ${m.percent!==null?`aria-valuenow="${Math.round(m.percent)}"`:''} aria-valuetext="${esc(m.stage+' · '+m.percentLabel)}"><b style="width:${m.percent??0}%"></b></div><div class="generation-progress-timing"><strong>${esc(m.remaining)}</strong><span>${m.renderElapsed!==null?`${['analysis','plan_setup','vision_study'].includes(job.kind)?'Reading':job.surface_cleanup?'Cleanup':'Render'} ${progressTime(m.renderElapsed)} · `:''}${time} total elapsed</span></div><div class="generation-progress-meta"><span>${esc(m.hint)}</span>${job.layout_guide_id?`<button type="button" class="btn small ghost" data-action="view" data-id="${esc(job.layout_guide_id)}">View layout guide</button>`:""}</div>${job.error?`<p class="job-error">${esc(job.error)}</p>`:''}`;
  };
  function latestRoomJob(){return Object.values(state?.jobs||{}).filter(j=>j.project_id===pid&&j.room_id===rid&&['reference','image'].includes(j.kind)).sort((a,b)=>b.created-a.created)[0]}
  window.openGenerationProgress=function(job){
    monitoredJob=job.id;
    showModal(job.kind==='video'?'Video generation':job.kind==='reference'?'Reference image generation':'Room image generation',`<p class="generation-room">${esc(P()?.rooms.find(r=>r.id===job.room_id)?.name||'Room')} · ${job.kind==='video'?esc(VideoPresets.describe(job)):'SIMULATED sample'}</p><div id="generation-modal-status" role="status" aria-live="polite"></div><div id="generation-job-actions" class="actions"></div><div id="generation-preview" class="generation-preview"><div class="generation-placeholder"><span class="generation-orbit" aria-hidden="true"></span><strong>${job.kind==='video'?'Your clip':'Your image'} will appear here</strong><p>You can close this window and keep working.</p></div></div>`,btn('Close','close-modal','','ghost'),'generation');
    $('#modal').classList.add('generation-dialog');
    updateGenerationProgress(job);
  };
  window.updateGenerationProgress=function(immediateJob){
    const panel=document.querySelector('.reference-grid > div > .panel'),latest=latestRoomJob();
    if(panel){
      let strip=panel.querySelector('.room-generation-strip');
      if(latest){
        if(!strip){strip=document.createElement('div');strip.className='room-generation-strip';strip.innerHTML='<div class="room-generation-content"></div><button type="button" class="btn small" data-generation="open"></button>';panel.querySelector('.panel-head').after(strip)}
        const asset=A(latest.result_asset_id);strip.querySelector('.room-generation-content').innerHTML=generationProgressMarkup(latest,asset,true);
        const button=strip.querySelector('[data-generation="open"]');button.dataset.job=latest.id;button.textContent=latest.status==='completed'?'View image':'View progress';
      }else strip?.remove();
    }
    if(window.updateRoomPreview)updateRoomPreview();
    if(modalType!=='generation'||!$('#modal').open)return;
    const job=immediateJob?.id===monitoredJob?immediateJob:state?.jobs[monitoredJob];if(!job)return;
    const asset=A(job.result_asset_id),m=generationProgressModel(job,asset);
    const status=$('#generation-modal-status');
    // Elapsed time changes without recreating the preview or resetting image loading.
    status.innerHTML=generationProgressMarkup(job,asset);
    const actions=$('#generation-job-actions'),action=m.busy?'cancel-job':['failed','cancelled','interrupted'].includes(job.status)?'recover-job':null;if(actions&&actions.dataset.state!==String(action)){actions.dataset.state=String(action);actions.innerHTML=action?`<button class="btn small" data-action="${action}" data-id="${esc(job.id)}">${m.busy?'Cancel job':'Recover this job'}</button>`:'';}
    const preview=$('#generation-preview');
    if(m.ready&&preview.dataset.asset!==asset.id){
      preview.dataset.asset=asset.id;
      preview.innerHTML=job.kind==='video'?`<video src="${url(asset.id)}" controls preload="metadata"></video><span>${esc(VideoPresets.describe(asset))} · Review the complete clip</span>`:`<img src="${url(asset.id)}" alt="${esc(job.category||P()?.rooms.find(r=>r.id===job.room_id)?.name||'Generated image')} · generated preview" data-action="view" data-id="${asset.id}"><span>Click image for full-size review</span>`;
    }else if(!m.ready){
      const message=preview.querySelector('strong');
      if(message)message.textContent=job.status==='failed'?'Generation could not finish':job.status==='cancelled'?'Generation cancelled':job.kind==='video'?'Your clip will appear here':'Your image will appear here';
      preview.classList.toggle('generation-stopped',!m.busy&&job.status!=='completed');
    }
  };
  document.addEventListener('click',e=>{const button=e.target.closest('[data-generation="open"]');if(button){const job=state?.jobs[button.dataset.job];if(job)openGenerationProgress(job)}});
}
