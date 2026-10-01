'use strict';
// Architecture tools hosted by the furniture canvas. All coordinates stay in
// drawing units and all drag deltas come from the pointer-down snapshot.
(() => {
 const clone=v=>structuredClone(v),id=()=> 'new'+crypto.randomUUID().replaceAll('-','');
 const kinds=['wall','window','door','sliding_door','opening','line','detail'];
 const names={wall:'Wall',window:'Window',door:'Door',sliding_door:'Sliding door',opening:'Door / opening',line:'Detail line',detail:'Outline'};
 const icons={select:'<path d="m5 3 14 10-7 1-3 7z"/>',wall:'<path d="M3 5h18v14H3zM3 12h18M9 5v7m7 0v7"/>',door:'<path d="M4 20V4h4m0 16V4l10 3v13zM14 12h1"/>',window:'<path d="M3 4h18v16H3zM12 4v16M3 12h18"/>',sliding_door:'<path d="M3 4h18v16H3zM12 4v16M6 10l2 2-2 2m12-4-2 2 2 2"/>'};
 const button=(text,action)=>`<button type="button" class="btn small" data-wall-action="${action}">${text}</button>`;
 class PlanWalls {
  constructor(doc,hooks){this.doc=doc;this.hooks=hooks;this.selected=null;this.tool='select';this.first=null;this.dirty=false;this.drag=null;this.history=[];this.future=[];this.snapping=true;this.guides=[];this.host=null}
  snapshot(){return clone({edits:this.doc.edits,features:this.doc.features,site:this.doc.site})}
  record(){this.history.push(this.snapshot());if(this.history.length>60)this.history.shift();this.future=[]}
  changed(){this.dirty=true;this.hooks.changed()}
  payload(){if(this.first)throw Error('Finish the wall or opening, or press Escape.');return {revision:this.doc.revision,map_revision:this.doc.map_revision,edits:this.doc.edits,features:this.doc.features,site:this.doc.site}}
  saved(doc){this.doc=doc;this.dirty=false;this.history=[];this.future=[];this.selected=null;this.first=null;this.tool='select'}
  clear(){this.selected=null;this.first=null;this.tool='select';this.guides=[];this.host=null}
  toolbar(){return `<div class="inline-wall-tools" role="toolbar" aria-label="Plan editing tools">${[['select','Select / move'],['wall','Add wall'],['door','Add door'],['window','Add window'],['sliding_door','Add sliding door']].map(([key,label])=>`<button type="button" class="btn drawing-icon ${this.tool===key?'selected':''}" data-wall-tool="${key}" aria-label="${label}" title="${label}" aria-pressed="${this.tool===key}"><svg viewBox="0 0 24 24">${icons[key]}</svg></button>`).join('')}${button('Undo','undo')}${button('Redo','redo')}<label class="wall-snap-toggle"><input type="checkbox" id="wall-snapping" ${this.snapping?'checked':''}> Snap</label></div>`}
  source(){return this.doc.features.find(f=>f.id===this.selected)||this.doc.elements.find(f=>f.id===this.selected)}
  element(){return this.hooks.svg()?.querySelector(`[data-plan-element="${this.selected}"]`)}
  geometry(key=this.selected){
   const source=this.doc.features.find(f=>f.id===key)||this.doc.elements.find(f=>f.id===key);if(source?.points)return clone(source);
   const el=this.hooks.svg()?.querySelector(`[data-plan-element="${key}"]`);if(!el)return null;
   if(['door','opening'].includes(source?.kind))return this.doorGeometry(el,source.id);
   if(!['wall','window','sliding_door','line'].includes(source?.kind))return null;
   const b=el.getBBox();if(Math.max(b.width,b.height)<4*Math.max(.1,Math.min(b.width,b.height)))return null;
   const horizontal=b.width>=b.height,m=el.transform.baseVal.consolidate()?.matrix;
   const transform=([x,y])=>{const p=m?new DOMPoint(x,y).matrixTransform(m):{x,y};return[p.x,p.y]};
   const points=(horizontal?[[b.x,b.y+b.height/2],[b.x+b.width,b.y+b.height/2]]:[[b.x+b.width/2,b.y],[b.x+b.width/2,b.y+b.height]]).map(transform);
   const thickness=Math.max(.1,Math.min(50,(horizontal?b.height:b.width)*(m?horizontal?Math.hypot(m.c,m.d):Math.hypot(m.a,m.b):1)||1.5));
   return {id:source.id,kind:source.kind,points,thickness,flip:false};
  }
  doorGeometry(el,key){
   const leaves=[],arcs=[],num='([-+]?\\d*\\.?\\d+(?:[eE][-+]?\\d+)?)',sep='[ ,]+',root=this.hooks.svg();
   const leaf=new RegExp('^\\s*M\\s*'+num+sep+num+'\\s*L\\s*'+num+sep+num+'\\s*$','i');
   const arc=new RegExp('^\\s*M\\s*'+num+sep+num+'\\s*A\\s*'+Array(7).fill(num).join(sep)+'\\s*$');
   for(const path of el.querySelectorAll('path:not(.plan-wall-hit)')){
    if(path.getAttribute('pointer-events')==='stroke')continue;
    const d=path.getAttribute('d')||'',a=d.match(arc),l=d.match(leaf),straight=/^\s*M[^a-z]+[LHV][^a-z]+$/i.test(d);if(!a&&!l&&!straight)return null;
    const m=root.getScreenCTM().inverse().multiply(path.getScreenCTM()),point=(x,y)=>{const p=new DOMPoint(x,y).matrixTransform(m);return[p.x,p.y]};
    if(a){const [x,y,rx,ry,rotation,large,sweep,ex,ey]=a.slice(1).map(Number);if(large||rotation||Math.abs(rx-ry)>.01)return null;arcs.push([point(x,y),point(ex,ey)])}
    else{const p=path.getPointAtLength(0),q=path.getPointAtLength(path.getTotalLength());leaves.push([point(p.x,p.y),point(q.x,q.y)])}
   }
   if(leaves.length!==1||arcs.length!==1)return null;
   const [a,b]=leaves[0],[u,v]=arcs[0],near=(p,q)=>Math.hypot(p[0]-q[0],p[1]-q[1])<.01;
   const [hinge,closed,tip]=near(b,v)?[a,u,b]:near(b,u)?[a,v,b]:near(a,v)?[b,u,a]:near(a,u)?[b,v,a]:[];
   if(!hinge)return null;
   return {id:key,kind:'door',points:[hinge,closed],thickness:.5,flip:(closed[0]-hinge[0])*(tip[1]-hinge[1])-(closed[1]-hinge[1])*(tip[0]-hinge[0])<0};
  }
  geometries(exclude=null){return [...this.doc.features,...this.doc.elements.filter(e=>!e.absorbed_by&&!this.doc.edits[e.id]?.hidden)].filter(e=>e.id!==exclude&&e.kind!=='floor_opening').map(e=>this.geometry(e.id)).filter(Boolean)}
  snap(p,e,targets=null){
   this.guides=[];if(!this.snapping||e.altKey)return {point:p};
   const all=targets||this.geometries(this.drag?.selected),scale=Math.abs(this.hooks.svg().getScreenCTM()?.a||1),tolerance=8/scale;
   const hit=DrawingGeometry.snapSegment(p,this.host?[this.host]:all,tolerance);
   if(hit){this.guides=[{points:hit.wall.points}];return hit}
   const result=DrawingGeometry.snapPoint(p,all.flatMap(f=>f.points),tolerance);this.guides=result.guides;return result;
  }
  drawGuides(){
   const svg=this.hooks.svg();if(!svg)return;svg.querySelector('#plan-snap-guides')?.remove();
   const lines=this.guides.map(g=>{const ps=g.points||(g.axis===0?[[g.value,0],[g.value,this.doc.height]]:[[0,g.value],[this.doc.width,g.value]]);return `<line x1="${ps[0][0]}" y1="${ps[0][1]}" x2="${ps[1][0]}" y2="${ps[1][1]}"/>`}).join('');
   svg.insertAdjacentHTML('beforeend',`<g id="plan-snap-guides" pointer-events="none">${lines}</g>`);
  }
  autoSplit(){
   const opening=this.geometry();if(!opening||!['window','door','sliding_door'].includes(opening.kind))return;
   const selected=this.selected;
   for(const wall of this.geometries(selected).filter(f=>f.kind==='wall')){
    const parts=DrawingGeometry.cutOpening(wall,opening,id);if(parts===null)continue;
    this.replace(wall,parts);this.changed();
   }
   this.selected=selected;
  }
  replace(old,features){
   const i=this.doc.features.findIndex(f=>f.id===old.id);
   if(i>=0)this.doc.features.splice(i,1);else this.doc.edits[old.id]={...this.doc.edits[old.id],hidden:true};
   this.doc.features.push(...features);this.selected=features[0]?.id||null;
  }
  updateGeometry(f){
   const old=this.source();if(this.doc.features.some(v=>v.id===old.id)){this.doc.features=this.doc.features.map(v=>v.id===old.id?f:v)}
   else{f.id=id();this.replace(old,[f])}this.selected=f.id;
  }
  properties(){
   const source=this.source();if(!source)return '';
   const f=this.geometry();
   return `<div class="wall-properties"><strong>${names[source.kind]||'Outline'}</strong>${f?`<div class="block-fields"><label class="field"><span>Length (plan units)</span><input id="wall-length" type="number" min=".2" step=".1" value="${Math.hypot(f.points[1][0]-f.points[0][0],f.points[1][1]-f.points[0][1]).toFixed(2)}"></label><label class="field"><span>Thickness</span><input id="wall-thickness" type="number" min=".1" max="50" step=".1" value="${f.thickness.toFixed(2)}"></label></div>${button('Apply size','size')}`:''}<div class="block-toolbar">${source.kind==='wall'?button('Split wall','split')+button('Insert window','insert-window'):''}${source.kind==='door'?button('Flip swing','flip'):''}${button('Delete','remove')}</div></div>`;
  }
  decorate(){
   const svg=this.hooks.svg();if(!svg)return;
   svg.querySelectorAll('[data-plan-element]').forEach(el=>{
    if(!kinds.includes(el.dataset.planKind))return;
    el.classList.add('plan-wall-editable');el.classList.toggle('plan-wall-selected',el.dataset.planElement===this.selected);
    // Fixed screen-space hit slop on paths, not bounding boxes across rooms.
    for(const path of [...el.querySelectorAll('path,line,polyline,polygon,rect')]){
     const hit=path.cloneNode(false);hit.removeAttribute('id');hit.setAttribute('class','plan-wall-hit');hit.setAttribute('style','fill:none!important;stroke:transparent!important;stroke-width:10px!important;vector-effect:non-scaling-stroke;pointer-events:stroke');path.parentNode.insertBefore(hit,path);
    }
   });this.handles();this.drawGuides();
   const holder=document.querySelector('#block-wall-properties');if(holder)holder.innerHTML=this.properties();
   document.querySelectorAll('.block-transform-panel,.block-object-properties').forEach(el=>{el.hidden=!!this.selected});
   const hint=document.querySelector('#block-edit-status');if(hint)hint.textContent=this.tool==='split'?'Click the selected wall to split it.':this.tool==='insert-window'?'Click both ends of the window on this wall.':this.tool!=='select'?`Click two points to add a ${names[this.tool].toLowerCase()}.`:this.dirty?'Unsaved wall changes.':'';
   document.querySelectorAll('[data-wall-tool]').forEach(el=>{el.classList.toggle('selected',el.dataset.wallTool===this.tool);el.setAttribute('aria-pressed',el.dataset.wallTool===this.tool?'true':'false')});
  }
  handles(){
   const svg=this.hooks.svg();if(!svg)return;svg.querySelector('#plan-wall-handles')?.remove();
   const f=this.geometry(),scale=Math.abs(svg.getScreenCTM()?.a||1),r=5/scale;
   let markup='';
   if(f){markup=f.points.map((p,i)=>`<circle data-wall-handle="${i}" cx="${p[0]}" cy="${p[1]}" r="${r}"><title>Drag wall end</title></circle>`).join('');
    if(f.kind==='wall'){const [a,b]=f.points,L=Math.hypot(b[0]-a[0],b[1]-a[1]),p=[(a[0]+b[0])/2-(b[1]-a[1])/L*f.thickness/2,(a[1]+b[1])/2+(b[0]-a[0])/L*f.thickness/2];markup+=`<rect data-wall-handle="thickness" x="${p[0]-r}" y="${p[1]-r}" width="${r*2}" height="${r*2}"><title>Drag to change wall thickness</title></rect>`}
   }
   if(this.first)markup+=`<circle cx="${this.first[0]}" cy="${this.first[1]}" r="${r}" pointer-events="none"/>`;
   svg.insertAdjacentHTML('beforeend',`<g id="plan-wall-handles">${markup}</g>`);
  }
  point(e){const p=new DOMPoint(e.clientX,e.clientY).matrixTransform(this.hooks.svg().getScreenCTM().inverse());return[Math.max(0,Math.min(this.doc.width,p.x)),Math.max(0,Math.min(this.doc.height,p.y))]}
  nearWall(p){const wall=this.geometry();if(wall?.kind!=='wall')throw Error('Select a straight wall first.');const q=DrawingGeometry.project(wall.points,p),scale=this.hooks.svg().getScreenCTM().a;if(Math.hypot(p[0]-q.point[0],p[1]-q.point[1])*scale>Math.max(12,wall.thickness*scale/2+5))throw Error('Click on the selected wall.');return {wall,point:q.point}}
  pointerDown(e){
   if(e.button!==0)return false;
   const el=e.target.closest('[data-plan-element]'),handle=e.target.closest('[data-wall-handle]')?.dataset.wallHandle;let p=this.point(e);
   if(this.tool!=='select'){
    try{
     if(!['split','insert-window'].includes(this.tool)){const snapped=this.snap(p,e);p=snapped.point;if(!this.first&&['window','door','sliding_door'].includes(this.tool))this.host=snapped.wall||null}
     if(this.tool==='split'){const {wall,point}=this.nearWall(p),features=DrawingGeometry.split(wall,point,id);this.record();this.replace(wall,features);this.changed();this.tool='select'}
     else if(this.tool==='insert-window'){const {wall,point}=this.nearWall(p);if(!this.first)this.first=point;else{const result=DrawingGeometry.insert(wall,this.first,point,'window',id);this.record();this.replace(wall,result.features);this.selected=result.openingId;this.first=null;this.tool='select';this.changed()}}
     else if(!this.first)this.first=p;
     else{let q=p;if(!e.shiftKey&&!this.host)q=Math.abs(p[0]-this.first[0])<Math.abs(p[1]-this.first[1])?[this.first[0],p[1]]:[p[0],this.first[1]];if(Math.hypot(q[0]-this.first[0],q[1]-this.first[1])<.2)throw Error('Choose a different end point.');this.record();const f={id:id(),kind:this.tool,points:[this.first,q],thickness:1.5,flip:false};this.doc.features.push(f);this.selected=f.id;this.first=null;this.tool='select';this.changed();this.autoSplit();this.host=null;this.guides=[]}
     this.hooks.select();this.hooks.redraw();if(!this.first)this.hooks.commit?.();
    }catch(err){this.hooks.error(err.message)}return true;
   }
   if(!handle&&(!el||!kinds.includes(el.dataset.planKind)))return false;
   if(!handle)this.selected=el.dataset.planElement;
   this.hooks.select();
   this.drag={start:p,screen:[e.clientX,e.clientY],before:this.snapshot(),source:clone(this.source()),geometry:this.geometry(),targets:this.geometries(this.selected),handle,moved:false,selected:this.selected};
   this.hooks.redraw();this.hooks.svg().setPointerCapture(e.pointerId);return true;
  }
  pointerMove(e){
   const drag=this.drag;if(!drag){if(this.tool!=='select'&&e.buttons!==4){this.snap(this.point(e),e);this.drawGuides();return true}return false}
   if(!drag.moved&&Math.hypot(e.clientX-drag.screen[0],e.clientY-drag.screen[1])<3)return true;
   if(!drag.moved){this.record();drag.moved=true}
   let p=this.point(e);
   if(drag.geometry&&drag.handle!=='thickness'){
    const anchor=drag.handle?drag.geometry.points[Number(drag.handle)]:drag.geometry.points[0],target=anchor.map((v,i)=>v+p[i]-drag.start[i]);
    const snapped=this.snap(target,e,drag.targets);p=p.map((v,i)=>v+snapped.point[i]-target[i]);
   }
   const delta=p.map((v,i)=>v-drag.start[i]);Object.assign(this.doc,clone(drag.before));this.selected=drag.selected;
   if(drag.handle&&drag.geometry){
    let f=drag.geometry;
    if(drag.handle==='thickness'){f=clone(f);const [a,b]=f.points,L=Math.hypot(b[0]-a[0],b[1]-a[1]);f.thickness=Math.max(.1,Math.min(50,f.thickness+2*(delta[0]*-(b[1]-a[1])/L+delta[1]*(b[0]-a[0])/L)))}
    else f=DrawingGeometry.dragEndpoint(f,Number(drag.handle),delta,this.doc.width,this.doc.height,!e.shiftKey);
    // Reuse one identifier throughout the gesture, including final pointerup.
    if(!drag.source.points){drag.newId=drag.newId||id();f.id=drag.newId;this.replace(drag.source,[f])}else this.updateGeometry(f);
   }else if(drag.source.points){const f=clone(drag.source),limits=[this.doc.width,this.doc.height];const shift=delta.map((v,i)=>Math.max(-Math.min(...f.points.map(p=>p[i])),Math.min(limits[i]-Math.max(...f.points.map(p=>p[i])),v)));f.points=f.points.map(p=>p.map((v,i)=>v+shift[i]));this.updateGeometry(f)}
   else{const edit=drag.before.edits[drag.selected]||{};this.doc.edits[drag.selected]={...edit,dx:Math.max(-this.doc.width,Math.min(this.doc.width,(edit.dx||0)+delta[0])),dy:Math.max(-this.doc.height,Math.min(this.doc.height,(edit.dy||0)+delta[1]))}}
   this.changed();this.hooks.redraw();return true;
  }
  pointerUp(e,cancel=false){if(!this.drag)return false;const drag=this.drag;if(cancel){Object.assign(this.doc,clone(drag.before));this.selected=drag.selected;if(drag.moved)this.history.pop()}else if(drag.moved){this.pointerMove(e);this.autoSplit()}this.drag=null;this.guides=[];this.host=null;const svg=this.hooks.svg();if(svg.hasPointerCapture(e.pointerId))svg.releasePointerCapture(e.pointerId);this.hooks.redraw();if(drag.moved&&!cancel)this.hooks.commit?.();return true}
  action(action){
   if(action==='undo'||action==='redo'){const from=action==='undo'?this.history:this.future,to=action==='undo'?this.future:this.history;if(from.length){to.push(this.snapshot());Object.assign(this.doc,from.pop());this.clear();this.changed()}this.hooks.redraw();this.hooks.commit?.();return}
   const source=this.source();if(!source)throw Error('Select a wall or opening first.');
   if(action==='split'||action==='insert-window'){if(this.geometry()?.kind!=='wall')throw Error('Select a straight wall first.');this.tool=action;this.first=null}
   else if(action==='remove'){this.record();this.replace(source,[]);this.changed()}
   else if(action==='size'){const f=this.geometry();if(!f)throw Error('This outline needs tracing before resizing.');const out=DrawingGeometry.resize(f,Number(document.querySelector('#wall-length').value),Number(document.querySelector('#wall-thickness').value),this.doc.width,this.doc.height);this.record();this.updateGeometry(out);this.changed()}
   else if(action==='flip'&&source.kind==='door'){this.record();source.flip=!source.flip;this.changed()}
   else if(['rotate-left','rotate-right','flip-x','flip-y','duplicate'].includes(action)){
    const f=this.geometry();if(!f)throw Error('Trace this imported outline as a wall or opening to transform it.');
    const center=[0,1].map(i=>(f.points[0][i]+f.points[1][i])/2),limits=[this.doc.width,this.doc.height];
    if(action==='duplicate'){
     f.id=id();const delta=limits.map((limit,i)=>Math.min(10,limit-Math.max(...f.points.map(p=>p[i]))));
     f.points=f.points.map(p=>p.map((v,i)=>v+delta[i]));
    }else{
     f.points=f.points.map(p=>{const x=p[0]-center[0],y=p[1]-center[1];return action==='rotate-left'?[center[0]+y,center[1]-x]:action==='rotate-right'?[center[0]-y,center[1]+x]:[center[0]+x*(action==='flip-x'?-1:1),center[1]+y*(action==='flip-y'?-1:1)]});
     if(action.startsWith('flip-')&&f.kind==='door')f.flip=!f.flip;
    }
    if(f.points.some(p=>p.some((v,i)=>v<0||v>limits[i])))throw Error('Move the object away from the plan edge before rotating.');
    this.record();if(action==='duplicate'){this.doc.features.push(f);this.selected=f.id}else this.updateGeometry(f);
    this.changed();this.autoSplit();
   }
   if(action==='size')this.autoSplit();this.hooks.redraw();if(!['split','insert-window'].includes(action))this.hooks.commit?.();
  }
 }
 window.PlanWalls=PlanWalls;
})();
