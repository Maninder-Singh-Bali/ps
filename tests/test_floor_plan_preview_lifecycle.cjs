// Exercise the actual editor transition function with an instrumented renderer.
// Real WebGL rendering is separately verified in the Mac browser.
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync(require.resolve('../static/floor-plan.js'),'utf8');
const body=source.slice(source.indexOf('async function setMode(next)'),source.indexOf('async function save()'));
const nodes=new Map(),node=s=>{if(!nodes.has(s))nodes.set(s,{hidden:s==='#model',dataset:{},setAttribute(k,v){this[k]=v;},removeAttribute(k){delete this[k];}});return nodes.get(s);};
let created=0,disposed=0,queue=[],messages=[];
class Viewer{constructor(canvas,view){assert(!canvas.lost,'cannot reuse a destroyed drawing context');this.canvas=canvas;this.view=view;created++;}update(faces){this.faces=faces;}dispose(){disposed++;this.canvas.lost=true;}}
const c=vm.createContext({window:{},modelAppearance:()=>({}),previewPolicy:()=>({available:true,editable:true}),doc:{id:'draft',features:[]},mode:'2d',viewer:null,viewerDraftId:null,previewSerial:0,changeSerial:0,attachment:null,elevationGuide:null,elevationWall:null,planView:null,view:[0,0,10,10],$:node,clearGuides(){},toast:m=>messages.push(m),status(){},draw(){},fitElevation(){c.view=[-5,-5,5,5];},inspector(){},hostForSelection:()=>({id:'wall'}),mpp:()=>.01,G:{issues:()=>[]},BlockModelViewer:{Viewer,defaults:()=>({zoom:1,yaw:0,pan:[0,0]})},api:()=>new Promise((resolve,reject)=>queue.push({resolve,reject}))});
vm.runInContext('function snapshot(){return JSON.parse(JSON.stringify(doc));}'+body,c);
const scene=id=>({geometry_hash:id,wall_footprints:{hash:id},surfaces:[{kind:'wall',color:[10,20,30],points:[[0,0,0],[1,0,0],[1,0,1]]}]});
(async()=>{
 let p=c.setMode('3d');queue.shift().resolve(scene('one'));await p;const first=c.viewer;first.view.zoom=3;first.view.yaw=.4;
 c.changeSerial++;p=c.setMode('3d');queue.shift().resolve(scene('two'));await p;assert.equal(c.viewer,first);assert.equal(created,1);assert.equal(disposed,0);assert.equal(first.view.zoom,3);assert.equal(first.view.yaw,.4);
 for(const mode of ['2d','elevation','2d']){await c.setMode(mode);p=c.setMode('3d');queue.shift().resolve(scene(mode));await p;assert.equal(c.viewer,first);assert.equal(disposed,0);assert.equal(first.view.zoom,3);assert.deepEqual(Array.from(c.view),[0,0,10,10]);}
 // A failed request retains the last rendered scene and camera.
 const old=first.faces;p=c.setMode('3d');queue.shift().reject(Error('preview unavailable'));await p;assert.equal(first.faces,old);assert.equal(c.mode,'3d');assert.equal(first.view.zoom,3);assert(messages.includes('preview unavailable'));
 // Late request cannot overwrite a newer response or a switch back to 2D.
 let older=c.setMode('3d'),oldJob=queue.shift(),newer=c.setMode('3d'),newJob=queue.shift();newJob.resolve(scene('new'));await newer;oldJob.resolve(scene('old'));await older;assert.equal(node('#model').dataset.geometryHash,'new');
 p=c.setMode('3d');const obsolete=queue.shift();await c.setMode('2d');obsolete.resolve(scene('obsolete'));await p;assert.equal(c.mode,'2d');assert.equal(node('#model').hidden,true);
 // Editing while entry to 3D is pending fetches the current document once.
 p=c.setMode('3d');const changed=queue.shift();c.changeSerial++;changed.resolve(scene('stale-edit'));await new Promise(setImmediate);assert.equal(queue.length,1);queue.shift().resolve(scene('latest-edit'));await p;assert.equal(node('#model').dataset.geometryHash,'latest-edit');
 c.doc={id:'different-draft',features:[]};p=c.setMode('3d');queue.shift().resolve(scene('different'));await p;assert.equal(c.viewer,first);assert.equal(first.view.zoom,1);assert.equal(created,1);assert.equal(disposed,0);
 console.log('Floor-plan 3D lifecycle: reuse, camera preservation, mode switches, failure retention, latest request/edit wins and new-draft reset passed.');
})().catch(e=>{console.error(e);process.exitCode=1;});
