const assert=require('node:assert/strict'),G=require('../static/trace-geometry.js');
const wall=(id,points,junction_ids,extra={})=>({id,kind:'wall',points,thickness:8,height_m:2.8,junction_ids,...extra});
const fixture=()=>[wall('cap',[[0,0],[30,0]],['a','b'],{junction_nodes:[{id:'t',point:[28.4,0]}],wall_chain_id:'group',review_note:'Keep this evidence'}),wall('branch',[[28.4,0],[28.4,100]],['t','c'],{thickness:4}),{id:'window',kind:'window',host_wall_id:'cap',offset:10,width:5,points:[[10,0],[15,0]],sill_m:.9,head_m:2.4,frame_thickness:2,thickness:2}];
for(const reverse of [false,true]){
 const before=fixture(),target=reverse?{wall:'cap',index:1,point:[30,0]}:{wall:'branch',index:0,point:[28.4,0]};
 const out=G.connectEndpoint(before,'cap',reverse?2:1,target,'join');
 assert.equal(out.length,before.length);assert.equal(out[0].junction_nodes.length,0);assert.equal(G.members(out,'cap',1).length,2);assert.equal(out[0].wall_chain_id,'group');assert.equal(out[0].review_note,before[0].review_note);assert.deepEqual(out[2],before[2]);
 const moved=G.moveEndpoint(out,'cap',1,[35,6]);assert.deepEqual(moved[0].points[1],moved[1].points[0]);
 const reopened=JSON.parse(JSON.stringify(out));assert.equal(G.members(reopened,'cap',1).length,2);assert.deepEqual(before,fixture(),'input untouched for undo');assert.deepEqual(JSON.parse(JSON.stringify(before)),fixture());
 const again=G.connectEndpoint(out,'cap',1,{wall:'branch',index:0,point:out[1].points[0]},'again');assert.deepEqual(again,out,'repeat join is idempotent');
}
const a=fixture();a[0].points=[[-1.6,0],[30,0]];a[0].junction_nodes=[{id:'t',point:[0,0]}];a[1].points[0]=[0,0];a[2].points=[[8.4,0],[13.4,0]];
const trimmed=G.connectEndpoint(a,'cap',0,{wall:'branch',index:0,point:[0,0]},'a-join');assert.equal(trimmed[2].offset,8.4);assert.deepEqual(trimmed[2].points,a[2].points,'A-end trim preserves opening world position');
const invalid=fixture();invalid[2].offset=28.5;invalid[2].width=1;assert.throws(()=>G.connectEndpoint(invalid,'cap',1,{wall:'branch',index:0,point:[28.4,0]},'bad'),/fit between/);
const target=G.junctionTarget([28.4,0],fixture(),.1,[{id:'branch',index:0}]);assert.equal(target.index,2,'retained branch is targetable');
const ordinary=[wall('h',[[0,0],[10,0]],['a','b']),wall('v',[[10,1],[10,20]],['c','d'])];
const joined=G.connectEndpoint(ordinary,'h',1,{wall:'v',index:0,point:[10,1]},'l');assert.equal(G.members(joined,'h',1).length,2);assert.deepEqual(ordinary[0].points[1],[10,0],'no implicit nearby joins');
console.log('Branch/end joins: both directions, shared movement, A-end opening position, invalid opening bounds, target discovery, persistence and repeat joins passed.');

// Construction: all coincident contact ends join, without collecting a near gap
// or a deliberately detached wall at the same position.
let contact=[wall('h',[[-20,0],[0,0]],['ha','hb']),wall('v',[[0,0],[0,20]],['va','vb']),wall('new',[[-10,-10],[0,0]],['na','nb']),wall('gap',[[.1,0],[20,0]],['ga','gb']),wall('detached',[[0,0],[10,-10]],['j:detached:keep','db'])];
contact=G.connectEndpoint(contact,'new',1,{wall:'h',index:1,point:[0,0]},'build');assert.equal(G.members(contact,'new',1).length,3);assert.equal(G.members(contact,'gap',0).length,1);assert.equal(G.members(contact,'detached',0).length,1);
let cross=[wall('h',[[-20,0],[20,0]],['ha','hb']),wall('v',[[0,-20],[0,20]],['va','vb'],{thickness:4}),wall('new',[[-15,-15],[0,0]],['na','nb'])];
const targetCross=G.smartSnap([0,0],cross,{tolerance:1,exclude:[{id:'new',index:0},{id:'new',index:1}]}).target;
cross=G.connectEndpoint(cross,'new',1,targetCross,'cross');assert.equal(G.members(cross,'new',1).length,5);assert.equal(cross.length,5);assert(cross.filter(w=>w.split_root==='v').every(w=>w.thickness===4));
const detached=G.detachEndpoint(fixture(),'cap',2,'branch');assert.equal(G.members(detached,'branch',0).length,1);assert.equal(detached.filter(w=>w.kind==='wall'&&w.junction_ids.includes('j:detached:branch')).length,2);assert.deepEqual(G.hosted(detached).find(o=>o.id==='window').points,fixture()[2].points);
console.log('Construction: coincident L/T contacts, crossing splits, unequal thickness, deliberate gaps/detach and branch detachment passed.');
