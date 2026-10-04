'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync(process.env.FURNITURE_SOURCE||'static/furniture-blocks.js','utf8');
const switchCode=source.slice(source.indexOf(' async function switchSection('),source.indexOf(' async function call('));
const callCode=source.slice(source.indexOf(' async function call('),source.indexOf(' let catalogueOpen='));
(async()=>{
 let release;const rooms=[{id:'a',plan_id:'p',bbox:[0,0,1,1],revision:1,block_layout:{items:[{id:'a1'}]}},{id:'b',plan_id:'p',bbox:[0,0,1,1],revision:1,block_layout:{items:[{id:'b1'}]}}];
 const context={ctx:{pid:'p',rid:'a',drafts:{}},roomSelectionSerial:0,busy:false,busyDone:Promise.resolve(),releaseBusy:()=>{},selected:'a1',items:[{id:'a1'}],issues:[],dirty:false,walls:{clear(){},payload(){}},multi:new Set(),modelView:{},history:null,structuredClone,JSON,Promise,room(){return rooms.find(r=>r.id===context.ctx.rid)},state:{projects:{p:{rooms}}},window:{},render(){context.renders.push([context.ctx.rid,context.selected])},renders:[],readContext:()=>({}),focusRoom(){},stashDraft(){context.ctx.drafts[context.ctx.rid]={items:structuredClone(context.items),selected:context.selected}},FurnitureLibrary:{consistentSofa:v=>v},plan:()=>({}),$:()=>null,saveStatus(){},savedSource(){},api:()=>new Promise(r=>release=r)};
 vm.createContext(context);vm.runInContext(switchCode+callCode,context);
 const first=context.switchSection('b','b1');assert.equal(context.busy,true);
 const second=context.switchSection('a','a1');
 release({items:[{id:'b1'}],issues:[],revision:1});const firstResult=await first;assert.equal(context.renders.filter(v=>v[0]==='b').length,1,'Old rebuild must not repaint the older room after a newer selection request');assert.equal(firstResult,false,'Superseded selection must not authorize a late continuation');
 await Promise.resolve();release({items:[{id:'a1'}],issues:[],revision:1});assert.equal(await second,true);
 assert.equal(context.ctx.rid,'a');assert.equal(context.selected,'a1');
 assert.equal(context.renders.filter(v=>v[0]==='b').length,1,'Old rebuild must not repaint the older room after a newer selection request');
 // A late response from a disposed/reopened editor cannot replace the new editor.
 const pending=context.call('check');context.ctx={pid:'p',rid:'b',drafts:{}};context.items=[{id:'new-item'}];release({items:[{id:'stale'}],issues:[],revision:1});await pending;
 assert.equal(context.items[0].id,'new-item');
 console.log('Queued room/object selection, late continuations, and disposed-editor responses passed.');
})().catch(e=>{console.error(e);process.exitCode=1});
