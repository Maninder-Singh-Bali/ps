const assert=require('node:assert/strict'),M=require('../static/model-viewer.js');
const face=points=>({points,architecture:true,surfaceKind:'joined_wall',color:'#ffffff'}),v={...M.defaults(),cutaway:true,yaw:0},bounds={center:[0,0,1],radius:4};
const a=[0,-2,0],b=[0,2,0],c=[0,2,3],d=[0,-2,3],faces=[face([a,b,c]),face([a,c,d])],before=JSON.stringify(faces);
const area=f=>{let sum=0;for(let i=0;i<f.points.length;i++){const p=f.points[i],q=f.points[(i+1)%f.points.length];sum+=p[1]*q[2]-q[1]*p[2];}return Math.abs(sum)/2};
for(const triangles of [faces,[face([a,b,d]),face([b,c,d])]]){const clipped=M.cutawayFaces(triangles,v,bounds);assert.equal(clipped.reduce((n,f)=>n+area(f),0),6);assert(clipped.every(f=>f.points.every(p=>p[1]<=1e-8)));assert(clipped.every(f=>f.edge_mask.length===f.points.length));}
assert.equal(JSON.stringify(faces),before);
const cap=face([[0,-2,3],[1,-2,3],[1,2,3],[0,2,3]]);assert(M.cutawayFaces([cap],v,bounds)[0].points.every(p=>p[1]<=1e-8));
assert.equal(M.cutawayFaces(faces,{...v,cutaway:false},bounds),faces);assert.equal(M.cutawayFaces(faces,{...v,walk:{}},bounds),faces);
const furniture={...face([a,b,c]),architecture:false};assert.equal(M.cutawayFaces([furniture],v,bounds)[0],furniture);
for(const yaw of [0,.4,Math.PI/2,Math.PI]){const out=M.cutawayFaces(faces,{...v,yaw},bounds);assert(out.every(f=>f.points.every(p=>p.every(Number.isFinite))));}
assert.equal(M.cutawayFaces([face([[0,0,0],[0,2,0],[0,0,3]])],v,bounds).length,0);
console.log('Cutaway: tessellation-independent section, caps, opposite views, walk/off, furniture and nonmutation passed');

// Room focus must not use the smaller room radius to clip distant apartment walls.
const projected=[{points:[[0,0,-800],[0,0,950],[0,0,2]]}];const extent=M.depthRadius(projected,375);assert.equal(extent,950);assert(projected[0].points.every(p=>Math.abs(p[2]/(extent*1.1))<1));assert.equal(M.depthRadius([],375),375);
console.log('Room-focus depth range retains all projected apartment vertices');
