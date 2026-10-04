'use strict';
// Keep the diagnostic draft optional once a section can supply a shared scene.
function reviewSceneTarget(plan, roomId, diagnostic=false) {
 if(roomId&&!diagnostic)return {endpoint:'shared-scene',query:'?room_id='+encodeURIComponent(roomId)};
 if(plan.raster_geometry||plan.plan_source?.vector||plan.cad_redraw_id)return {endpoint:'raster-draft',query:''};
 return null;
}
if(typeof module!=='undefined')module.exports={reviewSceneTarget};
