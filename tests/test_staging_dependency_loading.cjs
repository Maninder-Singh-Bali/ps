const assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
(async()=>{
 const d={id:'synthetic-floor-1',features:[],calibration:{},surface_design:{},wall_height_m:2.8};
 const seed={docs:{[d.id]:d},state:{projects:{'synthetic-ui':{rooms:[]}},assets:{}},scenes:{}};
 const pending=[],scripts=[],storage=new Map(),window={dispatchEvent(){},fetch:async()=>({ok:true,json:async()=>structuredClone(seed)})};
 const ctx=vm.createContext({window,URL,document:{currentScript:{src:'http://localhost/ps/app/ui-adapter.js'},createElement:()=>({remove(){}}),head:{append(el){scripts.push(String(el.src));pending.push(el);}}},location:{href:'http://localhost/ps/'},localStorage:{getItem:k=>storage.get(k),setItem:(k,v)=>storage.set(k,v)},structuredClone,Event,setTimeout,crypto:require('node:crypto').webcrypto,Response});
 vm.runInContext(fs.readFileSync('staging-preview/ui-adapter.js','utf8'),ctx);
 const flush=()=>new Promise(setImmediate),a=window.Staging.planApi('/resolve',{features:[]}),b=window.Staging.planApi('/resolve',{features:[]});
 await flush();assert.equal(scripts.length,1);assert(scripts[0].endsWith('polygon-clipping.js'));
 window.polygonClipping={};pending.shift().onload();await flush();assert.equal(scripts.length,2);assert(scripts[1].endsWith('joined-footprints.js'));
 window.StagingJoinedFootprints={resolve:()=>({joined:true})};pending.shift().onload();assert((await a).joined);assert((await b).joined);
 assert.equal(window.Staging.previewPolicy(d).available,true);assert.equal(window.Staging.previewPolicy(d).editable,false);
 assert.equal(window.Staging.previewPolicy({...d,features:[{id:'edit'}]}).available,false);
 assert.equal(scripts.length,2);console.log('Delayed dependencies load once, in order, before concurrent junction calls; static preview capability tracks edits.');
})().catch(e=>{console.error(e);process.exitCode=1;});
