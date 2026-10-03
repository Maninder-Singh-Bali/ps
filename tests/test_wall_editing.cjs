const assert=require('node:assert/strict'),G=require('../static/trace-geometry.js');
const wall=(id,a,b,props={})=>({id,kind:'wall',points:[a,b],thickness:10,height_m:2.5,review_note:'retain',...props});
const a=wall('a',[0,0],[100,0]),b=wall('b',[200,0],[100,0]);
const door={id:'door',kind:'door',host_wall_id:'b',offset:20,width:30,points:[[180,0],[150,0]],thickness:10,head_m:2.2,sill_m:0,hinge_end:false,flip:true,review_note:'door note'};
let fs=G.hosted([a,b,door]);let result=G.mergeWalls(fs,['a','b'],'chain');assert.equal(result.kind,'wall');assert.equal(result.features.filter(w=>w.kind==='wall').length,1);let o=result.features.find(f=>f.id==='door');assert.deepEqual(o.points,door.points);assert.equal(o.offset,150);assert.equal(o.hinge_end,true);for(const k of ['width','head_m','sill_m','flip','review_note'])assert.equal(o[k],door[k]);assert.deepEqual(result.features.find(f=>f.id==='a').points,[[0,0],[200,0]]);
const branch=wall('branch',[100,0],[100,100],{thickness:20});result=G.mergeWalls([...fs,branch],['a','b'],'chain');assert.equal(result.features.find(f=>f.id==='a').junction_nodes.length,1);assert.equal(G.members(result.features,'branch',0).length,2);let moved=G.moveEndpoint(result.features,'branch',0,[110,10]);assert.equal(G.members(moved,'branch',0).length,3);assert.ok(G.members(moved,'branch',0).every(m=>G.dist(m.point,[110,10])<1e-9));assert.equal(moved.find(f=>f.id==='door').review_note,'door note');
// Outer endpoint movement must not strand the branch, including the merged B end.
let outer=G.moveEndpoint(result.features,'a',1,[240,0]);assert.ok(outer.some(w=>w.kind==='wall'&&w.points.some(p=>G.dist(p,[240,0])<1e-9)));assert.equal(G.members(outer,'branch',0).length,3);
let split=G.split(result.features,'a',50,'split');assert.equal(G.members(split,'branch',0).length,2);assert.equal(split.find(f=>f.id==='split').junction_nodes.length,1);
const L=[a,wall('c',[100,0],[100,100])];result=G.mergeWalls(L,['a','c'],'L');assert.equal(result.kind,'chain');assert.deepEqual(result.features.map(w=>w.points),L.map(w=>w.points));assert.ok(result.features.every(w=>w.wall_chain_id==='L'));assert.equal(G.members(result.features,'a',1).length,2);
assert.throws(()=>G.mergeWalls([a,{...b,thickness:11}],['a','b'],'x'),/thickness/);assert.throws(()=>G.mergeWalls([a,{...b,review_note:'different'}],['a','b'],'x'),/review_note/);assert.throws(()=>G.mergeWalls([a,wall('b',[101,0],[200,0])],['a','b'],'x'),/disconnected/);assert.throws(()=>G.mergeWalls([a,wall('b',[0,20],[100,20])],['a','b'],'x'),/disconnected/);
let detached=G.detachEndpoint(G.junctions([a,b]),'b',1,'d');assert.throws(()=>G.mergeWalls(detached,['a','b'],'x'),/disconnected/);
assert.deepEqual(G.boxSelect([a,b,branch],[-1,-1],[201,1]),['a','b']);
const angled=wall('angled',[0,0],[100,100]);let s=G.smartSnap([51,52],[angled],{tolerance:8,connections:false});assert.match(s.hint,/Midpoint/);assert.deepEqual(s.point,[50,50]);assert.equal(s.target,null);
s=G.smartSnap([101,43],[a],{tolerance:4});assert.match(s.hint,/Aligned/);assert.deepEqual(s.point,[100,43]);assert.equal(s.target,null);
s=G.smartSnap([51,5],[a],{face:true,tolerance:2});assert.match(s.hint,/Wall face/);assert.equal(s.target,null);assert.deepEqual(s.point,[51,5]);
s=G.smartSnap([40,41],[angled],{origin:[30,50],tolerance:3});assert.match(s.hint,/Perpendicular/);assert.equal(s.target.wall,'angled');
s=G.smartSnap([51,50],[wall('h',[0,50],[100,50]),wall('v',[50,0],[50,100])],{tolerance:2});assert.ok(/Midpoint|Intersection/.test(s.hint));
s=G.smartSnap([100,1],[a],{enabled:false});assert.equal(s.hint,'');assert.deepEqual(s.point,[100,1]);
for(const scale of [.2,1,5]){s=G.smartSnap([100+7*scale,0],[a],{tolerance:8*scale});assert.match(s.hint,/Endpoint/);}
const movedWall=G.moveWalls([a,b],['a'],[10,20]);assert.deepEqual(movedWall[0].points,[[10,20],[110,20]]);assert.deepEqual(movedWall[1].points[1],[110,20]);
const roundtrip=JSON.parse(JSON.stringify(G.mergeWalls([...fs,branch],['a','b'],'chain').features));assert.equal(G.members(roundtrip,'branch',0).length,2);assert.deepEqual(G.hosted(roundtrip),roundtrip);
console.log('Passed wall merge/reversal/openings/T anchors/chain/rejections, box selection, move, guide targets/zoom/override and serialization.');
// Unrelated movements must not reintroduce boundaries into another merged wall.
const mergedT=G.mergeWalls([...fs,branch,wall('elsewhere',[0,200],[100,200])],['a','b'],'chain').features;
let unrelated=G.moveWalls(mergedT,['elsewhere'],[10,0]);assert.deepEqual(unrelated.find(w=>w.id==='a'),mergedT.find(w=>w.id==='a'));assert.equal(unrelated.length,mergedT.length);
assert.throws(()=>G.checkOpening(mergedT,mergedT.find(w=>w.id==='door'),90,30),/branch/);
assert.equal(G.openingRange(mergedT,mergedT.find(w=>w.id==='door')).min,100);
const ah=wall('ah',[0,0],[300,300]),ao={...door,id:'ao',host_wall_id:'ah',offset:40,width:30},target=wall('target',[100,0],[100,-50]);
let os=G.snapOpening([ah,ao,target],'ao',139,{enabled:true,tolerance:8});assert.ok(os.hint);assert.ok(Math.abs(os.point[0]-os.point[1])<1e-9);assert.equal(os.target,undefined);assert.ok(os.offset>=0&&os.offset+ao.width<=G.dist(...ah.points));
os=G.snapOpening([ah,ao,target],'ao',139,{enabled:false,tolerance:8});assert.equal(os.offset,139);assert.equal(os.hint,'');
