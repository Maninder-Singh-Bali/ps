'use strict';
// Browser-local 2D staging resolver. Offset sectors mirror wall_junctions.py;
// this never substitutes for the production backend's validation or 3D mesh.
(()=>{
 const nodeMode=typeof module!=='undefined',P=nodeMode?require('./vendor/polygon-clipping.js'):window.polygonClipping;
 const G=nodeMode?require('../static/trace-geometry.js'):window.TraceGeometry,D=nodeMode?require('../static/drawing-geometry.js'):window.DrawingGeometry;
 const EPS=1e-6,cross=(a,b)=>a[0]*b[1]-a[1]*b[0],sub=(a,b)=>a.map((v,i)=>v-b[i]),dist=(a,b)=>Math.hypot(...sub(a,b)),offset=(p,u,h,sign=1)=>[p[0]-u[1]*h*sign,p[1]+u[0]*h*sign];
 function envelope(walls){
  if(walls.length>400)throw Error('Synthetic junction preview supports up to 400 wall segments.');
  const nodes=new Map(),segments=[],bodies=[];
  const node=p=>{const key=p.map(v=>v.toFixed(6)).join(':');if(!nodes.has(key))nodes.set(key,{point:[...p],rays:[]});return nodes.get(key);};
  for(const w of walls){const [a,b]=w.points,L=dist(a,b);if(L<EPS)continue;const u=sub(b,a).map(v=>v/L);segments.push({a,b,u,L,h:w.thickness/2,id:w.id});node(a);node(b);}
  for(let i=0;i<segments.length;i++)for(const v of segments.slice(i+1)){
   const w=segments[i],den=cross(w.u,v.u);if(Math.abs(den)<1e-10)continue;
   const d=sub(v.a,w.a),t=cross(d,v.u)/den,s=cross(d,w.u)/den;
   if(t>=-EPS&&t<=w.L+EPS&&s>=-EPS&&s<=v.L+EPS)node(w.a.map((x,k)=>x+t*w.u[k]));
  }
  if(nodes.size>4000)throw Error('Synthetic junction preview has too many intersections.');
  const along=(w,p)=>{const d=sub(p,w.a),t=d[0]*w.u[0]+d[1]*w.u[1];return Math.abs(cross(w.u,d))<=EPS&&t>=-EPS&&t<=w.L+EPS?t:null;};
  for(const n of nodes.values()){
   const unique=new Map();
   const add=(u,h,length,id)=>{const angle=(Math.atan2(u[1],u[0])+2*Math.PI)%(2*Math.PI),key=angle.toFixed(9);if(!unique.has(key)||h>unique.get(key).h)unique.set(key,{u,h,length,id,angle});};
   for(const w of segments){const t=along(w,n.point);if(t===null)continue;if(t>EPS)add(w.u.map(v=>-v),w.h,t,w.id);if(t<w.L-EPS)add(w.u,w.h,w.L-t,w.id);}
   n.rays=[...unique.values()].sort((a,b)=>a.angle-b.angle);
  }
  const joins=[];
  for(const n of nodes.values()){
   const rs=n.rays,p=n.point,corners=[];
   if(rs.length===1){const r=rs[0];r.left=offset(p,r.u,r.h);r.right=offset(p,r.u,r.h,-1);continue;}
   for(let i=0;i<rs.length;i++){
    const r=rs[i],s=rs[(i+1)%rs.length],a=offset(p,r.u,r.h),b=offset(p,s.u,s.h,-1),den=cross(r.u,s.u);
    const t=Math.abs(den)>1e-10?cross(sub(b,a),s.u)/den:null,q=t===null?null:a.map((v,k)=>v+t*r.u[k]);
    const bound=Math.min(3*Math.max(r.h,s.h),Math.max(r.h,Math.min(r.length,s.length)*.45)),bevel=!q||dist(p,q)>bound;
    if(bevel){r.left=a;s.right=b;corners.push(a,b);}else{r.left=q;s.right=q;corners.push(q);}
    if((s.angle-r.angle+2*Math.PI)%(2*Math.PI)>Math.PI+1e-9)joins.push({point:p,walls:[r.id,s.id],kind:bevel?'bevel':'mitre',limit_px:bound});
   }
   if(corners.length>=3)bodies.push([corners]);
  }
  const ray=(n,u)=>n.rays.reduce((best,r)=>!best||dist(r.u,u)<dist(best.u,u)?r:best,null);
  for(const w of segments){
   const ns=[...nodes.values()].map(n=>({n,t:along(w,n.point)})).filter(x=>x.t!==null).sort((a,b)=>a.t-b.t);
   for(let i=1;i<ns.length;i++){if(ns[i].t-ns[i-1].t<EPS)continue;const r=ray(ns[i-1].n,w.u),s=ray(ns[i].n,w.u.map(v=>-v));bodies.push([[r.left,s.right,s.left,r.right]]);}
  }
  const polys=bodies.length?P.union(...bodies):[],rings=polys.map(p=>({outer:p[0].slice(0,-1),holes:p.slice(1).map(h=>h.slice(0,-1))}));
  const area=ps=>Math.abs(ps.reduce((s,p,i)=>s+cross(p,ps[(i+1)%ps.length]),0))/2;
  return {rings,joins,area_px2:rings.reduce((sum,r)=>sum+area(r.outer)-r.holes.reduce((n,h)=>n+area(h),0),0)};
 }
 function resolve(features){
  const fs=G.hosted(features),opens=fs.filter(f=>['door','window','sliding_door'].includes(f.kind));
  const walls=fs.filter(f=>f.kind==='wall').flatMap(w=>{let pieces=[w];for(const o of opens){if(o.host_wall_id&&o.host_wall_id!==w.id)continue;pieces=pieces.flatMap(p=>D.cutOpening(p,o,()=>w.id)||[p]);}return pieces;});
  const result={version:1,method:'synthetic browser-local joined offset union',...envelope(walls),reference_lines_unchanged:true,simulated:true};
  let hash=2166136261;for(const c of JSON.stringify(result))hash=Math.imul(hash^c.charCodeAt(0),16777619);result.hash='local-joined-'+(hash>>>0).toString(16);return result;
 }
 const api={resolve,envelope};if(nodeMode)module.exports=api;else window.StagingJoinedFootprints=api;
})();
