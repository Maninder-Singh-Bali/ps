const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync(require.resolve('../static/furniture-blocks.js'),'utf8');
const helpers=source.slice(source.indexOf(' function savedSource(){'),source.indexOf(' function historySnapshot(){'));
function fixture(){
 const pending=[],doc=n=>({revision:n,map_revision:n,features:[{id:'wall',points:[[0,0],[n*100,0]]}],edits:{},site:{}});
 const asset={drawing:doc(1),manual_document:{revision:1}};
 const r={id:'room',plan_id:'plan',revision:1,block_layout:{items:[{id:'sofa',x:5}]}};
 const node={hidden:true,textContent:'',append(){}};
 const c=vm.createContext({structuredClone,JSON,modalType:'blocks',busy:false,drag:null,groupDrag:null,panDrag:null,placement:null,dirty:false,history:{past:['old']},multi:new Set(),selected:'sofa',popupOpen:true,
  ctx:{pid:'project',rid:'room',ready:true,drawing:doc(1),view:[10,20,300,400],drafts:{},revision:1},
  items:structuredClone(r.block_layout.items),issues:[],state:{projects:{project:{map_revision:1}}},
  modelView:{zoom:3},plan:()=>asset,room:()=>r,
  walls:{doc:doc(1),dirty:false,saved(d){this.doc=d;this.dirty=false},snapshot(){return structuredClone(this.doc)},clear(){}},
  document:{activeElement:{tagName:'BODY'},createElement:()=>({})},$:()=>node,
  pendingChanges:()=>c.dirty||c.walls.dirty,
  render:()=>{c.renders=(c.renders||0)+1},
  api:(path,payload)=>new Promise((resolve,reject)=>pending.push({path,payload,resolve,reject}))});
 vm.runInContext(helpers,c);c.ctx.savedSource=c.savedSource();
 function update(n=2){asset.drawing=doc(n);asset.manual_document.revision=n;c.state.projects.project.map_revision=n;r.revision=n;}
 const result=n=>({revision:n,items:structuredClone(r.block_layout.items),issues:[],preview_scene:{wallLength:n*100},preview_floors:[{scene:{wallLength:n*100}}]});
 const flush=()=>new Promise(resolve=>setImmediate(resolve));
 async function complete(p,n=2){pending.shift().resolve(doc(n));await flush();pending.shift().resolve(result(n));await flush();pending.shift().resolve(doc(n));await p;}
 return {c,pending,doc,update,result,flush,complete,node};
}
(async()=>{
 {const f=fixture();await f.c.syncSaved();assert.equal(f.pending.length,0);f.update();const p=f.c.syncSaved();await f.complete(p);assert.equal(f.c.walls.doc.features[0].points[1][0],200);assert.equal(f.c.ctx.scene.wallLength,200);assert.equal(f.c.ctx.revision,2);assert.equal(f.c.items[0].x,5);assert.equal(f.c.selected,'sofa');assert.deepEqual(f.c.ctx.view,[10,20,300,400]);assert.equal(f.c.modelView.zoom,3);assert.equal(f.c.history,null);await f.c.syncSaved();assert.equal(f.pending.length,0);}
 {const f=fixture();f.update();f.c.dirty=true;f.c.items[0].x=99;await f.c.syncSaved();assert.equal(f.pending.length,0);assert.match(f.node.textContent,/unsaved/);assert.equal(f.c.items[0].x,99);assert.equal(f.c.ctx.revision,1);}
 for(const key of ['drag','groupDrag','panDrag','placement','busy']){const f=fixture();f.update();f.c[key]=true;await f.c.syncSaved();assert.equal(f.pending.length,0);}
 {const f=fixture();f.update();const p=f.c.syncSaved();await f.c.syncSaved();assert.equal(f.pending.length,1);f.c.dirty=true;f.c.items[0].x=99;f.pending.shift().resolve(f.doc(2));await p;assert.equal(f.c.items[0].x,99);assert.equal(f.c.ctx.revision,1);}
 {const f=fixture();f.update();const p=f.c.syncSaved();f.pending.shift().resolve(f.doc(2));await f.flush();f.update(3);f.pending.shift().resolve(f.result(2));await p;assert.equal(f.c.renders,undefined);const next=f.c.syncSaved();await f.complete(next,3);assert.equal(f.c.ctx.scene.wallLength,300);}
 {const f=fixture();f.update();const p=f.c.syncSaved();f.pending.shift().resolve(f.doc(2));await f.flush();f.pending.shift().resolve(f.result(2));await f.flush();f.pending.shift().resolve(f.doc(3));await p;assert.equal(f.c.renders,undefined);assert.equal(f.c.walls.doc.revision,1);}
 for(const change of [c=>c.ctx=null,c=>c.ctx.rid='other',c=>c.modalType='camera']){const f=fixture();f.update();const p=f.c.syncSaved();change(f.c);f.pending.shift().resolve(f.doc(2));await p;assert.equal(f.c.renders,undefined);}
 {const f=fixture();f.update();const p=f.c.syncSaved();f.pending.shift().reject(Error('offline'));await p;assert.equal(f.c.walls.doc.revision,1);assert.match(f.node.textContent,/Could not refresh/);assert.equal(f.c.ctx.syncing,false);const retry=f.c.syncSaved();await f.complete(retry);assert.equal(f.c.ctx.revision,2);}
 assert(source.includes("ctx.ready&&savedSource()!==ctx.savedSource"));
 console.log('Furnish saved-plan sync: coherent 2D/3D, preserved room/view/items, idempotency, dirty/gesture protection, latest-save races, navigation/disposal and retry passed.');
})().catch(e=>{console.error(e);process.exitCode=1});
