const assert=require('node:assert/strict'),G=require('../static/trace-geometry'),O=require('../static/opening-editor');
const wall=(id,a,b,t=20)=>({id,kind:'wall',points:[a,b],thickness:t,height_m:3,review_note:'retain'}),opening=(a,b)=>({id:'o',kind:'window',points:[a,b],thickness:10,sill_m:.7,head_m:2.1,flip:true,review_note:'source'}),eq=(a,b)=>assert.ok(G.dist(a,b)<1e-8);
for(const end of [[200,0],[0,200],[120,160]])for(const reverse of [false,true]){
 const u=end.map(v=>v/200),n=[-u[1],u[0]],at=t=>u.map((v,i)=>v*t+n[i]*-5),w=wall('w',[0,0],end),o=opening(at(40),at(70));if(reverse)o.points.reverse();const fs=[w,o],before=JSON.stringify(fs),p=O.attachmentProposal(fs,'o','w');assert.equal(JSON.stringify(fs),before);assert.equal(p.extended,false);const q=p.features[1];q.points.forEach((v,i)=>eq(v,o.points[i]));assert.equal(q.thickness,10);assert.ok(Math.abs(q.normal_offset+5)<1e-8);for(const k of ['sill_m','head_m','flip','review_note'])assert.equal(q[k],o[k]);
 const moved=O.edit(p.features,'o',{offset:50,height:1.2},'left',3);assert.equal(O.levels(moved[1]).base,.7);assert.equal(moved[1].thickness,10);assert.deepEqual(G.hosted(JSON.parse(JSON.stringify(p.features))),p.features);
 const split=G.split(p.features,'w',100,'w2');split.find(f=>f.id==='o').points.forEach((v,i)=>eq(v,o.points[i]));
}
const fs=[wall('w',[100,0],[300,0]),opening([50,-5],[100,-5]),wall('branch',[100,0],[100,100])],p=O.attachmentProposal(fs,'o','w');assert.equal(p.extension,50);assert.equal(p.features.length,fs.length);assert.equal(p.features.find(f=>f.id==='w').junction_nodes.length,1);assert.deepEqual(p.features.find(f=>f.id==='branch'),fs[2]);assert.throws(()=>O.edit(p.features,'o',{offset:5}),/branch/);
assert.throws(()=>O.attachmentProposal([wall('w',[101,0],[300,0]),fs[1]],'o','w'),/gap/);
assert.throws(()=>O.attachmentProposal([fs[0],opening([50,-6],[100,-6])],'o','w'),/outside/);
assert.throws(()=>O.attachmentProposal([fs[0],opening([50,-5],[100,0])],'o','w'),/parallel/);
const hostWithPeer=[wall('w',[100,0],[300,0]),opening([50,-5],[100,-5]),{id:'peer',kind:'door',host_wall_id:'w',offset:100,width:20,points:[[200,0],[220,0]],thickness:20,head_m:2,flip:true}];const extendedPeer=O.attachmentProposal(hostWithPeer,'o','w').features.find(f=>f.id==='peer');assert.deepEqual(extendedPeer.points,hostWithPeer[2].points);assert.equal(extendedPeer.offset,150);assert.equal(extendedPeer.flip,true);
const ambiguous=[wall('l',[0,0],[50,0]),wall('r',[100,0],[200,0]),opening([50,0],[100,0])];assert.equal(O.attachmentCandidates(ambiguous,'o').candidates.length,2);
const occupied=O.attach([wall('w',[0,0],[300,0]),opening([50,0],[100,0])],'o','w');assert.throws(()=>O.attach([...occupied,{...opening([75,0],[150,0]),id:'q'}],'q','w'),/overlap/);
// Reversed host merge preserves signed frame offset as well as hinge direction.
const mergedFs=O.attach([wall('a',[0,0],[100,0]),wall('b',[200,0],[100,0]),opening([150,5],[180,5])],'o','b');const merged=G.mergeWalls(mergedFs,['a','b'],'combined',3);const result=merged.features||merged;result.find(f=>f.id==='o').points.forEach((v,i)=>eq(v,mergedFs[2].points[i]));
console.log('Attachment geometry: pose/depth/metadata, 3 orientations, reverse hinges, extension, branches, gap/overlap guards, ambiguity, merge and roundtrip passed.');
