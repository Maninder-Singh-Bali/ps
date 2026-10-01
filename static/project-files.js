'use strict';

function storageLocationField(id,value){return `<label class="field"><span>Save location</span><div class="folder-input"><input id="${id}" aria-label="Save location" value="${esc(value)}" placeholder="C:\\PixeloidProjects" autocomplete="off"><button type="button" class="btn" data-storage="browse" data-target="${id}">Browse…</button></div></label>`}
function storageTree(title='Inside your project folder'){return `<div class="storage-tree"><strong>${esc(title)}</strong><ul><li>Floor_Plans <span>Drawings and original uploads</span></li><li>Rooms / each room <span>Room_References · Furniture_References · Generated_References · Images · Videos</span></li><li>Supporting_Files <span>Workflow files, prompts, history and analysis</span></li><li>Exports <span>Finished deliverables</span></li><li>project.json <span>Room map, reference links and review records</span></li></ul></div>`}
function newProjectDialog(){
  showModal('Start a new project',`<label class="field"><span>Project name</span><input id="new-project-name" placeholder="e.g. Courtyard residence" autofocus></label>${storageLocationField('new-project-parent',state.storage?.default_parent||'')}<p class="help">A separate folder named after your project will be created here. Existing folders will not be overwritten.</p>${storageTree()}`,btn('Cancel','close-modal','','ghost')+btn('Create project','create-project','','primary'),'new-project');
}

let storageTimer=null;
async function readStorage(projectId){const response=await fetch(`/api/projects/${projectId}/storage`);const data=await response.json();if(!response.ok)throw Error(data.error||'Could not read the project location.');return data}
function storageProgress(operation){
  const el=document.querySelector('#storage-progress');if(!el)return;
  el.hidden=!operation;if(!operation)return;
  const determinate=typeof operation.progress==='number';
  el.innerHTML=`<div class="job-top"><strong>${esc(operation.stage)}</strong><span>${determinate?operation.progress+'%':''}</span></div><div class="progress-track ${determinate?'':'indeterminate'}"><b style="width:${determinate?operation.progress:35}%"></b></div>${operation.error?`<p class="job-error">${esc(operation.error)}</p>`:''}`;
}
async function openProjectFiles(){
  if(!P())return toast('Create a project first.');
  const projectId=pid,data=await readStorage(projectId);
  showModal('Project files',`<p class="help">${esc(P().name)}</p><label class="field"><span>Current project folder</span><input readonly value="${esc(data.path)}"></label>${!data.organized?'<p class="help">This project uses its original folder structure. Selecting a new location will organise its files.</p>':''}${storageTree(data.organized?'Inside your project folder':'Folder structure at the new location')}<details class="storage-change"><summary>Change save location</summary>${storageLocationField('project-storage-parent',data.default_parent)}<p class="help">Copies all existing references and supporting files into a new project folder, then saves future files there. The original files remain available. Finish this project’s running activities first.</p><button type="button" class="btn primary" data-storage="copy" data-project="${projectId}">Copy project & use this location</button></details><div id="storage-progress" role="status" hidden></div>${state.storage?.errors?.[projectId]?`<p class="job-error">Project index could not be updated: ${esc(state.storage.errors[projectId])}</p>`:''}`,btn('Done','close-modal','','primary'),'project-files');
  storageProgress(data.operation);
  if(data.operation?.status==='copying')watchStorage(projectId);
}
function watchStorage(projectId){
  clearInterval(storageTimer);
  storageTimer=setInterval(async()=>{
    if(!$('#modal').open||modalType!=='project-files'){clearInterval(storageTimer);return}
    try{const data=await readStorage(projectId);storageProgress(data.operation);if(['completed','failed'].includes(data.operation?.status))clearInterval(storageTimer)}catch{}
  },600);
}
document.addEventListener('click',async e=>{
  const button=e.target.closest('[data-storage]');if(!button||button.disabled)return;
  const action=button.dataset.storage;
  try{
    if(action==='open'){await openProjectFiles();return}
    if(action==='browse'){
      const field=document.getElementById(button.dataset.target);button.disabled=true;button.textContent='Choosing…';
      try{const data=await api('/api/choose-folder',{initial:field.value});if(!data.cancelled&&field.isConnected)field.value=data.path}finally{button.disabled=false;button.textContent='Browse…'}
      return;
    }
    if(action==='copy'){
      button.disabled=true;const projectId=button.dataset.project;
      storageProgress({stage:'Preparing project files',progress:null});watchStorage(projectId);
      try{
        await api(`/api/projects/${projectId}/storage`,{parent:$('#project-storage-parent').value});await refresh();
        if($('#modal').open&&modalType==='project-files'&&pid===projectId)await openProjectFiles();
        toast('Project copied. Future files will use the new folder.');
      }catch(err){storageProgress({stage:'Original location preserved',error:err.message,progress:null});throw err}
      finally{button.disabled=false;clearInterval(storageTimer)}
    }
  }catch(err){toast(err.message)}
});
