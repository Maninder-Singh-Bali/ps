'use strict';
const assert=require('node:assert/strict');
const {walkProject,raycast,rayFor,walkMove,defaults,frame,project}=require('../static/model-viewer.js');
const floor={floor:true,floorName:'Ground',points:[[0,0,0],[10,0,0],[10,10,0],[0,10,0]]};
const wall={id:'wall',architecture:true,surfaceKind:'wall',floorName:'Ground',points:[[0,1,0],[10,1,0],[10,1,3],[0,1,3]]};
const ceiling={ceiling:true,surfaceKind:'ceiling',points:[[0,0,3],[10,0,3],[10,10,3],[0,10,3]]};
const w={position:[5,5,1.6],yaw:0,pitch:0,unit:1,floorName:'Ground'};
let ray=rayFor([250,200],{walk:w},null,500,400),hit=raycast(ray,[wall,ceiling,floor]);assert.equal(hit.id,'wall');assert.deepEqual(hit.point,[5,1,1.6]);assert(hit.normal.every((n,i)=>Math.abs(n-[0,1,0][i])<1e-9));
ray=rayFor([250,200],{walk:{...w,pitch:Math.PI/2-.01}},null,500,400);hit=raycast(ray,[wall,ceiling,floor]);assert(hit.ceiling);assert(Math.abs(hit.point[2]-3)<1e-9);
const crossing=walkProject([[4,6,0],[6,6,0],[6,1,3],[4,1,3]],w,500,400,10);assert(crossing.length>=3);assert(crossing.flat().every(Number.isFinite));
assert.equal(walkProject([[4,6,0],[6,6,0],[6,7,3]],w,500,400,10).length,0,'Geometry behind the eye is clipped');
let pos=w;for(let i=0;i<120;i++)pos=walkMove(pos,1,0,.05,[wall,floor]);assert(pos.position[1]>=1.18,'Walls block walking');assert(pos.position[1]<1.3);
const side=walkMove(w,0,1,.05,[wall,floor]);assert(side.position[0]>5);assert.equal(side.position[2],1.6);
const edge={...w,position:[.01,5,1.6]};assert.equal(walkMove(edge,0,-1,.05,[floor]).position[0],.01,'Do not walk off the slab');
const bounds=frame([wall,floor]);for(const projection of ['orthographic','perspective']){const v={...defaults(),projection},point=[5,1,1.6],screen=project(point,v,bounds,500,400),r=rayFor(screen,v,bounds,500,400),h=raycast(r,[wall]);assert(h);h.point.forEach((x,i)=>assert(Math.abs(x-point[i])<1e-8));}
console.log('Walk projection, near clipping, surface picking, wall collisions, slab boundaries and orbit ray mapping passed.');

