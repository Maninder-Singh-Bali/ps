'use strict';
const assert=require('node:assert/strict');
const {defaults,frame,project,gesture,inside,Viewer}=require('../static/model-viewer.js');
const scene=[{points:[[0,0,0],[20,0,0],[20,10,0],[0,10,0]]},{points:[[0,0,3],[20,0,3],[20,0,0]]}];
const original=JSON.stringify(scene),v=defaults(),bounds=frame(scene);
assert.deepEqual(bounds.center,[10,5,1.5]);
for(let yaw=0;yaw<7;yaw+=.4)for(let pitch=-Math.PI;pitch<Math.PI;pitch+=.2)for(const f of scene)for(const p of f.points){const q=project(p,{...v,yaw,pitch},bounds,440,300);assert(q[0]>0&&q[0]<440&&q[1]>0&&q[1]<300,'Fit must include every surface at every orbit angle')}
const before=project([20,10,3],v,bounds,440,300),orbit=gesture(v,80,30,false,440,300);
assert.notDeepEqual(project([20,10,3],orbit,bounds,440,300),before);
const panned=project([20,10,3],gesture(v,40,25,true,440,300),bounds,440,300);
assert(Math.abs(panned[0]-before[0]-40)<1e-9);assert(Math.abs(panned[1]-before[1]-25)<1e-9);
// Full turns return to the same view; neither axis stops at the poles.
for(const turns of [-3,-1,1,3])for(const axis of ['horizontal','vertical']){
 const next=gesture(v,axis==='horizontal'?turns*2*Math.PI/.008:0,axis==='vertical'?turns*2*Math.PI/.006:0,false,440,300);
 const q=project([20,10,3],next,bounds,440,300);
 q.forEach((n,i)=>assert(Math.abs(n-before[i])<1e-8,'Full rotation must return to its starting projection'));
}
assert(gesture({...v,pitch:Math.PI/2},0,30,false,440,300).pitch>Math.PI/2,'Pass through top');
assert(gesture({...v,pitch:-Math.PI/2},0,-30,false,440,300).pitch<-Math.PI/2,'Pass through bottom');
const edgeA=project([20,10,3],{...v,pitch:Math.PI-1e-6},bounds,440,300),edgeB=project([20,10,3],{...v,pitch:-Math.PI+1e-6},bounds,440,300);
edgeA.forEach((n,i)=>assert(Math.abs(n-edgeB[i])<.001,'No jump at angular wrap'));
assert(gesture(v,40,0,false,440,300).yaw<v.yaw,'Drag right rotates model right');
assert(inside([1,1],[[0,0],[2,0],[2,2],[0,2]]));assert(!inside([4,1],[[0,0],[2,0],[2,2],[0,2]]));
// A real event lifecycle with a minimal canvas: orbit/pan/cancel never selects or edits.
global.ResizeObserver=class{observe(){}disconnect(){}};
const canvas={style:{},clientWidth:440,clientHeight:300,focus(){},setPointerCapture(){},releasePointerCapture(){},hasPointerCapture(){return true},getBoundingClientRect(){return {left:0,top:0}}};
let picked=0;const viewer=new Viewer(canvas,defaults(),()=>picked++);viewer.draw=()=>{};
viewer.hits=[{id:'sofa',points:[[0,0],[100,0],[100,100],[0,100]]}];
const ev=(x,y,button=0)=>({clientX:x,clientY:y,button,pointerId:1,preventDefault(){}});
canvas.onpointerdown(ev(10,10));canvas.onpointerup(ev(10,10));assert.equal(picked,1);
canvas.onpointerdown(ev(10,10));canvas.onpointermove(ev(60,30));canvas.onpointerup(ev(60,30));assert.equal(picked,1);
canvas.onpointerdown(ev(10,10,1));canvas.onpointermove(ev(50,40,1));canvas.onpointerup(ev(50,40,1));assert.equal(picked,1);
canvas.onpointerdown(ev(10,10));canvas.onpointercancel();canvas.onpointerup(ev(10,10));assert.equal(picked,1);
viewer.zoom(1e6);assert.equal(viewer.view.zoom,12);viewer.zoom(1e-9);assert.equal(viewer.view.zoom,.25);viewer.reset(true);assert.equal(viewer.view.pitch,Math.PI/2);assert.equal(viewer.view.zoom,1);
assert.equal(JSON.stringify(scene),original);assert.deepEqual(v,defaults());
// Perspective foreshortens distance; orthographic keeps parallel widths equal.
const b={center:[0,0,0],radius:10},ortho={...defaults(),yaw:0,pitch:0},pers={...ortho,projection:'perspective'};
const widthAt=(view,y)=>project([2,y,0],view,b,500,500)[0]-project([-2,y,0],view,b,500,500)[0];
assert.equal(widthAt(ortho,5),widthAt(ortho,-5));assert(widthAt(pers,5)>widthAt(pers,-5));
for(const projection of ['orthographic','perspective'])for(let yaw=0;yaw<6.4;yaw+=.4)for(let pitch=-3.2;pitch<3.2;pitch+=.4)for(const f of scene)for(const p of f.points){const q=project(p,{...v,yaw,pitch,projection},bounds,440,300);assert(q.every(Number.isFinite));assert(q[0]>0&&q[0]<440&&q[1]>0&&q[1]<300)}
viewer.view.projection='perspective';viewer.reset();assert.equal(viewer.view.projection,'perspective');
console.log('Model viewer: orbit, fit, pan, zoom, picking, cancellation and geometry preservation passed.');

assert(gesture(v,0,40,false,440,300).pitch>v.pitch,'Downward drag increases elevation');
assert(gesture(v,0,-40,false,440,300).pitch<v.pitch,'Upward drag decreases elevation');
const {pick}=require('../static/model-viewer.js');
const near={id:'cushion',points:[[0,0,3],[10,0,3],[10,10,3],[0,10,3]]},far={id:'seat-base',points:[[0,0,0],[10,0,0],[10,10,0],[0,10,0]]};
assert.equal(pick([3,3],[near,far]).id,'cushion','Selection follows depth, not surface iteration order');
assert.equal(pick([3,3],[far,near]).id,'cushion');assert.equal(pick([30,30],[near,far]),null);
const many=Array.from({length:40000},()=>near);assert(Number.isFinite(frame(many).radius),'Detailed furniture scenes do not overflow argument limits');
console.log('Depth-aware picking and large-scene bounds passed.');

// A room-sized orbit can put adjoining architecture behind the camera.
// Every yaw must clip before division, including faces straddling the eye plane.
const {orbitProject,rotate}=require('../static/model-viewer.js');
const focus={center:[0,0,0],radius:2},pv={...defaults(),yaw:0,pitch:0,projection:'perspective'};
assert.deepEqual(orbitProject([[-1,7,0],[1,7,0],[1,8,1]],pv,focus,500,400),[]);
const spanning=[[-1,5,0],[1,5,0],[1,7,1],[-1,7,1]];
const clipped=orbitProject(spanning,pv,focus,500,400);
assert.equal(clipped.length,4);assert(clipped.flat().every(Number.isFinite));
assert(clipped.every(p=>p[2]>=2),'Behind-eye vertices must not invert the depth or floor');
for(let yaw=0;yaw<Math.PI*2;yaw+=Math.PI/24){
 const view={...pv,yaw},poly=orbitProject(spanning,view,focus,500,400);
 assert(poly.flat().every(Number.isFinite));
 if(spanning.every(p=>6-rotate(p,view)[2]<.02))assert.equal(poly.length,0);
}
const safe=[[-1,0,0],[1,0,0],[1,0,1]];
assert.deepEqual(orbitProject(safe,pv,focus,500,400),safe.map(p=>project(p,pv,focus,500,400)));
console.log('Room-focus perspective near-plane clipping and full orbit passed.');
