const fs=require('fs'),vm=require('vm'),assert=require('assert');
const elements={},handlers={},timers=new Map(),requests=[],frames=new Map();let tid=0;
const element=id=>elements[id]??=( {id,value:'',hidden:false,textContent:'',style:{},attributes:{},setAttribute(k,v){this.attributes[k]=v},querySelectorAll(){return []},classList:{add(){}},setPointerCapture(){},getScreenCTM(){return {a:1,d:1,inverse(){return {}}}},close(){}} );
const room={id:'room',revision:3,plan_id:'plan',bbox:[0,0,1,1]};
const sandbox={DrawingGeometry:require('../static/drawing-geometry.js'),requestAnimationFrame(fn){frames.set(++tid,fn);return tid},cancelAnimationFrame(id){frames.delete(id)},console,Math,Number,structuredClone,encodeURIComponent,setTimeout(fn){timers.set(++tid,fn);return tid},clearTimeout(id){timers.delete(id)},state:{projects:{project:{rooms:[room]}}},pid:'project',rid:'room',modalType:'camera',window:{},document:{addEventListener(type,fn){(handlers[type]??=[]).push(fn)}},$:selector=>element(selector),A:()=>({id:'plan',width:100,height:100}),url:id=>'/'+id,esc:s=>s,showModal(){element('#camera-height').value='1.5';element('#camera-target-height').value='1.5';element('#camera-fov').value='67';element('#camera-original').checked=true},toast(){},refresh:async()=>{},confirm:()=>true,DOMPoint:class{constructor(x,y){this.x=x;this.y=y}matrixTransform(){return this}},api:async(route,data,method)=>{if(method==='GET')return {saved_camera:null,calibrated:false};requests.push({route,data});return route.endsWith('camera-preview')?{image:'data:image/png;base64,test',typed_segments:2}:{revision:4,camera:data}}};
vm.createContext(sandbox);vm.runInContext(fs.readFileSync('static/camera-view.js','utf8'),sandbox);
sandbox.document.querySelectorAll=()=>[];
const originalApi=sandbox.api;
sandbox.api=async(route,data,method)=>route.endsWith('/drawing')?{elements:[],features:[]}:originalApi(route,data,method);
sandbox.DrawingPreview=sandbox.window.DrawingPreview={markup:()=>'<g data-current-walls></g>',finish(){}};
sandbox.FurnitureLibrary={symbol:()=>'<rect width="100" height="100"/>'};
sandbox.PlanLabels=sandbox.window.PlanLabels={objectName:v=>v.label,attach(){}};
room.block_layout={items:[{id:'sofa',label:'Sofa',x:.2,y:.3,width:.1,depth:.2,angle:90}]};
sandbox.state.projects.project.rooms.push({id:'other-room',plan_id:'plan',bbox:[.5,0,.5,1],block_layout:{items:[{id:'chair',label:'Chair',x:.7,y:.5,width:.1,depth:.1,angle:0}]}});
async function action(name){const button={dataset:{camera:name}};const e={target:{closest(selector){return selector==='[data-camera]'?button:null}}};for(const fn of handlers.click)await fn(e)}
function pointer(type,x,y,handle){element('#camera-plan')['onpointer'+type]({button:0,pointerId:1,clientX:x,clientY:y,target:{dataset:handle?{handle}:{}}})}
async function animate(){for(let i=0;frames.size&&i<100;i++){const work=[...frames.values()];frames.clear();for(const fn of work)fn()}assert.equal(frames.size,0)}
async function flush(){const pending=[...timers.values()];timers.clear();for(const fn of pending)await fn()}
(async()=>{
 await sandbox.window.openCameraView();
 element('#camera-original').checked=false;
 await action('position');
 assert.match(element('#camera-plan').innerHTML,/data-current-walls/);
 assert.match(element('#camera-plan').innerHTML,/data-camera-block="sofa"/);
 assert.match(element('#camera-plan').innerHTML,/data-camera-block="chair"/);
 assert.match(element('#camera-plan').innerHTML,/data-object-label="Chair"/);
 await action('preview');assert.match(element('#camera-status').textContent,/Place camera/);assert.equal(requests.length,0);
 await action('position');pointer('down',20,80);await action('preview');assert.match(element('#camera-empty').textContent,/target away/);assert.equal(requests.length,0);
 // Reproduce the user path: drag the overlapping target while target-placement mode is active.
 pointer('down',20,80,'target');pointer('move',40,30);pointer('up',40,30);await flush();
 assert.equal(requests.length,1);assert.equal(element('#camera-preview').hidden,false);assert.deepEqual([...requests[0].data.target],[.4,.3]);
 // Enter Aim mode without a new click: a valid existing view must still refresh and save.
 await action('target');await action('preview');assert.equal(requests.length,2);await action('save');assert.match(requests[2].route,/floor-camera$/);
 // Manual refresh cancels a pending automatic refresh (no stale timer hides the result).
 pointer('down',40,30,'target');pointer('move',45,35);pointer('up',45,35);await action('preview');await flush();assert.equal(element('#camera-preview').hidden,false);assert.equal(timers.size,0);
 const cameraBefore=JSON.stringify(requests.at(-1).data);const countBefore=requests.length;
 await action('zoom-in');await animate();const zoomed=element('#camera-plan').attributes.viewBox.split(' ').map(Number);assert.ok(zoomed[2]<100);
 const svg=element('#camera-plan');svg.onpointerdown({button:1,clientX:50,clientY:50,pointerId:2,preventDefault(){}});svg.onpointermove({clientX:70,clientY:60});svg.onpointerup({});const panned=svg.attributes.viewBox.split(' ').map(Number);assert.equal(panned[0],zoomed[0]-20);assert.equal(panned[1],zoomed[1]-10);
 await action('fit-plan');await animate();assert.equal(svg.attributes.viewBox,'0 0 100 100');
 let prevented=false;svg.onwheel({ctrlKey:true,deltaY:-150,deltaMode:0,clientX:25,clientY:30,preventDefault(){prevented=true}});await animate();assert.ok(prevented);assert.ok(Number(svg.attributes.viewBox.split(' ')[2])<100);
 const beforePan=svg.attributes.viewBox.split(' ').map(Number);
 svg.onwheel({deltaX:12,deltaY:24,deltaMode:0,preventDefault(){}});
 let wheelPan=svg.attributes.viewBox.split(' ').map(Number);
 assert.deepEqual(wheelPan,[beforePan[0]+12,beforePan[1]+24,...beforePan.slice(2)]);
 svg.onwheel({deltaX:1,deltaY:2,deltaMode:1,preventDefault(){}});
 assert.deepEqual(svg.attributes.viewBox.split(' ').map(Number),[wheelPan[0]+16,wheelPan[1]+32,...wheelPan.slice(2)]);
 // A pending button zoom cannot continue and undo a subsequent pan.
 await action('zoom-in');svg.onwheel({deltaX:5,deltaY:7,deltaMode:0,preventDefault(){}});assert.equal(frames.size,0);
 const stable=svg.attributes.viewBox;await animate();assert.equal(svg.attributes.viewBox,stable);
 const panStart=stable.split(' ').map(Number);
 svg.onpointerdown({button:0,shiftKey:true,clientX:10,clientY:10,pointerId:3,preventDefault(){}});svg.onpointermove({clientX:30,clientY:40});svg.onpointerup();
 assert.deepEqual(svg.attributes.viewBox.split(' ').map(Number),[panStart[0]-20,panStart[1]-30,...panStart.slice(2)]);
 assert.equal(requests.length,countBefore);await action('preview');assert.equal(JSON.stringify(requests.at(-1).data),cameraBefore);
 // A save/refresh must capture the visible controls even before a change event.
 element('#camera-target-height').value='1.1';element('#camera-fov').value='90';
 await action('preview');assert.equal(requests.at(-1).data.target_height,1.1);assert.equal(requests.at(-1).data.horizontal_fov,90);
 await action('save');assert.equal(requests.at(-1).data.target_height,1.1);assert.equal(requests.at(-1).data.horizontal_fov,90);
 console.log('Camera zoom/pan: controls, smooth wheel, fit, and unchanged camera payload passed');
 console.log('Camera UI: incomplete-view feedback, drag completion, pending aim refresh/save, and timer race passed');
 await sandbox.window.openCameraView('project','room',{view:[10,20,30,40]});
 assert.equal(element('#camera-plan').attributes.viewBox,'10 20 30 40');
 let furnitureSwitch;
 sandbox.openFurnitureBlocks=async(...args)=>{furnitureSwitch=args};
 await action('furniture');
 assert.equal(furnitureSwitch[1],'room');assert.deepEqual([...furnitureSwitch[2].view],[10,20,30,40]);
 console.log('Shared camera workspace: corrected walls, all-room furniture, and retained view passed');
 // A room without cameras can discover saved views on the same floor.
 const other=sandbox.state.projects.project.rooms.find(r=>r.id==='other-room');
 const cam={position:[.7,.7],target:[.6,.3],height:1.4,target_height:1.4,horizontal_fov:50};
 other.name='other-room';other.revision=2;other.camera_views={saved:{id:'saved',name:'Living view',revision:6,camera:cam}};
 sandbox.state.projects.project.rooms.push({id:'upstairs',plan_id:'plan',floor:'upper',camera_views:{hidden:{id:'hidden',name:'Upstairs',camera:cam}}});
 sandbox.openCameraView=sandbox.window.openCameraView;
 const selected=[];sandbox.window.WorkspaceSelection={selectRoom:id=>selected.push(['room',id]),selectCamera:id=>selected.push(['camera',id])};
 await sandbox.window.openCameraView('project','room',{viewId:null});
 assert.match(element('#camera-saved-view').innerHTML,/other-room/);
 assert(!element('#camera-saved-view').innerHTML.includes('Upstairs'));
 assert.match(element('#camera-plan').innerHTML,/data-saved-camera="saved"/);
 await action('preview');assert.match(element('#camera-empty').textContent,/Choose a saved view/);
 for(const fn of handlers.change)await fn({target:{id:'camera-saved-view',value:'saved'}});
 await flush();assert.equal(requests.at(-1).data.room_id,'other-room');assert.equal(element('#camera-preview').hidden,false);
 assert.deepEqual(selected,[['room','other-room'],['camera','saved']]);
 assert.deepEqual(other.camera_views.saved.camera,cam);
 // Cancelling a dirty switch retains the selected camera and its draft.
 element('#camera-name').value='Unsaved name';for(const fn of handlers.input)fn({target:{id:'camera-name'}});
 sandbox.confirm=()=>false;const count=selected.length;
 for(const fn of handlers.change)await fn({target:{id:'camera-saved-view',value:''}});
 assert.equal(selected.length,count);assert.equal(element('#camera-saved-view').value,'saved');
 console.log('Saved camera discovery: floor isolation, cross-room preview and unsaved-change protection passed');
 sandbox.confirm=()=>true;
 // Reload with no per-room memory must restore the named camera, not New view.
 await sandbox.window.openCameraView('project','other-room',{view:[0,0,10,10]});await flush();
 assert.equal(element('#camera-saved-view').value,'saved');assert.equal(element('#camera-preview').hidden,false);
 assert.equal(element('#camera-plan').attributes.viewBox,'0 0 100 100');
 // Explicit New view must remain blank even if the server returns a saved camera.
 const normalApi=sandbox.api;sandbox.api=async(...args)=>args[0].includes('shared-scene')?{saved_camera:cam}:normalApi(...args);
 await sandbox.window.openCameraView('project','other-room',{viewId:null});await action('preview');assert.equal(element('#camera-preview').hidden,true);
 sandbox.api=normalApi;
 // Delayed earlier room selection must not restore an old camera/route after a newer one.
 let release;sandbox.api=(...args)=>args[0].includes('shared-scene')&&args[0].includes('other-room')?new Promise(resolve=>release=resolve):normalApi(...args);
 const slow=handlers.change[0]({target:{id:'camera-saved-view',value:'saved'}});
 await sandbox.window.openCameraView('project','room',{viewId:null});const selectionCount=selected.length;
 release({saved_camera:cam});await slow;assert.equal(selected.length,selectionCount);assert.equal(element('#camera-saved-view').value,'');
 sandbox.api=normalApi;
 console.log('Camera navigation: two-axis pan, line deltas, pinch, shift-drag, reload, explicit New view and async ordering passed');


})().catch(e=>{console.error(e);process.exitCode=1});
