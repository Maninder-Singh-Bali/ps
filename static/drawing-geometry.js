'use strict';
(() => {
 const clone=v=>JSON.parse(JSON.stringify(v));
 function project(points,p){
  const [a,b]=points,dx=b[0]-a[0],dy=b[1]-a[1],l2=dx*dx+dy*dy;
  if(l2<.04)throw Error('Select a longer wall.');
  const t=((p[0]-a[0])*dx+(p[1]-a[1])*dy)/l2;
  return {t,point:[a[0]+t*dx,a[1]+t*dy]};
 }
 function insert(wall,p,q,kind,id){
  if(wall.kind!=='wall'||!['window','door','sliding_door'].includes(kind))throw Error('Select a straight wall to insert an opening.');
  const one=project(wall.points,p),two=project(wall.points,q),lo=Math.min(one.t,two.t),hi=Math.max(one.t,two.t),L=Math.hypot(wall.points[1][0]-wall.points[0][0],wall.points[1][1]-wall.points[0][1]);
  if(lo<0||hi>1||L*(hi-lo)<.2)throw Error('Choose two different points within the selected wall.');
  if((lo>0&&lo*L<.2)||(hi<1&&(1-hi)*L<.2))throw Error('Leave a longer wall end or place the opening exactly at the end.');
  const at=t=>wall.points[0].map((v,i)=>v+t*(wall.points[1][i]-v));
  const result=[];
  if(lo>0)result.push({...clone(wall),id:id(),points:[clone(wall.points[0]),at(lo)]});
  const opening={...clone(wall),id:id(),kind,points:[at(lo),at(hi)]};result.push(opening);
  if(hi<1)result.push({...clone(wall),id:id(),points:[at(hi),clone(wall.points[1])]});
  return {features:result,openingId:opening.id};
 }
 function resize(feature,length,thickness,width,height){
  if(!Number.isFinite(length)||length<.2||!Number.isFinite(thickness)||thickness<.1||thickness>50)throw Error('Enter a valid length and thickness.');
  const f=clone(feature),[a,b]=f.points,L=Math.hypot(b[0]-a[0],b[1]-a[1]);
  f.points[1]=a.map((v,i)=>v+(b[i]-v)*length/L);f.thickness=thickness;
  if(f.points[1].some((v,i)=>!Number.isFinite(v)||v<0||v>[width,height][i]))throw Error('The resized wall would extend outside the plan.');
  return f;
 }
 function zoom(view,anchor,delta,planWidth){
  const width=Math.min(planWidth*8,Math.max(planWidth/100,view[2]*Math.exp(Math.max(-500,Math.min(500,delta))*.0015))),ratio=width/view[2];
  return [anchor[0]-(anchor[0]-view[0])*ratio,anchor[1]-(anchor[1]-view[1])*ratio,width,view[3]*ratio];
 }
 function split(wall,p,id){
  if(wall.kind!=='wall')throw Error('Select a straight wall to split.');
  const cut=project(wall.points,p),length=Math.hypot(wall.points[1][0]-wall.points[0][0],wall.points[1][1]-wall.points[0][1]);
  if(cut.t*length<.2||(1-cut.t)*length<.2)throw Error('Split inside the wall, away from either end.');
  return [
   {...clone(wall),id:id(),points:[clone(wall.points[0]),cut.point]},
   {...clone(wall),id:id(),points:[clone(cut.point),clone(wall.points[1])]}
  ];
 }
 function dragEndpoint(feature,index,delta,width,height,lockAxis=true){
  const out=clone(feature),anchor=feature.points[1-index],moving=feature.points[index];
  let target=moving.map((v,i)=>v+delta[i]);
  if(lockAxis){
   const dx=moving[0]-anchor[0],dy=moving[1]-anchor[1],length=Math.hypot(dx,dy),u=[dx/length,dy/length];
   let distance=Math.max(.2,(target[0]-anchor[0])*u[0]+(target[1]-anchor[1])*u[1]);
   for(let i=0;i<2;i++)if(Math.abs(u[i])>1e-9)distance=Math.min(distance,((u[i]>0?[width,height][i]:0)-anchor[i])/u[i]);
   target=anchor.map((v,i)=>v+distance*u[i]);
  }else target=target.map((v,i)=>Math.max(0,Math.min([width,height][i],v)));
  if(Math.hypot(target[0]-anchor[0],target[1]-anchor[1])<.2)return out;
  out.points[index]=target;return out;
 }
 function resizeOutline(edit,box,delta){
  const a=(edit.rotation||0)*Math.PI/180,c=Math.cos(a),s=Math.sin(a);
  const local=[c*delta[0]+s*delta[1],-s*delta[0]+c*delta[1]],sx=edit.sx||1,sy=edit.sy||1;
  const nx=box.width>.01?Math.max(.01,Math.min(100,sx+local[0]/box.width)):sx;
  const ny=box.height>.01?Math.max(.01,Math.min(100,sy+local[1]/box.height)):sy;
  const ax=(sx-nx)*(box.x-(edit.cx||0)),ay=(sy-ny)*(box.y-(edit.cy||0));
  return {...clone(edit),sx:nx,sy:ny,dx:(edit.dx||0)+c*ax-s*ay,dy:(edit.dy||0)+s*ax+c*ay};
 }
 function snapPoint(p,targets,tolerance){
  const point=[...p],guides=[];
  for(let axis=0;axis<2;axis++){let best=null,distance=tolerance;
   for(const q of targets){const d=Math.abs(p[axis]-q[axis]);if(d<=distance){best=q;distance=d}}
   if(best){point[axis]=best[axis];guides.push({axis,value:best[axis],from:[...best],to:[...point]})}
  }
  return {point,guides};
 }
 function snapSegment(p,walls,tolerance){
  let best=null,distance=tolerance;
  for(const wall of walls){if(wall.kind!=='wall')continue;const q=project(wall.points,p);if(q.t<0||q.t>1)continue;
   const d=Math.hypot(q.point[0]-p[0],q.point[1]-p[1]);if(d<=distance){distance=d;best={point:q.point,wall}}}
  return best;
 }
 function snapBounds(points,targets,tolerance){
  const shift=[0,0],guides=[];
  for(let axis=0;axis<2;axis++){
   const lo=Math.min(...points.map(p=>p[axis])),hi=Math.max(...points.map(p=>p[axis]));let distance=tolerance,best=null;
   for(const value of [lo,(lo+hi)/2,hi])for(const p of targets){const delta=p[axis]-value;if(Math.abs(delta)<distance){distance=Math.abs(delta);best={axis,value:p[axis],delta}}}
   if(best){shift[axis]=best.delta;guides.push(best)}
  }
  return {shift,guides};
 }
 function cutOpening(wall,opening,id){
  if(wall.kind!=='wall'||!['window','door','sliding_door'].includes(opening.kind))return null;
  const [a,b]=wall.points,[p,q]=opening.points,L=Math.hypot(b[0]-a[0],b[1]-a[1]),O=Math.hypot(q[0]-p[0],q[1]-p[1]);if(L<.2||O<.2)return null;
  const u=[(b[0]-a[0])/L,(b[1]-a[1])/L];
  if(Math.abs(u[0]*(q[1]-p[1])-u[1]*(q[0]-p[0]))/O>.01)return null;
  if(Math.max(...[p,q].map(v=>Math.abs(u[0]*(v[1]-a[1])-u[1]*(v[0]-a[0]))))>((wall.thickness||1.5)+(opening.thickness||1.5))/2+.05)return null;
  const ts=[project(wall.points,p).t,project(wall.points,q).t],lo=Math.max(0,Math.min(...ts)),hi=Math.min(1,Math.max(...ts));if((hi-lo)*L<.2)return null;
  const at=t=>a.map((v,i)=>v+t*(b[i]-v)),out=[];
  if(lo*L>=.2)out.push({...clone(wall),id:id(),points:[clone(a),at(lo)]});
  if((1-hi)*L>=.2)out.push({...clone(wall),id:id(),points:[at(hi),clone(b)]});
  return out;
 }
 const api={project,insert,resize,zoom,split,dragEndpoint,resizeOutline,snapPoint,snapSegment,snapBounds,cutOpening};
 if(typeof module!=='undefined')module.exports=api;else window.DrawingGeometry=api;
})();
