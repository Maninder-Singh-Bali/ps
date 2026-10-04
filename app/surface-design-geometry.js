'use strict';
// Draft surface coordinates are metres. Wall x stays measured from saved end A;
// y is elevation. Horizontal surfaces use plan X/Y, never a mirrored image.
(()=>{
const copy=x=>JSON.parse(JSON.stringify(x)),dist=(a,b)=>Math.hypot(a[0]-b[0],a[1]-b[1]);
const kinds={painting:[.6,.8,.03],mirror:[.6,.9,.025],sconce:[.16,.3,.15],switchboard:[.16,.09,.015],socket:[.09,.09,.015],tv:[1.2,.7,.08],shelf:[.9,.06,.25],panel:[.6,1.2,.025],pendant:[.36,.36,.25],downlight:[.1,.1,.06],fan:[1.2,1.2,.2],grille:[.5,.2,.06],track:[2,.04,.04],profile:[2,.025,.025],bulkhead:[1.2,1.2,.15],rug:[1.6,2.3,.012],threshold:[.9,.1,.02],border:[2,.08,.012]};
function context(d,s){const m=d.calibration?.metres_per_pixel;if(!m)throw Error('Calibrate the drawing first.');if(s.kind==='wall'){const w=d.features.find(w=>w.id===s.wall_id&&w.kind==='wall');if(!w)return {missing:true};const L=dist(...w.points)*m,u=w.points[1].map((v,i)=>(v-w.points[0][i])*m/L);return {wall:w,L,H:w.height_m??d.wall_height_m,u,n:[-u[1]*s.side,u[0]*s.side],origin:w.points[0].map(v=>v*m),m};}const xs=s.boundary.map(p=>p[0]),ys=s.boundary.map(p=>p[1]),origin=[Math.min(...xs)*m,Math.min(...ys)*m];return {origin,L:(Math.max(...xs)-Math.min(...xs))*m,H:(Math.max(...ys)-Math.min(...ys))*m,m};}
function hull(ps){const sorted=ps.slice().sort((a,b)=>a[0]-b[0]||a[1]-b[1]),cross=(a,b,c)=>(b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0]);const part=xs=>{const out=[];for(const p of xs){while(out.length>1&&cross(out.at(-2),out.at(-1),p)<=0)out.pop();out.push(p);}return out;};return part(sorted).slice(0,-1).concat(part(sorted.reverse()).slice(0,-1));}
function corners(o){if(o.run){const r=o.rotation*Math.PI/180,h=o.height/2;return hull(o.run.flatMap(p=>[[-h,-h],[h,-h],[h,h],[-h,h]].map(q=>[p[0]+q[0],p[1]+q[1]]))).map(p=>[o.x+p[0]*Math.cos(r)-p[1]*Math.sin(r),o.y+p[0]*Math.sin(r)+p[1]*Math.cos(r)]);}const r=o.rotation*Math.PI/180,c=Math.cos(r),s=Math.sin(r);return [[-1,-1],[1,-1],[1,1],[-1,1]].map(([x,y])=>[o.x+x*o.width/2*c-y*o.height/2*s,o.y+x*o.width/2*s+y*o.height/2*c]);}
function inside(p,poly){let yes=false;for(let i=0,j=poly.length-1;i<poly.length;j=i++){const a=poly[i],b=poly[j],v=[b[0]-a[0],b[1]-a[1]],q=[p[0]-a[0],p[1]-a[1]];if(Math.abs(v[0]*q[1]-v[1]*q[0])<1e-7&&q[0]*v[0]+q[1]*v[1]>=-1e-7&&q[0]*v[0]+q[1]*v[1]<=v[0]*v[0]+v[1]*v[1]+1e-7)return true;if((a[1]>p[1])!==(b[1]>p[1])&&p[0]<(b[0]-a[0])*(p[1]-a[1])/(b[1]-a[1])+a[0])yes=!yes;}return yes;}
function overlaps(a,b){for(const p of [a,b])for(let i=0;i<p.length;i++){const q=p[(i+1)%p.length],n=[q[1]-p[i][1],p[i][0]-q[0]],A=a.map(v=>v[0]*n[0]+v[1]*n[1]),B=b.map(v=>v[0]*n[0]+v[1]*n[1]);if(Math.max(...A)<=Math.min(...B)+1e-8||Math.max(...B)<=Math.min(...A)+1e-8)return false;}return true;}
function openingRects(d,s){const c=context(d,s);if(c.missing||s.kind!=='wall')return [];return d.features.filter(o=>o.host_wall_id===s.wall_id).map(o=>({id:o.id,x:(o.offset+o.width/2)*c.m,y:((o.kind==='window'?(o.sill_m??.9):(o.base_m??0))+(o.head_m??(o.kind==='window'?2.4:2.2)))/2,width:o.width*c.m,height:(o.head_m??(o.kind==='window'?2.4:2.2))-(o.kind==='window'?(o.sill_m??.9):(o.base_m??0)),rotation:0}));}
// View-only context. Never split host walls or change surface/item coordinates.
function roomPolygon(d,r){const b=r.bbox;return (r.area_polygon||[[b[0],b[1]],[b[0]+b[2],b[1]],[b[0]+b[2],b[1]+b[3]],[b[0],b[1]+b[3]]]).map(p=>[p[0]*d.width,p[1]*d.height]);}
function roomWallSpans(d,s,r){
 const c=context(d,s);if(c.missing||!r)return [];
 const poly=roomPolygon(d,r).map(p=>p.map(v=>v*c.m)),offset=c.wall.thickness*c.m/2+.001;
 const origin=c.origin.map((v,i)=>v+c.n[i]*offset),cross=(a,b)=>a[0]*b[1]-a[1]*b[0],cuts=[0,c.L];
 for(let i=0;i<poly.length;i++){const a=poly[i],b=poly[(i+1)%poly.length],v=b.map((x,j)=>x-a[j]),q=a.map((x,j)=>x-origin[j]),den=cross(c.u,v);if(Math.abs(den)<1e-9)continue;const x=cross(q,v)/den,t=cross(q,c.u)/den;if(x>0&&x<c.L&&t>=0&&t<=1)cuts.push(x);}
 cuts.sort((a,b)=>a-b);const spans=[];
 for(let i=1;i<cuts.length;i++){const a=cuts[i-1],b=cuts[i];if(b-a>1e-6&&inside(origin.map((v,j)=>v+c.u[j]*(a+b)/2),poly))spans.push([a,b]);}
 return spans;
}
function roomWallSide(d,w,r){if(!r)return null;const sides=[-1,1].filter(side=>roomWallSpans(d,{kind:'wall',wall_id:w.id,side},r).length);return sides.length===1?sides[0]:null;}
function wallPartitions(d,s){
 const c=context(d,s);if(c.missing)return [];const result=[],eps=1e-6;
 for(const w of d.features){if(w.kind!=='wall'||w.id===s.wall_id)continue;
  const ps=w.points.map(p=>{const q=p.map((v,i)=>v*c.m-c.origin[i]);return [q[0]*c.u[0]+q[1]*c.u[1],q[0]*c.n[0]+q[1]*c.n[1]];}),[a,b]=ps,dy=b[1]-a[1];
  if(Math.abs(dy)<eps)continue;const t=-a[1]/dy;
  // Actual segment intersections only: do not bridge a gap to another wall.
  if(t< -eps||t>1+eps)continue;const x=a[0]+t*(b[0]-a[0]);if(x<=eps||x>=c.L-eps)continue;
  const length=dist(a,b),width=(w.thickness||0)*c.m*length/Math.abs(dy);
  result.push({id:w.id,x,width:Math.min(c.L,width),height:Math.min(c.H,w.height_m??d.wall_height_m),facing:Math.max(a[1],b[1])>eps});
 }
 return result.sort((a,b)=>a.x-b.x);
}
function conflicts(d,s,o){const c=context(d,s);if(c.missing)return ['Host wall missing — item retained; select a new host explicitly.'];const ps=corners(o),issues=[];if(s.kind==='wall'){if(ps.some(p=>p[0]<-1e-6||p[1]<-1e-6||p[0]>c.L+1e-6||p[1]>c.H+1e-6))issues.push('Outside wall face');for(const q of openingRects(d,s))if(overlaps(ps,corners(q)))issues.push('Opening conflict: '+q.id);}else{const world=ps.map(p=>p.map((v,i)=>(v+c.origin[i])/c.m));if(world.some(p=>!inside(p,s.boundary))||(s.holes||[]).some(h=>world.some(p=>inside(p,h))||h.some(p=>inside(p,world))))issues.push('Outside surface or over a void');}for(const q of d.surface_design?.items||[])if(q.surface_id===s.id&&q.id!==o.id&&overlaps(ps,corners(q)))issues.push('Overlaps '+q.kind);return issues;}
function world(d,s,o,p=[0,0],depth=0){const c=context(d,s);if(c.missing)return null;const r=o.rotation*Math.PI/180,x=o.x+p[0]*Math.cos(r)-p[1]*Math.sin(r),y=o.y+p[0]*Math.sin(r)+p[1]*Math.cos(r);if(s.kind==='wall'){const offset=c.wall.thickness*c.m/2+.003+depth;return [c.origin[0]+c.u[0]*x+c.n[0]*offset,c.origin[1]+c.u[1]*x+c.n[1]*offset,y];}return [c.origin[0]+x,c.origin[1]+y,s.kind==='ceiling'?(s.elevation_m??2.5)-(o.drop||0)-depth:(s.elevation_m||0)+.005+depth];}
function snap(d,s,o,tol){const c=context(d,s),xs=[0,c.L/2,c.L],ys=[0,c.H/2,c.H],others=[...openingRects(d,s),...(d.surface_design?.items||[]).filter(q=>q.surface_id===s.id&&q.id!==o.id)];for(const q of others){const ps=corners(q);xs.push(Math.min(...ps.map(p=>p[0])),q.x,Math.max(...ps.map(p=>p[0])));ys.push(Math.min(...ps.map(p=>p[1])),q.y,Math.max(...ps.map(p=>p[1])));}const out=copy(o),guides=[];for(const [axis,refs] of [[0,xs],[1,ys]]){const ps=corners(out),positions=[Math.min(...ps.map(p=>p[axis])),out[axis?'y':'x'],Math.max(...ps.map(p=>p[axis]))];let best=null;for(const ref of refs)for(const pos of positions){const delta=ref-pos;if(Math.abs(delta)<=tol&&(!best||Math.abs(delta)<Math.abs(best.delta)))best={delta,ref};}if(best){out[axis?'y':'x']+=best.delta;guides.push({axis,value:best.ref});}}return {item:out,guides};}
function align(items,mode){const out=copy(items);if(out.length<2)throw Error('Shift-click at least two items on this face.');if(mode==='space'){if(out.length<3)throw Error('Select at least three items to distribute.');out.sort((a,b)=>a.x-b.x);const first=out[0],last=out.at(-1),gap=(last.x+last.width/2-(first.x-first.width/2)-out.reduce((s,o)=>s+o.width,0))/(out.length-1);let edge=first.x-first.width/2;for(const o of out){o.x=edge+o.width/2;edge+=o.width+gap;}return out;}const axis=['left','right','centre-x'].includes(mode)?'x':'y',edge=mode==='left'||mode==='bottom'?-1:mode==='right'||mode==='top'?1:0,extent=o=>{const ps=corners(o).map(p=>p[axis==='x'?0:1]);return edge<0?Math.min(...ps):edge>0?Math.max(...ps):o[axis];},target=extent(out[0]);for(const o of out)o[axis]+=target-extent(o);return out;}
// Drag any local corner; keep its opposite fixed (default +X/+Y for compatibility).
function resize(o,delta,corner=2,fromCentre=false){
 if(fromCentre)delta=delta.map(v=>v*2);
 const out=copy(o),r=o.rotation*Math.PI/180,c=Math.cos(r),s=Math.sin(r),dx=delta[0]*c+delta[1]*s,dy=-delta[0]*s+delta[1]*c;
 const [sx,sy]=[[-1,-1],[1,-1],[1,1],[-1,1]][corner]||[1,1];
 out.width=Math.max(.01,o.width+sx*dx);out.height=Math.max(.01,o.height+sy*dy);
 if(o.reference?.aspect_locked!==false){const factor=Math.max(.01/Math.min(o.width,o.height),1+(sx*dx*o.width+sy*dy*o.height)/(o.width*o.width+o.height*o.height));out.width=o.width*factor;out.height=o.height*factor;}
 const x=fromCentre?0:sx*(out.width-o.width)/2,y=fromCentre?0:sy*(out.height-o.height)/2;out.x+=x*c-y*s;out.y+=x*s+y*c;return out;
}
function translate(items,dx,dy){return items.map(o=>({...copy(o),x:o.x+dx,y:o.y+dy}));}
const api={roomPolygon,roomWallSpans,roomWallSide,wallPartitions,copy,kinds,context,corners,inside,overlaps,openingRects,conflicts,world,snap,align,resize,translate};if(typeof module!=='undefined')module.exports=api;else window.SurfaceDesignGeometry=api;
})();
