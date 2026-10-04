const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync(require.resolve('../static/floor-plan.js'),'utf8');
const body=source.slice(source.indexOf('function flushFocusedValue(){'),source.indexOf("document.addEventListener('input'"));
function fixture(){
 const pending=[],nodes=new Map(),node=s=>{if(!nodes.has(s))nodes.set(s,{textContent:'',disabled:false});return nodes.get(s);};
 const doc=id=>({id,revision:1,features:[],name:id,calibration:{metres_per_pixel:.01}});
 const c=vm.createContext({doc:doc('A'),dirty:true,changeSerial:1,saveTicket:0,navigationSerial:0,openTicket:0,savingKey:null,previewSerial:0,attachment:null,history:['edit'],future:[],selected:'a-wall',footprintKey:'',footprintResult:null,joinSource:null,snapTarget:null,startTarget:null,start:null,measure:[],typed:'',thickness:0,overlay:'corrected',document:{activeElement:null,querySelector:()=>null},location:{hash:'A'},clone:x=>JSON.parse(JSON.stringify(x)),$:node,esc:x=>x,confirm:()=>true,toast:m=>c.messages.push(m),messages:[],status(){node('#status').textContent=c.dirty?'Unsaved changes':'Saved';},clearGuides(){},clearSelection(){c.selected=null;},mpp:()=>.01,setMode:async()=>{},repairImportedOpenings(){},render(){},fit(){},requestAnimationFrame:fn=>fn(),api:(path,payload)=>path===''?Promise.resolve([]):new Promise((resolve,reject)=>pending.push({path,payload,resolve,reject}))});
 vm.runInContext(body,c);return {c,pending,doc,node};
}
(async()=>{
 for(const editB of [false,true]){
  const {c,pending,doc}=fixture();const save=c.save(),a=pending.shift();const opening=c.open('B');pending.shift().resolve(doc('B'));await opening;c.selected='b-wall';
  if(editB){c.doc.name='B edited';c.dirty=true;c.changeSerial++;}
  a.resolve({...doc('A'),revision:2});await save;assert.equal(c.doc.id,'B');assert.equal(c.doc.revision,1);assert.equal(c.selected,'b-wall');assert.equal(c.dirty,editB);assert.equal(c.doc.name,editB?'B edited':'B');
 }
 {const {c,pending,doc}=fixture();const b=c.open('B'),reqB=pending.shift(),d=c.open('C'),reqC=pending.shift();reqC.resolve(doc('C'));await d;reqB.resolve(doc('B'));await b;assert.equal(c.doc.id,'C');assert.equal(c.location.hash,'C');}
 {const {c,pending,doc}=fixture();const p=c.save();c.doc.name='new edit';c.changeSerial++;pending.shift().resolve({...doc('A'),revision:2});await p;assert.equal(c.doc.name,'new edit');assert.equal(c.doc.revision,2);assert(c.dirty);assert.equal(c.selected,'a-wall');}
 {const {c,pending,node}=fixture();const p=c.save();pending.shift().reject(Error('disk unavailable'));await p;assert(c.dirty);assert.equal(c.doc.revision,1);assert.equal(node('#save').disabled,false);assert.equal(node('#status').textContent,'Save failed');}
 {const {c,pending,doc,node}=fixture();const p=c.save(),a=pending.shift(),b=c.open('B');pending.shift().resolve(doc('B'));await b;a.reject(Error('old error'));await p;assert.equal(c.doc.id,'B');assert(!c.messages.includes('old error'));assert.equal(node('#save').disabled,false);}
 {const {c,pending,doc}=fixture();const b=c.open('B');c.doc.name='edit while opening';c.changeSerial++;pending.shift().resolve(doc('B'));await b;assert.equal(c.doc.id,'A');assert.equal(c.doc.name,'edit while opening');}
 console.log('Save/open races: identity, navigation order, edits during save/open, failure, dirty/selection/revision preservation passed.');
})().catch(e=>{console.error(e);process.exitCode=1;});
