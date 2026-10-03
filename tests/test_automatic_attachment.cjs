const assert=require('node:assert/strict'),G=require('../static/trace-geometry'),H=require('../static/opening-hosts'),O=require('../static/opening-editor');
const w=(id,a,b,t=20)=>({id,kind:'wall',points:[a,b],thickness:t,height_m:3});
const o=(id,kind,a,b,t=10)=>({id,kind,points:[a,b],thickness:t,...(kind==='window'?{sill_m:.7,head_m:2.1}:{base_m:0,head_m:2.2}),flip:true,evidence:{method:'source'}});
const eq=(a,b)=>assert.ok(G.dist(a,b)<1e-7);
for(const u of [[1,0],[0,1],[.6,.8]])for(const reverse of [false,true]){
 const at=(t,n=0)=>[u[0]*t-u[1]*n,u[1]*t+u[0]*n];
 let fs=[w('left',at(0),at(50)),w('right',at(200),at(140)),o('window','window',at(50,-5),at(90,-5)),o('door','door',at(140),at(90),20),w('perpendicular',at(50),at(50,90))];if(reverse)fs[0].points.reverse();
 const before=JSON.stringify(fs),r=H.repair(fs,3);assert.equal(JSON.stringify(fs),before);assert.equal(r.repaired.length,2);assert.equal(r.unresolved.length,0);const win=r.features.find(f=>f.id==='window'),door=r.features.find(f=>f.id==='door');assert.equal(win.host_wall_id,door.host_wall_id);assert.equal(r.features.filter(f=>f.kind==='wall').length,2);
 for(const q of [win,door]){const old=fs.find(f=>f.id===q.id);q.points.forEach((p,i)=>eq(p,old.points[i]));for(const k of ['thickness','sill_m','head_m','base_m','flip','evidence'])assert.deepEqual(q[k],old[k]);}
 assert.deepEqual(r.features.find(f=>f.id==='perpendicular'),fs[4]);assert.equal(r.features.find(f=>f.id===win.host_wall_id).junction_nodes.length,1);
 assert.deepEqual(H.repair(r.features,3).features,r.features);assert.deepEqual(G.hosted(JSON.parse(JSON.stringify(r.features))),r.features);
 // The shared window/door edge remains an overlap stop, not a wall through either aperture.
 assert.throws(()=>O.edit(r.features,'window',{width:100},'left',3),/overlap|branch|ends/);
}
const perp=[w('p',[50,0],[50,100]),o('window','window',[50,0],[100,0])];assert.equal(H.repair(perp).repaired.length,0);
const gap=[w('a',[0,0],[49,0]),o('window','window',[50,0],[100,0])];assert.equal(H.repair(gap).repaired.length,0);
const ambiguous=[w('a',[0,-2],[50,-2]),w('b',[0,2],[50,2]),o('window','window',[50,0],[100,0])];assert.equal(H.candidates(ambiguous,'window').candidates.length,2);assert.equal(H.repair(ambiguous).repaired.length,0);
const incompatible=[w('a',[0,0],[50,0]),{...w('b',[100,0],[150,0]),height_m:4},o('window','window',[50,0],[100,0])];assert.equal(H.candidates(incompatible,'window').candidates.length,2);
const merged=[{...w('a',[0,0],[50,0]),wall_chain_id:'group'}, {...w('b',[100,0],[150,0]),wall_chain_id:'group'},o('window','window',[50,0],[100,0])];assert.equal(H.repair(merged).repaired.length,0);assert.deepEqual(H.repair(merged).features,merged);
const containedGroup=[{...w('a',[0,0],[100,0]),wall_chain_id:'group'},{...w('b',[100,0],[200,0]),wall_chain_id:'group'},o('window','window',[20,0],[50,0])];const grouped=H.repair(containedGroup);assert.equal(grouped.repaired.length,1);assert.deepEqual(grouped.features.slice(0,2),containedGroup.slice(0,2));
const detached=[{...w('a',[0,0],[50,0]),junction_ids:['a','end1']},{...w('b',[50,0],[100,0]),junction_ids:['end2','b']},o('window','window',[100,0],[120,0])];assert.equal(H.repair(detached).repaired.length,0);
const full=[w('a',[0,0],[200,0]),{...o('window','window',[50,0],[100,0]),sill_m:0,head_m:3}];assert.equal(H.repair(full,3).features.find(f=>f.id==='window').sill_m,0);
console.log('Automatic host repair: adjacent door/window, split/reversed/angled runs, face offsets, external junction, metadata, gaps/perpendicular/ambiguity/property/group guards, full-height glazing, idempotence and roundtrip passed.');
