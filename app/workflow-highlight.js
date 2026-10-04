/* Set the destination tab before content loads; never infer readiness from colour. */
window.setWorkflowHighlight=function(stage){
 const target=stage==='plan'?'architecture':stage;
 document.querySelectorAll('[data-stage],[data-workspace-stage]').forEach(button=>{
  const key=button.dataset.workspaceStage||(button.dataset.stage==='plan'?'architecture':button.dataset.stage);
  if(key===target)button.setAttribute('aria-current','page');else button.removeAttribute('aria-current');
 });
};
if(location.pathname.endsWith('/ps/app/floor-plan.html'))setWorkflowHighlight(new URLSearchParams(location.search).get('stage')==='surfaces'?'surfaces':'architecture');
