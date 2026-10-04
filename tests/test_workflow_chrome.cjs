const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const src=fs.readFileSync(require.resolve('../static/app.js'),'utf8');
const fn=src.slice(src.indexOf('async function openWorkspaceStage('),src.indexOf("document.addEventListener('click',e=>{const b=e.target.closest('[data-workspace-stage]')"));
async function run({pending=false,active=false,stage='cameras'}={}){
 const calls=[],ctx={pid:'project',rid:'room',planId:'plan',tab:'images',pendingWorkspaceStage:null,workflowOpening:false,workflowNavigation:0,location:{},history:{replaceState(){}},encodeURIComponent,localStorage:{setItem(){}},toast:s=>calls.push('blocked'),A:()=>({manual_draft_id:'draft'}),P:()=>({}),renderShell:()=>calls.push('shell'),renderMain:()=>calls.push('main'),openCameraView:async()=>calls.push('camera'),openFurnitureBlocks:async()=>calls.push('furnish')};
 ctx.window={InlinePlan:{active:()=>active,mode:()=>'blocks',ready:async()=>calls.push('ready')},FurnitureEditor:{pending:()=>pending}};
 vm.createContext(ctx);vm.runInContext(src.slice(src.indexOf('function currentWorkspaceStage()'),src.indexOf('function renderShell()'))+fn,ctx);await ctx.openWorkspaceStage(stage);return {calls,ctx};
}
(async()=>{
 for(const stage of ['cameras','furnish','images','videos','architecture','surfaces']){const x=await run({pending:true,active:true,stage});assert.deepEqual(x.calls,['blocked']);assert.equal(x.ctx.location.href,undefined);}
 for(const stage of ['cameras','furnish']){const x=await run({stage});assert.equal(x.ctx.tab,'references');assert(x.calls.indexOf('ready')<x.calls.indexOf(stage==='cameras'?'camera':'furnish'));}
 for(const name of ['index','floor-plan']){const html=fs.readFileSync(require.resolve('../static/'+name+'.html'),'utf8');assert(html.includes('/workspace-chrome.css'));assert(html.includes('workspace-brand'));assert(/<footer[^>]*><span class="appearance-controls">/.test(html));}
 console.log('Shared workflow frame: dirty navigation blocked, editor mount awaited, logo/theme/footer shared across both pages (10 checks).');
})().catch(e=>{console.error(e);process.exitCode=1});
