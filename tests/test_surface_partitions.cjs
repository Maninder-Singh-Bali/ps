'use strict';
const assert=require('node:assert/strict'),D=require('../static/surface-design-geometry.js');
const wall=(id,a,b)=>({id,kind:'wall',points:[a,b],thickness:16,height_m:2.8});
const host=wall('host',[60,460],[1200,460]);
const d={width:1260,height:960,calibration:{metres_per_pixel:.01},wall_height_m:2.8,features:[host,wall('kitchen',[600,460],[600,900]),wall('bath',[900,460],[900,900]),wall('opposite',[440,340],[440,460]),wall('gap',[700,480],[700,900]),wall('parallel',[800,460],[1000,460])]},s={kind:'wall',wall_id:'host',side:1};
const r={bbox:[60/1260,460/960,540/1260,440/960]},before=JSON.stringify(d);
assert.equal(D.roomWallSide(d,host,r),1);
const spans=D.roomWallSpans(d,s,r);assert.equal(spans.length,1);assert.ok(Math.abs(spans[0][0])<1e-8);assert.ok(Math.abs(spans[0][1]-5.4)<1e-8);
assert.deepEqual(D.wallPartitions(d,s).map(p=>[p.id,p.facing]),[['opposite',false],['kitchen',true],['bath',true]]);
assert.ok(Math.abs(D.wallPartitions(d,s)[1].width-.16)<1e-8);
assert.equal(D.roomWallSpans(d,{...s,side:-1},r).length,0);
const reversed=structuredClone(d);reversed.features[0].points.reverse();assert.equal(D.roomWallSide(reversed,reversed.features[0],r),-1);
assert.ok(Math.abs(D.wallPartitions(reversed,{...s,side:-1}).find(p=>p.id==='kitchen').x-6)<1e-8);
const angle=Math.PI/4,angled=structuredClone(d);angled.features.forEach(w=>w.points=w.points.map(([x,y])=>[x*Math.cos(angle)-y*Math.sin(angle),x*Math.sin(angle)+y*Math.cos(angle)]));
assert.ok(Math.abs(D.wallPartitions(angled,s).find(p=>p.id==='kitchen').x-5.4)<1e-8);
assert.equal(JSON.stringify(d),before,'view helpers must not mutate walls');
const concave={bbox:[0,0,1,1],area_polygon:[[60/1260,460/960],[1200/1260,460/960],[1200/1260,900/960],[900/1260,900/960],[900/1260,470/960],[600/1260,470/960],[600/1260,900/960],[60/1260,900/960]]};
assert.equal(D.roomWallSpans(d,s,concave).length,1); // The actual face still runs inside its shallow connecting strip.
console.log('Surface partition context: same/opposite side, gaps, parallel, reversed, angled, room span, nonmutation passed');
