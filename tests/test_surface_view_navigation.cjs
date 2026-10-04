// Real surface-editor event routing; no scene edits are needed to leave design mode.
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const nodes=new Map();function node(id){if(!nodes.has(id))nodes.set(id,{style:{},events:{},clientWidth:900,clientHeight:700,querySelector(){return null},remove(){},setAttribute(k,v){this[k]=v;},addEventListener(k,f){(this.events[k]||=[]).push(f);}});return nodes.get(id);}
const doc={id:'apartment',units:'m',calibration:{metres_per_pixel:.03},features:[],surface_design:{surfaces:[{id:'ceiling',kind:'ceiling',boundary:[[0,0],[100,0],[100,100],[0,100]],holes:[]}],items:[]}},before=JSON.stringify(doc);
let fits=0,commits=0,mode='2d';const context=vm.createContext({window:{},document:{body:{classList:{add(){},remove(){}}},querySelector:node,addEventListener(){}},SurfaceDesignGeometry:require('../static/surface-design-geometry.js'),TraceGeometry:{},crypto:{}});
vm.runInContext(fs.readFileSync(require.resolve('../static/surface-design.js'),'utf8'),context);const S=context.window.SurfaceDesign;
S.install({doc:()=>doc,svg:node('svg'),wall:()=>null,clearSelection(){},mode:m=>{mode=m;},is3d:()=>mode==='3d',render(){},fit(){fits++;},commit(){commits++;},toast:m=>{throw Error(m);}});
for(const from of ['2d','3d']){
 node('#design-open').onclick();assert(S.active());mode=from;
 let stopped=false;node('#view2').events.click[0]({stopImmediatePropagation(){stopped=true;}});
 assert(stopped);assert.equal(S.active(),true);S.close();assert.equal(mode,'2d');
}
assert.equal(fits,2);assert.equal(commits,0);assert.equal(JSON.stringify(doc),before);
console.log('Surface 3D → 2D retains surface mode; explicit Plan navigation exits without mutating geometry.');

// A selected wall face has two distinct 2D presentations. Switching must not edit it.
doc.features=[{id:'wall',kind:'wall',points:[[0,0],[100,0]],thickness:10}];doc.surface_design.surfaces=[{id:'face',kind:'wall',wall_id:'wall',side:-1}];
node('#design-open').onclick();const saved=JSON.stringify(doc);
for(const [id,pressed] of [['viewe','viewe'],['view2','view2'],['viewe','viewe'],['view3','view3'],['view2','view2']]){
 node('#'+id).events.click[0]({stopImmediatePropagation(){}});
 assert.equal(node('#'+pressed)['aria-pressed'],'true');
 for(const other of ['view2','viewe','view3'].filter(v=>v!==pressed))assert.equal(node('#'+other)['aria-pressed'],'false');
 assert.equal(JSON.stringify(doc),saved);
}
console.log('Selected wall: plan/elevation/3D indicators follow the displayed view without scene mutation.');
