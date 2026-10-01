(()=>{
 function launchButton(){return '<button type="button" class="btn primary" data-system="start">Start local renderer</button>'}
 async function check(){
  showModal('System check','<p role="status">Checking local components, workflows, model files and saved activities…</p>','','system-check');
  try{
   const report=await api('/api/system-status',{},'GET');if(modalType!=='system-check')return;
   $('#modal-body').innerHTML=`<div class="system-intro"><strong>${report.status==='ready'?'Ready to work locally':'Some components need attention'}</strong><span>Checked ${new Date(report.checked*1000).toLocaleTimeString()}</span></div><p class="help">Your projects and generation run on this PC. Internet is only needed when you choose to discover or import products online.</p><div class="system-checks">${report.checks.map(c=>`<article class="system-row ${c.status}"><span class="system-symbol">${c.status==='ready'?'✓':c.status==='info'?'i':'!'}</span><div><strong>${esc(c.name)}</strong><p>${esc(c.detail)}</p></div><small>${esc(c.status==='ready'?'Ready':c.status==='info'?'Note':'Needs attention')}</small></article>`).join('')}</div><div class="actions">${!report.renderer_connected?launchButton():''}<button class="btn" data-system="check">Check again</button><a class="btn ghost" href="/local-guide.html" target="_blank" rel="noopener">Local setup guide ↗</a></div>`;
  }catch(e){if(modalType==='system-check')$('#modal-body').innerHTML='<p class="notice">'+esc(e.message)+'</p><button class="btn" data-system="check">Try again</button>'}
 }
 document.addEventListener('click',async e=>{const b=e.target.closest('[data-system]');if(!b)return;if(b.dataset.system==='check')return window.LocalSetup?window.LocalSetup.open():check();if(b.dataset.system==='start'){b.disabled=true;try{const r=await api('/api/renderer/start',{});toast(r.message);await check()}catch(err){toast(err.message)}finally{b.disabled=false}}});
})();
