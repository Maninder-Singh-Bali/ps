const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const src=fs.readFileSync(require.resolve('../static/app.js'),'utf8');
const functions=src.slice(src.indexOf('function currentWorkspaceStage()'),src.indexOf('function renderShell()'))+src.slice(src.indexOf('async function openWorkspaceStage('),src.indexOf("document.addEventListener('click',e=>{const b=e.target.closest('[data-workspace-stage]')"));
function fixture(target){
 let release,mode='blocks',active=false;const ready=new Promise(r=>release=r),seen=[];
 const ctx={pendingWorkspaceStage:target,workflowOpening:false,workflowNavigation:0,tab:'plan',pid:'p',rid:'r',planId:'a',location:{},history:{replaceState(){}},encodeURIComponent,localStorage:{setItem(){}},A:()=>({manual_draft_id:'d'}),P:()=>({}),toast:()=>{},renderMain:()=>{active=true},renderShell:()=>seen.push(ctx.currentWorkspaceStage()),openCameraView:async()=>{mode='camera'},openFurnitureBlocks:async()=>{mode='blocks'}};
 ctx.window={InlinePlan:{active:()=>active,mode:()=>mode,ready:()=>ready},FurnitureEditor:{pending:()=>false},CameraEditor:{pending:()=>false},setWorkflowHighlight:s=>seen.push(s)};
 vm.createContext(ctx);vm.runInContext(functions,ctx);return {ctx,seen,release};
}
(async()=>{
 for(const target of ['furnish','cameras','images','videos','architecture','surfaces']){
  const {ctx,seen,release}=fixture(target);assert.equal(ctx.currentWorkspaceStage(),target,'route before project/editor loading');
  const opening=ctx.openWorkspaceStage(target);ctx.renderShell();assert.equal(ctx.currentWorkspaceStage(),target,'while editor loading');
  if(['furnish','cameras'].includes(target)){await ctx.openWorkspaceStage('images');assert.equal(ctx.currentWorkspaceStage(),target,'do not race an in-flight editor mount');}
  release();await opening;assert(seen.every(x=>x===target),`${target}: ${seen}`);assert.equal(ctx.currentWorkspaceStage(),target);
 }
 // Leaving for Plan/Surfaces must not wait for camera data or a preview mount.
 for(const destination of ['surfaces','architecture'])for(const delay of ['mount','camera']){
  const {ctx,release,seen}=fixture(null);let finishCamera,reset=0,replaced=0;
  ctx.window.InlinePlan.reset=()=>{reset++};ctx.history.replaceState=()=>{replaced++};
  const cameraReady=new Promise(r=>finishCamera=r);
  if(delay==='camera')ctx.openCameraView=()=>cameraReady;
  const opening=ctx.openWorkspaceStage('cameras');
  if(delay==='camera'){release();await Promise.resolve();await Promise.resolve();}
  await ctx.openWorkspaceStage(destination);
  assert(ctx.location.href.includes('/floor-plan.html'));assert.equal(reset,1);assert.equal(ctx.pendingWorkspaceStage,destination);
  release();finishCamera();await opening;
  assert.equal(replaced,0,'late camera completion cannot replace destination URL');assert.equal(ctx.currentWorkspaceStage(),destination);assert.equal(seen.at(-1),destination);
 }
 const {ctx,release}=fixture(null);ctx.tab='images';ctx.openCameraView=async()=>{throw Error('fixture mount failure')};const failed=ctx.openWorkspaceStage('cameras');release();await failed;assert.equal(ctx.pendingWorkspaceStage,null);assert.equal(ctx.workflowOpening,false);assert.equal(ctx.currentWorkspaceStage(),'furnish','failure reflects actual mounted view');
 const helper=fs.readFileSync(require.resolve('../static/workflow-highlight.js'),'utf8');
 for(const stage of ['plan','surfaces']){
  const buttons=['plan','furnish','surfaces','cameras','images','videos'].map(key=>({dataset:{stage:key},current:false,setAttribute(){this.current=true},removeAttribute(){this.current=false}}));
  const c={location:{pathname:'/floor-plan.html',search:stage==='surfaces'?'?stage=surfaces':''},URLSearchParams,document:{querySelectorAll:()=>buttons}};c.window=c;vm.runInNewContext(helper,c);assert.deepEqual(buttons.filter(b=>b.current).map(b=>b.dataset.stage),[stage]);
 }
 console.log('Workflow highlight: all six routes retain destination during loading; camera-to-surfaces/plan during delayed mount and camera fetch, concurrent clicks, failure recovery and initial Plan/Surfaces selection passed.');
})().catch(e=>{console.error(e);process.exitCode=1});
