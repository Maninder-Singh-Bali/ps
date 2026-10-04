const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
(async()=>{
const listeners={},nodes=new Map();const node=id=>{if(!nodes.has(id))nodes.set(id,{style:{},clientWidth:900,clientHeight:700,querySelector(){return null},after(){},setAttribute(){},addEventListener(){}});return nodes.get(id);};
let attempts=0,mode='2d',viewer=null,release=null,messages=[];
const d={id:'test',calibration:{metres_per_pixel:1},features:[],surface_design:{surfaces:[],items:[]}};
const ctx=vm.createContext({window:{},document:{body:{classList:{add(){},remove(){}}},querySelector:node,addEventListener(k,f){listeners[k]=f}},SurfaceDesignGeometry:require('../static/surface-design-geometry.js'),TraceGeometry:{},localStorage:{setItem(){}},crypto:{}});
vm.runInContext(fs.readFileSync(require.resolve('../static/surface-design.js'),'utf8'),ctx);ctx.window.SurfaceDesign.install({doc:()=>d,svg:node('svg'),viewer:()=>viewer,is3d:()=>mode==='3d',mode:async()=>{attempts++;if(release===false)await new Promise(r=>release=r)},toast:m=>messages.push(m)});
const click=action=>listeners.click({target:{closest:()=>({dataset:{designAction:action}})},stopImmediatePropagation(){}}),flush=()=>new Promise(setImmediate);
click('cutaway');await flush();assert.equal(attempts,1);assert(messages.at(-1).includes('unavailable'));
release=false;click('cutaway');await flush();click('cutaway');await flush();assert.equal(attempts,2);release();await flush();assert.equal(messages.length,2);
let draws=0;viewer={view:{cutaway:false},draw(){draws++}};mode='3d';click('cutaway');await flush();assert.equal(viewer.view.cutaway,true);assert.equal(draws,1);assert.equal(attempts,2);
click('cutaway');await flush();assert.equal(viewer.view.cutaway,false);assert.equal(draws,2);
console.log('Surface appearance: one failed attempt, duplicate-click guard, recovery and on/off passed');
})();
