const assert=require('node:assert/strict'),G=require('../static/trace-geometry.js');
let cases=0;
for(const end of [[600,0],[0,600],[360,480],[-360,-480]])for(const kind of ['door','window']){
 const w={id:'w',kind:'wall',points:[[0,0],end],thickness:15},o={id:'o',kind,host_wall_id:'w',offset:100,width:70,head_m:2.3,sill_m:kind==='window'?.85:0,hinge_end:true,flip:true,review_note:'keep',points:[[0,0],[1,0]],thickness:15},other={...o,id:'other',offset:330,width:100},fs=G.hosted([w,o,other]);
 const range=G.openingRange(fs,fs[1]);assert.deepEqual(range,{min:0,max:260});
 const moved=G.slideOpening(fs,'o',180,range);assert.equal(moved[1].offset,180);assert.equal(G.project(moved[1].points[1],w).t,180);
 for(const key of ['width','head_m','sill_m','hinge_end','flip','host_wall_id','review_note'])assert.deepEqual(moved[1][key],o[key]);
 assert.deepEqual(moved[0],fs[0]);assert.deepEqual(moved[2],fs[2]);assert.equal(fs[1].offset,100);
 assert.equal(G.slideOpening(fs,'o',1000,range)[1].offset,260); // cannot leap through neighbour
 assert.equal(G.slideOpening(fs,'o',-1000,range)[1].offset,0);
 assert.equal(G.openingRange(fs,fs[2]).min,170);assert.equal(G.slideOpening(fs,'other',1000)[2].offset,500);
 assert.throws(()=>G.checkOpening(fs,o,-1),/ends/);assert.throws(()=>G.checkOpening(fs,o,550),/ends/);assert.throws(()=>G.checkOpening(fs,o,300),/overlap/);assert.throws(()=>G.checkOpening(fs,o,100,250),/overlap/);
 G.checkOpening(fs,o,260);G.checkOpening(fs,o,430); // numeric relocation to a clear interval is explicit
 assert.deepEqual(G.hosted(JSON.parse(JSON.stringify(moved))),moved);cases++;
}
const w={id:'w',kind:'wall',points:[[0,0],[600,0]],thickness:15},a={id:'a',kind:'door',host_wall_id:'w',offset:100,width:70,points:[[100,0],[170,0]]},legacy={id:'legacy',kind:'window',points:[[300,0],[400,0]],thickness:15};
assert.equal(G.openingRange([w,a,legacy],a).max,230);assert.throws(()=>G.checkOpening([w,a,legacy],a,250),/overlap/);
assert.throws(()=>G.openingRange([w,legacy],legacy),/Attach/);
console.log(`Passed ${cases} door/window direction cases; bounds, overlap corridor, metadata preservation, legacy protection and roundtrip.`);
