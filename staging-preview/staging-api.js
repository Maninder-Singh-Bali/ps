'use strict';
// Static preview adapter. No remote application API, credential or worker exists.
(()=>{
 const base=new URL('.',document.currentScript.src),nativeFetch=window.fetch.bind(window),key='pixeloid.synthetic-staging.v1',clone=v=>structuredClone(v);
 const ready=Promise.all(['fixture.json','fixture-scene.json','fixture-footprint.json'].map(n=>nativeFetch(new URL(n,base)).then(r=>{if(!r.ok)throw Error('Synthetic fixture could not load.');return r.json()})));
 const shape=d=>JSON.stringify({features:d.features.map(f=>[f.id,f.kind,f.points,f.thickness,f.height_m,f.host_wall_id,f.offset,f.width,f.sill_m,f.base_m,f.head_m,f.flip,f.hinge_end]),scale:d.calibration?.metres_per_pixel,height:d.wall_height_m,surfaces:d.surface_design});
 let session=null;
 async function load(){const [seed]=await ready;if(session)return clone(session);try{const raw=localStorage.getItem(key);if(raw){const saved=JSON.parse(raw);if(saved.id===seed.id&&Array.isArray(saved.features))return saved}}catch{}return clone(seed)}
 function publish(d){const text=JSON.stringify(d);try{localStorage.setItem(key,text);session=null}catch{session=clone(d);throw Error('Browser storage is unavailable. Edits remain in this tab only; they were not saved persistently.')}window.dispatchEvent(new Event('staging-saved'))}
 async function api(path,body,raw=false){
  const [seed,scene,footprint]=await ready;
  if(raw)throw Error('Uploads are unavailable in the public synthetic preview. No file was sent.');
  if(path===''){const d=await load();return [{id:d.id,name:d.name,revision:d.revision,count:d.features.length}]}
  if(path==='/'+seed.id){
   const current=await load();if(body===undefined)return clone(current);
   if(body.id!==seed.id||body.revision!==current.revision)throw Error('This browser draft changed in another tab. Reopen before saving.');
   if(!Array.isArray(body.features)||body.features.length>1000||!body.features.every(f=>Array.isArray(f.points)&&f.points.length===2&&f.points.flat().every(Number.isFinite)))throw Error('Invalid synthetic geometry.');
   if(JSON.stringify(body).length>1500000)throw Error('This preview is limited to small synthetic drafts.');
   const saved={...clone(body),revision:current.revision+1,updated:new Date().toISOString()};publish(saved);return clone(saved);
  }
  if(path==='/preview'){
   if(shape(body)!==shape(seed))throw Error('Live 3D rebuilding is unavailable in this static preview. Your edits are kept. Reset the demo to inspect the original 3D fixture.');
   return clone(scene);
  }
  if(path==='/resolve'){
   if(shape(body)===shape(seed))return clone(footprint);
   // Editing remains real client geometry. Fill is deliberately a simple
   // browser approximation, not the Python joined-wall polygon resolver.
   const G=window.TraceGeometry,D=window.DrawingGeometry,fs=G.hosted(body.features),opens=fs.filter(f=>['door','window','sliding_door'].includes(f.kind));
   const pieces=fs.filter(f=>f.kind==='wall').flatMap(w=>{let ps=[w];for(const o of opens){if(o.host_wall_id!==w.id)continue;ps=ps.flatMap(p=>D.cutOpening(p,o,()=>w.id)||[p])}return ps});
   return {hash:'browser-approximation',rings:pieces.map(w=>{const [a,b]=w.points,L=Math.hypot(b[0]-a[0],b[1]-a[1]),n=[-(b[1]-a[1])/L*w.thickness/2,(b[0]-a[0])/L*w.thickness/2];return {outer:[a.map((v,i)=>v+n[i]),b.map((v,i)=>v+n[i]),b.map((v,i)=>v-n[i]),a.map((v,i)=>v-n[i])],holes:[]}})};
  }
  throw Error('Unavailable in synthetic staging. No backend request or generation job was submitted.');
 }
 // A deny-by-default network boundary for the reused editor's optional APIs.
 window.fetch=(input,options)=>{const u=new URL(typeof input==='string'||input instanceof URL?input:input.url,location.href);if(u.origin!==location.origin||u.pathname.includes('/api/')||u.pathname.includes('/media/'))return Promise.resolve(new Response(JSON.stringify({error:'Unavailable in staging: no live backend or external product lookup.'}),{status:503,headers:{'Content-Type':'application/json'}}));return nativeFetch(input,options)};
 window.validateReferenceFile=()=> 'Reference uploads are unavailable in this synthetic preview.';
 window.Staging={ready,load,api,shape};
 document.addEventListener('click',e=>{if(e.target.closest('#upload,[data-action="import"],[data-design-action="reference"],[data-design-action="texture"],[data-design-action="product"],[data-design-action="finish-product"]')){e.preventDefault();e.stopImmediatePropagation();alert('Unavailable in the public synthetic preview. No file or URL was sent.')}if(e.target.closest('[data-staging-reset]')){if(confirm('Reset only this browser’s synthetic demo edits?')){localStorage.removeItem(key);session=null;location.reload()}}},true);
 document.addEventListener('DOMContentLoaded',()=>{const b=document.querySelector('#upload');if(b){b.disabled=true;b.title='Uploads unavailable in synthetic staging'}const f=document.querySelector('#file');if(f)f.disabled=true;});
})();
