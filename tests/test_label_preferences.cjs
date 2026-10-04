const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync(require.resolve('../static/plan-labels.js'),'utf8'),store=new Map();
function load(){const c={window:{},localStorage:{getItem:k=>store.get(k)||null,setItem:(k,v)=>store.set(k,v)},document:{querySelectorAll:()=>[]}};vm.createContext(c);vm.runInContext(source,c);return c.window.PlanLabels;}
let labels=load();assert.equal(labels.objectsVisible,false);labels.setObjects(true);assert.equal(load().objectsVisible,true);labels.setObjects(false);assert.equal(load().objectsVisible,false);
store.set('pixeloid-all-object-labels','invalid JSON');assert.equal(load().objectsVisible,false);
console.log('Quiet initial labels, explicit preferences and corrupted-preference recovery passed.');
