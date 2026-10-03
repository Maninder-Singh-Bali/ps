'use strict';
(()=>{
 const message='Generation paused — current experiment allowance exhausted.';
 const selector='[data-planner="image"],[data-planner="video"],[data-action="generate-image"],[data-action="generate-video"],[data-action="submit-prompt-reference"],[data-scene="generate"],[data-action="recover-job"]';
 const paused=()=>typeof P==='function'&&P()?.generation_phase?.status==='paused';
 function blocked(button){if(button?.dataset.action==='recover-job'){const job=state?.jobs?.[button.dataset.id],phase=state?.projects?.[job?.project_id]?.generation_phase;return ['image','video','reference'].includes(job?.kind)&&phase?.status==='paused'&&!phase.continuing_job_ids?.includes(job.id)}return paused()}
 function apply(){
  const stop=paused(),main=document.querySelector('#main'),existing=document.querySelector('#generation-phase-notice');
  if(stop&&main&&!existing){const note=document.createElement('div');note.id='generation-phase-notice';note.className='generation-phase-notice';note.setAttribute('role','status');note.textContent=message+' '+Object.entries(P().generation_phase.allowances||{}).map(([name,a])=>name.replaceAll('_',' ')+': '+a.used+'/'+a.limit).join(' · ')+'. Viewing and review remain available.';main.prepend(note)}
  if(!stop)existing?.remove();
  const modal=document.querySelector('#modal-body');
  if(stop&&modal?.querySelector(selector)&&!modal.querySelector('.generation-phase-notice')){const note=document.createElement('p');note.className='generation-phase-notice';note.id='generation-phase-modal-notice';note.textContent=message;modal.prepend(note)}
  if(!stop)document.querySelector('#generation-phase-modal-notice')?.remove();
  document.querySelectorAll(selector).forEach(b=>{if(blocked(b)){if(!b.hasAttribute('data-phase-disabled'))b.dataset.phaseDisabled=String(b.disabled);b.disabled=true;b.title=message}else if(b.hasAttribute('data-phase-disabled')){b.disabled=b.dataset.phaseDisabled==='true';delete b.dataset.phaseDisabled;b.removeAttribute('title')}});
 }
 document.addEventListener('click',e=>{const button=e.target.closest(selector);if(button&&blocked(button)){e.preventDefault();e.stopImmediatePropagation();toast(message)}},true);
 new MutationObserver(apply).observe(document.body,{childList:true,subtree:true});apply();
 window.GenerationPhase={message,paused,apply};
})();
