'use strict';
// Same-origin CSRF wrapper covers existing uploads and specialist API controls.
(()=>{
 const original=window.fetch.bind(window);
 const session=original('/api/access/session').then(r=>r.json());
 window.fetch=async(input,options={})=>{
  const address=new URL(typeof input==='string'?input:input.url,location.href);
  const method=(options.method||input.method||'GET').toUpperCase();
  if(address.origin===location.origin&&!['GET','HEAD','OPTIONS'].includes(method)){
   const s=await session;const headers=new Headers(options.headers||(input instanceof Request?input.headers:undefined));
   if(s.csrf)headers.set('X-Pixeloid-CSRF',s.csrf);options={...options,headers};
  }
  const response=await original(input,options);
  if(address.origin===location.origin&&response.status===401)location.assign('/login');
  return response;
 };
 async function draw(checkPC=false){
  const s=await session;const statusResponse=await fetch('/api/studio/status'+(checkPC?'?check=1':''));const initialStatus=await statusResponse.json();if(!s.enabled&&!initialStatus.remote)return;
  let host=document.querySelector('#studio-status');
  if(!host){host=document.createElement('details');host.id='studio-status';host.innerHTML='<summary>Studio</summary><div><p role="status"></p><button data-studio="check">Check PC</button><button data-studio="prepare">Prepare Studio</button><button data-studio="release">Release models</button><button data-studio="stop">Stop processing services</button><button data-studio="pause">Pause queue</button><button data-studio="resume">Resume queue</button><button data-studio="logout">Sign out</button><small></small></div>';document.querySelector('.top-actions').prepend(host);host.addEventListener('click',async e=>{
   const b=e.target.closest('[data-studio]');if(!b)return;b.disabled=true;
   try{if(b.dataset.studio==='check'){await draw(true);return;}if(b.dataset.studio==='stop'&&!confirm('Stop only Studio-owned processing services? The dashboard stays available. Active work must first be finished or cancelled in Activity.'))return;
    const response=await fetch(b.dataset.studio==='logout'?'/api/access/logout':'/api/studio/'+b.dataset.studio,{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});const data=await response.json();if(!response.ok)throw Error(data.error);if(b.dataset.studio==='logout'){location.assign('/login');return}await draw(initialStatus.remote);
   }catch(err){host.querySelector('p').textContent=err.message}finally{b.disabled=false}
  });}
  try{const d=initialStatus;host.querySelector('summary').textContent=d.remote?'Studio · Local design':'Studio · '+d.state;host.querySelector('p').textContent=d.message+(d.remote&&d.checked?' Last PC check: '+new Date(d.checked*1000).toLocaleString()+' · cached reading.':'');host.querySelector('[data-studio="check"]').hidden=!d.remote;for(const action of ['prepare','release','stop','pause','resume'])host.querySelector('[data-studio="'+action+'"]').hidden=!!d.remote&&(!d.reachable||d.stale);host.querySelector('[data-studio="prepare"]').textContent=d.state==='Error'?'Retry preparation':'Prepare Studio';for(const action of ['release','stop'])host.querySelector('[data-studio="'+action+'"]').disabled=d.ownership!=='dashboard'||d.active_jobs>0;host.querySelector('[data-studio="pause"]').hidden=!d.remote||!d.reachable||d.stale||d.paused;host.querySelector('[data-studio="resume"]').hidden=!d.remote||!d.reachable||d.stale||!d.paused;host.querySelector('[data-studio="logout"]').hidden=!s.enabled;host.querySelector('small').textContent=d.remote?'Editing stays on this Mac. PC checks are manual; accepted jobs reconnect to their saved job ID.':(s.lan_url||'Local access')+' · '+d.ownership+' renderer · HTTP, not encrypted';}
  catch{host.querySelector('summary').textContent='Studio · Offline';host.querySelector('p').textContent='Local dashboard unavailable. Saved projects remain on this Mac.'}
 }
 document.addEventListener('DOMContentLoaded',()=>{draw();setInterval(draw,5000)});
})();
