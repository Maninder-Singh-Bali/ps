"use strict";
(function(root){
 function resolve(project,assets,saved={}){
  if(!project)return {planId:null,roomId:null,floor:null,cameraId:null,changed:false};
  const plans=project.floor_plans||[], planId=plans.includes(saved.planId)?saved.planId:plans[0]||null;
  const rooms=(project.rooms||[]).filter(r=>r.plan_id===planId), scope=assets[planId]?.construction_selection;
  const preferredFloor=saved.floor||(scope?.confirmed?scope.floor:null);
  const room=rooms.find(r=>r.id===saved.roomId)||rooms.find(r=>r.floor===preferredFloor)||rooms[0];
  const views=room?.camera_views||{}, cameraId=views[saved.cameraId]?saved.cameraId:Object.keys(views)[0]||null;
  const value={planId,roomId:room?.id||null,floor:room?.floor||null,cameraId};
  return {...value,changed:Object.keys(value).some(k=>saved[k]!=null&&saved[k]!==value[k])};
 }
 const api={resolve};
 if(typeof module!=='undefined')module.exports=api;
 else {
  let owner=null;
  api.cameraId=null;
  const read=id=>{try{return JSON.parse(localStorage.getItem('pixeloid-ui-staging-selection:'+id)||'{}')}catch{return {}}};
  api.restore=()=>{
   if(!P())return;
   const saved=owner===pid?{planId,roomId:rid,floor:R()?.floor,cameraId:api.cameraId}:read(pid);
   const resolved=resolve(P(),state.assets,saved);owner=pid;planId=resolved.planId;rid=resolved.roomId;api.cameraId=resolved.cameraId;
   if(resolved.changed)toast('Saved selection is unavailable. Opened '+(R()?.name||'the available plan')+' and its available camera.');
  };
  api.remember=()=>{
   if(!P()||owner!==pid||!R()||R().plan_id!==planId)return;
   const saved=resolve(P(),state.assets,{planId,roomId:rid,floor:R().floor,cameraId:api.cameraId});api.cameraId=saved.cameraId;
   try{localStorage.setItem('pixeloid-ui-staging-selection:'+pid,JSON.stringify(saved))}catch{}
  };
  api.selectCamera=id=>{api.cameraId=id;api.remember()};
  root.WorkspaceSelection=api;
 }
})(typeof window!=='undefined'?window:this);
