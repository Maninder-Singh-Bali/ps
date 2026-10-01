'use strict';
// Uses local saved geometry. Never presents an input check as an image QA pass.
document.addEventListener('click',async e=>{
 const button=e.target.closest('[data-action="plan-check"]');if(!button)return;
 const room=R();if(!room)return;
 button.disabled=true;
 try{
  const report=await api(roomUrl(room,'preflight'),{},'GET');
  const rows=report.checks.map(c=>`<li style="margin:.8rem 0"><b>${c.level==='blocked'?'Needs correction':c.level==='warning'?'Check':'Passed'}:</b> ${esc(c.message)}</li>`).join('');
  showModal('Plan check · '+esc(room.name),`<p><strong>${report.can_generate?'Inputs checked · image review still required':'Correct these inputs before generation'}</strong></p><ul>${rows}</ul><p>${esc(report.scope)}</p>`,btn('Close','close-modal','','ghost'),'plan-check');
 }catch(err){toast(err.message)}finally{button.disabled=false}
});
