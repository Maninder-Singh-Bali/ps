const assert=require('node:assert/strict');global.window={FurnitureLibrary:{presets:[]}};
const {labelPosition,overlap}=require('../static/plan-labels.js');
const v={x:0,y:0,w:500,h:500},anchor={x:100,y:200,left:60,right:140,top:120,bottom:280};
const p=labelPosition(anchor,130,17,[],v);assert.equal(overlap(p,{x:60,y:120,w:80,h:160}),0);
const next=labelPosition(anchor,60,17,[p],v);assert.equal(overlap(next,p),0);
for(const a of [{x:0,y:0,left:0,right:5,top:0,bottom:5},{x:498,y:499,left:490,right:500,top:490,bottom:500}]){const q=labelPosition(a,100,17,[],v);assert(q.x>=0&&q.y>=0&&q.x+q.w<=500&&q.y+q.h<=500)}
assert.equal(window.PlanLabels.objectName({kind:'sofa',shape:'l',seat_count:5}),'5-seater L-shaped sofa');
assert.equal(window.PlanLabels.objectName({kind:'table',label:'Monti coffee table'}),'Coffee table');
assert.equal(window.PlanLabels.objectName({kind:'unknown'}),'Unclassified object');
console.log('Object label names, collision placement, own-footprint avoidance and viewport bounds passed');
