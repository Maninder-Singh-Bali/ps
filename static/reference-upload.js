'use strict';

// Read the drag payload synchronously: browsers clear it after the drop event.
function readImageDrop(transfer) {
  let files=Array.from(transfer?.files||[]);
  if(!files.length) files=Array.from(transfer?.items||[]).filter(x=>x.kind==='file').map(x=>x.getAsFile()).filter(Boolean);
  if(files.length) return {files};
  const get=type=>{try{return transfer?.getData(type)||''}catch{return ''}};
  let source='';
  if(get('text/html')&&typeof DOMParser!=='undefined') {
    const doc=new DOMParser().parseFromString(get('text/html'),'text/html');
    const img=doc.querySelector('img');
    const candidates=(img?.getAttribute('srcset')||'').split(',').map(s=>s.trim().split(/\s+/)).filter(x=>/^https?:|^\/\//.test(x[0])).sort((a,b)=>parseFloat(b[1]||'0')-parseFloat(a[1]||'0'));
    source=candidates[0]?.[0]||img?.getAttribute('src')||'';
    if(source&&!/^https?:|^\/\//.test(source))source='';
  }
  if(!source)source=get('text/uri-list').split(/\r?\n/).find(x=>x.trim()&&!x.startsWith('#'))||'';
  if(!source) source=get('text/plain').trim();
  return {files:[],source:source.trim()};
}

function validateReferenceFile(file,kind) {
  if(!file||!file.size) return 'This image is empty. Choose the saved image file.';
  if(file.size>32*1024*1024) return 'Files must be smaller than 32 MB.';
  const extension=String(file.name||'').split('.').pop().toLowerCase();
  if(kind==='plan'&&extension==='dwg')return 'DWG is unsupported by the installed local tools. Choose DXF or PDF.';
  if(kind==='plan'&&extension==='dxf')return '';
  const image=/^image\/(png|jpeg|webp|gif|bmp|avif)$/.test(file.type||'')||['png','jpg','jpeg','webp','gif','bmp','avif'].includes(extension);
  if(!image&&!(kind==='plan'&&(file.type==='application/pdf'||extension==='pdf'))) return 'Choose an image file (PNG, JPG or WEBP)'+(kind==='plan'?' or a floor-plan PDF or DXF.':'.');
  return '';
}

function studioDropSource(source,origin) {
  if(!source) throw Error('No image file was received. Drop a saved image from a folder, or click to browse.');
  const parsed=new URL(source,origin);
  if(parsed.origin===origin&&/^\/media\/[a-zA-Z0-9]+$/.test(parsed.pathname)) return parsed.href;
  if(['http:','https:'].includes(parsed.protocol)&&!parsed.username&&!parsed.password)return parsed.href;
  throw Error('This drop contains an image link, not a file. Save the image to your PC, then drop that file here.');
}

function uploadDestination(spec,projectId,roomId) {
  return Object.freeze({kind:spec.kind,project_id:spec.project_id||projectId,room_id:spec.kind==='plan'?null:(spec.room_id||roomId)});
}

if(typeof module!=='undefined') module.exports={readImageDrop,validateReferenceFile,studioDropSource,uploadDestination};

if(typeof document!=='undefined') {
  const pendingUploads=new Map();
  const lastAdded=new Map();
  const revealedUploads=new Set();

  window.renderUploadPreviews=function() {
    for(const [id,item] of pendingUploads) {
      if(item.spec.project_id!==pid||item.spec.room_id!==rid||tab!=='references')continue;
      if(document.querySelector('[data-upload-preview="'+id+'"]'))continue;
      const container=item.spec.kind==='anchor'?document.querySelector('.anchor-layout'):document.querySelector('.refs');
      if(!container)continue;
      const card=document.createElement('article');card.className='ref-card pending-reference';card.dataset.uploadPreview=id;
      card.innerHTML=`${item.url?`<img src="${item.url}" alt="${esc(item.file.name)} upload preview">`:''}<div class="ref-body"><strong>${esc(item.file.name)}</strong><p class="upload-item-status" role="status">${esc(item.status)}</p><div class="progress-track indeterminate"><b></b></div></div>`;
      const drop=container.querySelector('.dropzone');container.insertBefore(card,drop||null);
    }
    for(const [aid,until] of lastAdded) {
      if(Date.now()>until){lastAdded.delete(aid);revealedUploads.delete(aid);continue}
      const image=document.querySelector('.refs img[data-id="'+aid+'"]');
      const card=image?.closest('.ref-card');if(card){card.classList.add('reference-just-added');if(!revealedUploads.has(aid)){card.scrollIntoView({block:'nearest',inline:'nearest'});revealedUploads.add(aid)}}
    }
    document.querySelectorAll('.dropzone[data-drop="reference"]').forEach(el=>{
      el.setAttribute('role','button');el.tabIndex=0;el.setAttribute('aria-label','Add furniture reference images');
      const hint=el.querySelector('small');if(hint)hint.textContent='Files or web images · click to browse';
    });
  };

  function updatePending(id,status) {
    const item=pendingUploads.get(id);if(item)item.status=status;
    const label=document.querySelector('[data-upload-preview="'+id+'"] .upload-item-status');if(label)label.textContent=status;
  }
  function clearPending(id) {
    const item=pendingUploads.get(id);if(item?.url)URL.revokeObjectURL(item.url);
    pendingUploads.delete(id);document.querySelector('[data-upload-preview="'+id+'"]')?.remove();
  }

  window.uploadFiles=async function(files,spec) {
    let destination=uploadDestination(spec||{},pid,rid);
    files=Array.from(files||[]);
    if(!files.length)return toast('No image file was received. Drop a saved image from a folder, or click to browse.');
    if((!destination.project_id&&destination.kind!=='plan')||(!destination.room_id&&destination.kind!=='plan'))return toast('Choose a project and room before adding references.');
    if(destination.kind==='anchor'&&files.length>1)return toast('Drop one room reference at a time. You can drop multiple furniture images together.');
    if(uploading)return toast('Please wait for the current upload.');
    const valid=[],failures=[];
    for(const file of files){const error=validateReferenceFile(file,destination.kind);if(error)failures.push(file.name+': '+error);else valid.push(file)}
    if(!valid.length)return toast(failures.join(' '));
    uploading=true;let saved=0;
    if(!destination.project_id){try{const project=await api('/api/projects',{name:valid[0].name.replace(/\.[^.]+$/,'')});pid=project.id;destination=uploadDestination({kind:'plan',project_id:pid},pid,null);tab='plan';localStorage.setItem('pixeloid-tab',tab);await refresh(true)}catch(err){uploading=false;return toast(err.message)}}
    const progress=document.createElement('div');progress.className='upload-progress';progress.setAttribute('role','status');document.body.append(progress);
    const pendingIds=valid.map((file,i)=>{const id=Date.now()+'-'+i;pendingUploads.set(id,{file,spec:destination,url:file.type==='application/pdf'?null:URL.createObjectURL(file),status:'Waiting to upload'});return id});
    renderUploadPreviews();
    try {
      for(let i=0;i<valid.length;i++) {
        const file=valid[i],previewId=pendingIds[i];updatePending(previewId,'Uploading…');
        progress.innerHTML=`<strong>Adding ${i+1} of ${valid.length}</strong><p class="help">${esc(file.name)}</p><div class="progress-track"><b style="width:0%"></b></div><span class="help">0%</span>`;
        try {
          const data=await new Promise((resolve,reject)=>{
            const xhr=new XMLHttpRequest();xhr.open('POST',`/api/projects/${destination.project_id}/upload?kind=${encodeURIComponent(destination.kind)}${destination.room_id?'&room_id='+encodeURIComponent(destination.room_id):''}`);
            xhr.timeout=120000;xhr.setRequestHeader('Content-Type','application/octet-stream');xhr.setRequestHeader('X-Filename',encodeURIComponent(file.name));
            xhr.upload.onprogress=e=>{if(e.lengthComputable){const percent=Math.round(100*e.loaded/e.total);progress.querySelector('b').style.width=percent+'%';const label=percent===100?'Saving image…':percent+'%';progress.querySelector('span').textContent=label;updatePending(previewId,label)}};
            xhr.onload=()=>{try{const result=JSON.parse(xhr.responseText);if(xhr.status<200||xhr.status>=300)throw Error(result.error||'The image could not be saved.');if(!result.assets?.length)throw Error('The server did not return a saved image.');resolve(result)}catch(e){reject(e)}};
            xhr.onerror=()=>reject(Error('Upload connection interrupted.'));xhr.ontimeout=()=>reject(Error('Upload timed out. Check your connection to the local studio.'));xhr.onabort=()=>reject(Error('Upload was cancelled.'));xhr.send(file);
          });
          saved++;for(const a of data.assets)lastAdded.set(a.id,Date.now()+15000);
          updatePending(previewId,'Saved · updating preview…');
          if(destination.kind==='plan'){planId=data.assets.find(a=>a.kind==='plan')?.id||data.assets[0].id;tab='plan';localStorage.setItem('pixeloid-tab',tab);window.StructureReview.closed=false;}
          await refresh(true);clearPending(previewId);renderUploadPreviews();
        } catch(e){failures.push(file.name+': '+e.message);clearPending(previewId)}
      }
      // Import already queues preparation and detection once per page.
      const room=state?.projects[destination.project_id]?.rooms.find(r=>r.id===destination.room_id);
      const where=destination.kind==='anchor'?'room image':destination.kind==='plan'?'floor plan':'Furniture & materials';
      toast([saved?`${saved} ${saved===1?'image':'images'} added to ${room?.name?room.name+' · ':''}${where}.`:'No images were added.',...failures].join(' '));
    } finally {uploading=false;progress.remove();pendingIds.forEach(clearPending)}
  };

  window.handleImageDrop=async function(payload,spec) {
    try {
      if(payload.files.length)return await uploadFiles(payload.files,spec);
      const source=studioDropSource(payload.source,location.origin);
      if(new URL(source).origin!==location.origin||!/^\/media\/[a-zA-Z0-9]+$/.test(new URL(source).pathname))return await importRemoteReference(source,spec);
      const res=await fetch(source,{credentials:'same-origin'});if(!res.ok)throw Error('This reference image is no longer available.');
      const blob=await res.blob();if(!blob.type.startsWith('image/'))throw Error('Drop an image, not a page or video link.');
      const aid=new URL(source).pathname.split('/').pop(),asset=A(aid);
      const filename=asset?.display_name||asset?.name||'reference.png';
      await uploadFiles([new File([blob],filename,{type:blob.type})],spec);
    } catch(e){toast(e.message)}
  };

  async function importRemoteReference(source,spec) {
    const destination=uploadDestination(spec,pid,rid);
    if(uploading)return toast('Please wait for the current image import.');
    if(!destination.project_id||(!destination.room_id&&destination.kind!=='plan'))return toast('Choose a project and room first.');
    uploading=true;const id='web-'+Date.now();
    pendingUploads.set(id,{file:{name:'Image from '+new URL(source).hostname},spec:destination,url:null,status:'Downloading and saving image…'});renderUploadPreviews();
    const progress=document.createElement('div');progress.className='upload-progress';progress.setAttribute('role','status');
    progress.innerHTML='<strong>Importing image from website</strong><p class="help">Saving a copy in this room’s project folder…</p><div class="progress-track indeterminate"><b></b></div>';document.body.append(progress);
    try {
      const result=await api(`/api/projects/${destination.project_id}/import-image`,{url:source,kind:destination.kind,room_id:destination.room_id});
      if(!result.assets?.length)throw Error('The website did not return a saved image.');
      for(const a of result.assets)lastAdded.set(a.id,Date.now()+15000);
      updatePending(id,'Saved · updating preview…');await refresh(true);clearPending(id);renderUploadPreviews();
      const room=state?.projects[destination.project_id]?.rooms.find(r=>r.id===destination.room_id);
      toast('Image imported to '+(room?.name?room.name+' · ':'')+(destination.kind==='reference'?'Furniture & materials':destination.kind==='anchor'?'room image':'floor plan')+'.');
    } finally {uploading=false;progress.remove();clearPending(id)}
  }

  window.bindDrops=function() {
    document.querySelectorAll('[data-drop]').forEach(el=>{
      const spec=uploadDestination({kind:el.dataset.drop},pid,rid);
      el.ondragover=e=>{e.preventDefault();e.stopPropagation();if(e.dataTransfer)e.dataTransfer.dropEffect='copy';el.classList.add('drag')};
      el.ondragleave=e=>{if(!el.contains(e.relatedTarget))el.classList.remove('drag')};
      el.ondrop=e=>{e.preventDefault();e.stopPropagation();const payload=readImageDrop(e.dataTransfer);document.querySelectorAll('.drag').forEach(d=>d.classList.remove('drag'));void handleImageDrop(payload,spec)};
    });
    renderUploadPreviews();
  };
  document.addEventListener('keydown',e=>{if(e.target.matches('.dropzone[data-drop]')&&['Enter',' '].includes(e.key)){e.preventDefault();chooseUpload(e.target.dataset.drop)}});
  // Keep a misplaced file drop from navigating away and discarding the project view.
  document.addEventListener('dragover',e=>{if(Array.from(e.dataTransfer?.types||[]).includes('Files'))e.preventDefault()});
  document.addEventListener('drop',e=>{if(Array.from(e.dataTransfer?.types||[]).includes('Files')&&!e.target.closest('[data-drop]')){e.preventDefault();toast('Drop the image on the room preview or the Furniture & materials area.')}});
}
