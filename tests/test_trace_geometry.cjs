const assert=require('node:assert/strict'),G=require('../static/trace-geometry.js');
const w={id:'w',kind:'wall',points:[[0,0],[400,0]],thickness:15},o={id:'o',kind:'door',host_wall_id:'w',offset:50,width:90,points:[[50,0],[140,0]],thickness:15};
assert.deepEqual(G.moveEndpoint([w,o],'w',1,[0,400])[1].points,[[0,50],[0,140]]);
assert.deepEqual(G.snap([2,3],[w],5).point,[0,0]);assert.deepEqual(G.snap([2,3],[w],5,false).point,[2,3]);
assert.deepEqual(G.trace([0,0],[100,0],20,'inside'),[[0,10],[100,10]]);
assert.deepEqual(G.trace([0,0],[100,0],20,'outside'),[[0,-10],[100,-10]]);
assert.throws(()=>G.split([w,o],'w',100,'q'),/opening/);const parts=G.split([w,{...o,offset:250}],'w',200,'q');assert.equal(parts[1].host_wall_id,'q');assert.equal(parts[1].offset,50);
assert.equal(G.parseLength('6\' 8"'),2.032);assert.equal(G.parseLength('4105 mm'),4.105);assert.equal(G.parseLength('10','ft'),3.048);
assert.equal(G.issues([w,{...o,offset:390}]).filter(x=>/beyond/.test(x.message)).length,1);
const ps=[[0,0],[400,0],[400,300],[0,300]],fs=ps.map((p,i)=>({id:'w'+i,kind:'wall',points:[p,ps[(i+1)%4]],thickness:15}));assert.equal(G.rooms(fs,.01)[0].area,12);assert.equal(G.rooms(fs.slice(0,3),.01).length,0);assert.equal(G.rooms(fs,0).length,0);assert.equal(G.rooms(fs.map((f,i)=>i===0?{...f,points:[[1,0],f.points[1]]}:f),.01).length,0);
const moved=G.moveEndpoint(fs,'w0',1,[420,10]);assert.deepEqual(moved[1].points[0],[420,10]);
console.log('Passed hosted movement, units, face offsets, snapping override, splitting, opening bounds, exact closure and shared junction tests.');

for(const [value,unit,metres] of [['12','in',.3048],['36','in',.9144],['12 in','m',.3048],['1 m','in',1],['25.4 mm','in',.0254]])assert.ok(Math.abs(G.parseLength(value,unit)-metres)<1e-12);
