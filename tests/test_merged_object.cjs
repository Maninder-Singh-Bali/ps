const assert=require('node:assert/strict'),G=require('../static/trace-geometry.js');
const w=(id,points,extras={})=>({id,kind:'wall',points,thickness:16,height_m:2.5,review_note:'keep',corner_radius:2,...extras});
const a=w('a',[[100,100],[300,100]]),b=w('b',[[300,100],[300,350]]),o={id:'door',kind:'door',host_wall_id:'b',offset:70,width:80,thickness:16,points:[[300,170],[300,250]],head_m:2.2,sill_m:0,hinge_end:true,flip:true,review_note:'opening'};
const fs=G.hosted([a,b,o]),merged=G.mergeChain(fs,['a','b'],'merge-1').features;
assert.deepEqual(merged.map(f=>f.points),fs.map(f=>f.points));assert.equal(merged.length,fs.length);assert.deepEqual(G.chainMembers(merged,'a'),['a','b']);assert.deepEqual(G.chainMembers(merged,'b'),['a','b']);
const moved=G.moveObject(merged,['b'],[40,30]);for(const f of fs){const now=moved.find(x=>x.id===f.id);assert.deepEqual(now.points,f.points.map(p=>[p[0]+40,p[1]+30]));for(const k of ['thickness','height_m','corner_radius','width','offset','head_m','sill_m','hinge_end','flip','review_note'])assert.equal(now[k],f[k]);}
assert.deepEqual(G.members(moved,'a',1).map(m=>m.point),[[340,130],[340,130]]);
const edited=G.moveEndpoint(merged,'a',1,[320,130]);assert.deepEqual(G.chainMembers(edited,'b'),['a','b']);assert.deepEqual(edited[0].points[1],edited[1].points[0]);
const outside=w('external',[[100,100],[100,0]],{thickness:24}),connected=[...merged,outside];assert.equal(G.externalConnections(connected,['a','b']).length,1);assert.throws(()=>G.moveObject(connected,['b'],[50,0]),/outside/);assert.deepEqual(connected.at(-1),outside);
const detached=G.detachOutside(connected,['a','b'],'detach');assert.deepEqual(detached.map(f=>f.points),connected.map(f=>f.points));assert.equal(G.externalConnections(detached,['a','b']).length,0);assert.equal(G.members(detached,'a',1).length,2);const translated=G.moveObject(detached,['a'],[50,0]);assert.deepEqual(translated.at(-1).points,outside.points);
const separate=G.unmergeChain(merged,'merge-1');assert.deepEqual(G.chainMembers(separate,'a'),['a']);assert.equal(G.members(separate,'a',1).length,2);assert.deepEqual(separate.map(f=>f.points),merged.map(f=>f.points));
assert.deepEqual(G.chainMembers(fs,'a'),['a']); // Joined does not mean merged.
const reloaded=JSON.parse(JSON.stringify(moved));assert.deepEqual(G.chainMembers(reloaded,'b'),['a','b']);assert.deepEqual(G.moveObject(reloaded,['a'],[-40,-30]),merged);
const straight=G.mergeChain([w('s1',[[0,0],[100,0]]),w('s2',[[200,0],[100,0]])],['s1','s2'],'straight').features;assert.equal(straight.length,2);assert.deepEqual(straight[1].points,[[200,0],[100,0]]);
console.log('Passed persistent object selection, rigid L translation, openings/properties, segment editing, external connection blocking/detach, unmerge, save/reopen and joined-only independence.');
// Grouping does not collapse segments: differing source evidence/properties are
// retained verbatim, including a reversed member and its attached opening.
const documented=[w('p',[[0,0],[100,0]],{evidence:{source_ids:['pdf-a']},review_note:'measured'}),w('q',[[200,0],[100,0]],{evidence:{source_ids:['pdf-b']},review_note:'assumed',thickness:20,height_m:2.8,material:'brick'}),{...o,id:'win',kind:'window',hinge_end:false,host_wall_id:'q',offset:20,width:30,points:[[180,0],[150,0]],sill_m:.8,head_m:2}];
const documentedBefore=G.copy(documented),group=G.mergeChain(documented,['p','q'],'documented').features;
assert.deepEqual(documented,documentedBefore);
for(const f of group){const original=documented.find(x=>x.id===f.id),retained={...f};delete retained.wall_chain_id;delete retained.junction_ids;assert.deepEqual(retained,original);}
assert.deepEqual(G.hosted(group).find(f=>f.id==='win').points,documented[2].points);
assert.deepEqual(G.unmergeChain(group,'documented'),G.junctions(documented));
assert.deepEqual(G.chainMembers(JSON.parse(JSON.stringify(group)),'q'),['p','q']);
const tbranch=w('t',[[100,0],[100,70]]),withBranch=G.mergeChain([...documented,tbranch],['p','q'],'documented').features;
assert.deepEqual(withBranch.at(-1),tbranch);assert.equal(G.members(withBranch,'t',0).length,3);
assert.throws(()=>G.moveObject(withBranch,['p'],[10,0]),/outside/);
assert.throws(()=>G.mergeChain([w('a',[[0,0],[100,0]]),w('b',[[101,0],[200,0]])],['a','b'],'gap'),/disconnected/);
assert.throws(()=>G.mergeChain([w('a',[[0,0],[100,0]]),w('b',[[0,5],[100,5]])],['a','b'],'parallel'),/disconnected/);
assert.throws(()=>G.mergeChain([w('a',[[0,0],[100,0]]),w('b',[[100,0],[50,0]])],['a','b'],'duplicate'),/overlapping/);
assert.throws(()=>G.mergeChain(G.detachEndpoint(documented,'q',1,'intentional'),['p','q'],'detached'),/disconnected/);
// Low-level consolidation still refuses incompatible properties/data loss.
assert.throws(()=>G.mergeWalls(documented,['p','q'],'consolidate'),/different/);
console.log('Passed distinct evidence/notes/properties grouping, reversed opening preservation, T branch, disconnected/detached/overlap guards and strict consolidation.');
