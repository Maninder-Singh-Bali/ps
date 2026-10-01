const assert=require('node:assert/strict');
const {generationProgressModel:model}=require('../static/generation-progress.js');
const {generatedRoomResults:results,roomPreviewResult:preview}=require('../static/room-results.js');
const job={status:'running',kind:'image',created:100,progress_scope:'sampling',progress:50,steps:[2,4],eta:{seconds:8,at:110,scope:'sampling'}};
for(const kind of ['analysis','plan_setup','vision_study']){
 const m=model({kind,status:'completed',stage:'Suggestions ready',created:100,finished:101},null,102);
 assert.equal(m.ready,true);assert.equal(m.stage,'Suggestions ready');
}
assert.equal(model(job,null,111).percent,50);
assert.equal(model(job,null,200).percent,50); // time must never move the bar
assert.match(model(job,null,111).remaining,/7s of rendering left/);
assert.match(model(job,null,200).remaining,/recalculating/); // no bogus zero seconds
assert.equal(model({...job,progress:null,eta:null},null,112).percent,null);
assert.equal(model({...job,status:'waiting'},null,112).percent,50);
assert.match(model({...job,status:'waiting'},null,112).remaining,/when rendering starts/);
assert.equal(model({...job,progress:100,eta:null},null,115).ready,false);
assert.equal(model({...job,status:'completed',progress:100},null,115).ready,false);
assert.equal(model({...job,status:'completed',finished:115},{url:'/media/result'},200).elapsed,15);
assert.equal(model({...job,status:'completed'},{url:'/media/result'},115).ready,true);
assert.equal(model({...job,status:'failed'},null,115).remaining,'Remaining time: —');
const room={id:'a',revision:2,anchor_id:'anchor',images:['out','old','foreign'],reference_candidates:['product','environment']};
const assets={anchor:{id:'anchor',created:50},out:{id:'out',room_id:'a',created:110,kind:'image',job_id:'j',input_revision:2},old:{id:'old',room_id:'a',created:100,kind:'image',imported:true},foreign:{id:'foreign',room_id:'b',created:150,kind:'image',job_id:'j',input_revision:2},product:{id:'product',room_id:'a',created:200,kind:'reference_candidate',reference_purpose:'product',input_revision:2},environment:{id:'environment',room_id:'a',created:90,kind:'reference_candidate',reference_purpose:'environment',input_revision:2}};
const jobs={j:{status:'completed'}};
assert.deepEqual(results(room,assets,jobs).map(a=>a.id),['product','out','environment']);
assert.equal(preview(room,assets,jobs).id,'out'); // product never replaces the room
assert.equal(room.anchor_id,'anchor'); // preview does not alter references or approval
assert.equal(preview({...room,revision:3},assets,jobs),null);
assert.equal(preview(room,{...assets,out:{...assets.out,status:'rejected'}},jobs).id,'environment');
assert.equal(preview(room,assets,{j:{status:'running'}}).id,'environment');
assert.equal(preview(room,{...assets,anchor:{created:300}},jobs),null);
console.log('21 progress, ETA and automatic room preview checks passed');

assert.equal(model({...job,started:105,status:'completed',finished:115},{url:'/media/result'},200).renderElapsed,10);

assert.equal(model({...job,status:'completed'},{url:'/media/result',status:'rejected'}).stage,'Image needs revision');
