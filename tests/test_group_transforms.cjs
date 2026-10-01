const assert=require('node:assert/strict'),L=require('../static/furniture-library.js');
const p={width:1000,height:600};
const sofa=L.create('sofa-2',[.1,.1,.8,.8],p,{width_m:10,depth_m:6},[.4,.4],'sofa'),chair=L.create('chair',[.1,.1,.8,.8],p,{width_m:10,depth_m:6},[.6,.6],'chair');
const rows=[{key:'f:r:sofa',type:'furniture',owner:'r',value:sofa},{key:'f:s:chair',type:'furniture',owner:'s',value:chair},{key:'w:newwindow',type:'wall',value:{id:'newwindow',kind:'window',points:[[300,200],[500,200]],thickness:3}},{key:'w:newdoor',type:'wall',value:{id:'newdoor',kind:'door',points:[[500,200],[550,200]],thickness:2,flip:false}}],before=JSON.stringify(rows);
const moved=L.transformGroup(rows,p,{delta:[25,30]});assert(Math.abs(moved[0].value.x-sofa.x-.025)<1e-10);assert(Math.abs(moved[0].value.y-sofa.y-.05)<1e-10);assert.deepEqual(moved[2].value.points,[[325,230],[525,230]]);
let rotated=rows;for(let i=0;i<4;i++)rotated=L.transformGroup(rotated,p,{rotation:90});for(let i=0;i<2;i++){assert(Math.abs(rotated[i].value.x-rows[i].value.x)<1e-10);assert(Math.abs(rotated[i].value.y-rows[i].value.y)<1e-10)}
const mirrored=L.transformGroup(rows,p,{flip:'x'});assert(mirrored[0].value.flip_x);assert(mirrored[3].value.flip);assert.equal(mirrored[0].value.seat_count,2);
const scaled=L.transformGroup(rows,p,{factor:1.1});assert(Math.abs(scaled[0].value.width-sofa.width*1.1)<1e-10);assert.equal(scaled[0].value.seat_count,2);assert(Math.abs(scaled[0].value.sofa_modules.pitch_width-sofa.sofa_modules.pitch_width*1.1)<1e-10);assert(Math.abs(scaled[2].value.thickness-3.3)<1e-9);
assert.throws(()=>L.transformGroup(rows,p,{delta:[1000,0]}));assert.equal(JSON.stringify(rows),before);
console.log('Mixed selections: movement, four-turn rotation, reflection, uniform scale, modules, boundaries and immutable snapshots passed.');
