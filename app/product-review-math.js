'use strict';
(function(root){
 const distance=(a,b)=>Math.hypot(a[0]-b[0],a[1]-b[1]);
 function plane(h,p){const d=h[2][0]*p[0]+h[2][1]*p[1]+h[2][2];if(!Number.isFinite(d)||Math.abs(d)<1e-9)throw Error('Selection is too close to the plane horizon.');return [(h[0][0]*p[0]+h[0][1]*p[1]+h[0][2])/d,(h[1][0]*p[0]+h[1][1]*p[1]+h[1][2])/d]}
 function shape(points){
  const cross=points.map((p,i)=>{const q=points[(i+1)%4],r=points[(i+2)%4];return(q[0]-p[0])*(r[1]-q[1])-(q[1]-p[1])*(r[0]-q[0])});
  if(cross.some(v=>Math.abs(v)<1)||!(cross.every(v=>v>0)||cross.every(v=>v<0)))throw Error('Choose four distinct corners around the poster, without crossing edges.');
 }
 function measure(object,points){
  const needed=object.kind==='artwork'?4:2;
  if(points.length!==needed)throw Error(`Select ${needed} image points first.`);
  if(points.some(p=>p.length!==2||p.some(v=>!Number.isFinite(v))))throw Error('Invalid image points.');
  const p=points.map(p=>plane(object.image_to_plane,p));
  if(object.kind==='artwork'){
   shape(points);
   const widths=[distance(p[0],p[1]),distance(p[3],p[2])],heights=[distance(p[0],p[3]),distance(p[1],p[2])];
   const width=(widths[0]+widths[1])/2,height=(heights[0]+heights[1])/2;
   if(Math.min(width,height)<1e-5)throw Error('The selected outline is degenerate.');
   const errors=points.map((v,i)=>distance(v,object.outline[i]));
   return {width_m:width,height_m:height,ratio:width/height,target_ratio:object.dimensions.width_m/object.dimensions.height_m,
    width_error_percent:100*(width/object.dimensions.width_m-1),height_error_percent:100*(height/object.dimensions.height_m-1),
    corner_errors_px:errors,corner_rms_px:Math.sqrt(errors.reduce((s,v)=>s+v*v,0)/4),widths_m:widths,heights_m:heights};
  }
  const diameter=distance(p[0],p[1]);if(diameter<1e-5)throw Error('Choose opposite rim edges.');
  return {diameter_m:diameter,diameter_error_percent:100*(diameter/object.dimensions.diameter_m-1)};
 }
 function uncertainty(object,points,pixels){
  // Sensitivity samples at independent square click-error corners, not rigorous bounds.
  let low=Infinity,high=-Infinity;const field=object.kind==='artwork'?'ratio':'diameter_m';
  function visit(index,rows){if(index===points.length){try{const v=measure(object,rows)[field];low=Math.min(low,v);high=Math.max(high,v)}catch(_){}return}
   for(const x of [-pixels,pixels])for(const y of [-pixels,pixels])visit(index+1,[...rows,[points[index][0]+x,points[index][1]+y]])}
  visit(0,[]);return Number.isFinite(low)?{field,low,high}:null;
 }
 function alignment(pairs){
  const errors=pairs.map(p=>distance(p.expected,p.observed));
  let spread=0;
  for(let i=0;i<pairs.length;i++)for(let j=i+1;j<pairs.length;j++)for(let k=j+1;k<pairs.length;k++){
   const [a,b,c]=[pairs[i],pairs[j],pairs[k]].map(p=>p.expected);spread=Math.max(spread,Math.abs((b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0]))/2);
  }
  const xs=pairs.map(p=>p.expected[0]),ys=pairs.map(p=>p.expected[1]);
  return {residuals_px:errors,span_px:pairs.length?[Math.max(...xs)-Math.min(...xs),Math.max(...ys)-Math.min(...ys)]:[0,0],count:pairs.length,rms_px:errors.length?Math.sqrt(errors.reduce((s,v)=>s+v*v,0)/errors.length):null,max_px:errors.length?Math.max(...errors):null,spatially_distributed:pairs.length>=3&&spread>1920*1080*.02};
 }
 function buildReport(data,review){
  const measurements={};
  for(const o of data.objects){const points=review.marks[o.id]||[];try{measurements[o.id]={points,result:measure(o,points),click_sensitivity:uncertainty(o,points,review.tolerance)}}catch(e){measurements[o.id]={points,incomplete:e.message}}}
  return {version:2,image:data.asset_id,image_sha256:data.image_sha256,scene_fingerprint:data.scene_fingerprint,review_key:data.review_key,camera:data.camera,objects:data.objects,
   alignment_pairs:review.pairs,alignment:alignment(review.pairs),alignment_status:'UNVERIFIED',metric_status:'INCONCLUSIVE',architectural_notes:review.notes,
   click_tolerance_px:review.tolerance,uncertainty_method:'Sampled square-corner click perturbations; not confidence intervals or rigorous bounds. Camera, wall thickness, product plane, depth and identification errors excluded.',
   measurements,measurement_assumptions:{artwork:'Visible face corners exclude frame and shadow. Wall-plane pose, depth and camera alignment are assumptions.',pendant:'Only the recorded confirmed diameter is used. Actual rim elevation, shade height and suspension length are unknown; apparent width at a proxy elevation does not prove physical size.'},limitations:data.limitations,approved:false};
 }
 const api={plane,measure,uncertainty,alignment,buildReport};if(typeof module!=='undefined')module.exports=api;else root.ProductReviewMath=api;
})(typeof window==='undefined'?{}:window);
