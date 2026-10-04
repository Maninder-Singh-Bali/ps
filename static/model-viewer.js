'use strict';
// Orthographic inspection of the shared scene. Orbit never changes the saved camera.
(() => {
 const defaults=()=>({yaw:-Math.PI/4,pitch:Math.PI/5,zoom:1,pan:[0,0],transparent:false,edges:false,cutaway:false,projection:'orthographic'});
 const clamp=(v,a,b)=>Math.max(a,Math.min(b,v));
 const angle=v=>Math.atan2(Math.sin(v),Math.cos(v));
 function rotate(p,view){const c=Math.cos(view.yaw),s=Math.sin(view.yaw),x=p[0]*c-p[1]*s,y=p[0]*s+p[1]*c;return [x,y*Math.sin(view.pitch)-p[2]*Math.cos(view.pitch),y*Math.cos(view.pitch)+p[2]*Math.sin(view.pitch)]}
 function frame(faces){const lo=[Infinity,Infinity,Infinity],hi=[-Infinity,-Infinity,-Infinity];for(const f of faces)for(const p of f.points)for(let i=0;i<3;i++){lo[i]=Math.min(lo[i],p[i]);hi[i]=Math.max(hi[i],p[i])}if(!Number.isFinite(lo[0]))return {center:[0,0,0],radius:1};return {center:lo.map((v,i)=>(v+hi[i])/2),radius:Math.max(1,Math.hypot(...hi.map((v,i)=>v-lo[i]))/2)}}
 function project(p,view,bounds,width,height){const q=rotate(p.map((v,i)=>v-bounds.center[i]),view),scale=Math.min(width,height)*.43/bounds.radius*view.zoom;const R=bounds.radius,D=R*3,perspective=view.projection==='perspective',factor=perspective?D/(D-q[2]):1,depth=perspective?R*((D*D-R*R)/(R*(D-q[2]))-D/R):q[2];return [width/2+view.pan[0]*width+q[0]*scale*factor,height/2+view.pan[1]*height+q[1]*scale*factor,depth]}
 function inside(p,ps){let hit=false;for(let i=0,j=ps.length-1;i<ps.length;j=i++)if((ps[i][1]>p[1])!==(ps[j][1]>p[1])&&p[0]<(ps[j][0]-ps[i][0])*(p[1]-ps[i][1])/(ps[j][1]-ps[i][1])+ps[i][0])hit=!hit;return hit}
 function gesture(start,dx,dy,pan,width,height){return pan?{...start,pan:[start.pan[0]+dx/width,start.pan[1]+dy/height]}:{...start,yaw:angle(start.yaw-dx*.008),pitch:angle(start.pitch+dy*.006)}}
 const dot=(a,b)=>a.reduce((s,v,i)=>s+v*b[i],0),sub=(a,b)=>a.map((v,i)=>v-b[i]),cross=(a,b)=>[a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]],normal=v=>{const n=Math.hypot(...v);return v.map(x=>x/(n||1))};
 function walkBasis(w){const s=Math.sin(w.yaw),c=Math.cos(w.yaw),p=Math.sin(w.pitch),q=Math.cos(w.pitch);return {right:[c,s,0],up:[-s*p,c*p,q],forward:[s*q,-c*q,p]}}
 function cameraPoint(p,w){const b=walkBasis(w),v=sub(p,w.position);return [dot(v,b.right),dot(v,b.up),dot(v,b.forward)]}
 function clipNear(points,near){const out=[];for(let i=0;i<points.length;i++){const a=points[i],b=points[(i+1)%points.length],A=a[2]>=near,B=b[2]>=near;if(A)out.push(a);if(A!==B){const t=(near-a[2])/(b[2]-a[2]);out.push(a.map((v,j)=>v+t*(b[j]-v)))}}return out}
 function walkProject(points,w,width,height,radius){const near=w.unit*.04,f=height/(2*Math.tan((w.verticalFov||60)*Math.PI/360));return clipNear(points.map(p=>cameraPoint(p,w)),near).map(p=>[width/2+p[0]*f/p[2],height/2-p[1]*f/p[2],radius*1.1*(2*near/p[2]-1)])}
 function rayFor(p,view,bounds,width,height){
  if(view.walk){const w=view.walk,b=walkBasis(w),f=height/(2*Math.tan((w.verticalFov||60)*Math.PI/360)),x=(p[0]-width/2)/f,y=-(p[1]-height/2)/f;return {origin:w.position,direction:normal(b.forward.map((v,i)=>v+x*b.right[i]+y*b.up[i]))}}
  const scale=Math.min(width,height)*.43/bounds.radius*view.zoom,x=(p[0]-width/2-view.pan[0]*width)/scale,y=(p[1]-height/2-view.pan[1]*height)/scale,D=bounds.radius*3;
  const inverse=q=>{const yy=q[1]*Math.sin(view.pitch)+q[2]*Math.cos(view.pitch),z=-q[1]*Math.cos(view.pitch)+q[2]*Math.sin(view.pitch),c=Math.cos(view.yaw),s=Math.sin(view.yaw);return [q[0]*c+yy*s,-q[0]*s+yy*c,z]};
  const origin=inverse(view.projection==='perspective'?[0,0,D]:[x,y,D]).map((v,i)=>v+bounds.center[i]);
  return {origin,direction:normal(inverse(view.projection==='perspective'?[x,y,-D]:[0,0,-1]))};
 }
 function raycast(ray,faces,maxDistance=Infinity){let best=null;
  for(const face of faces)for(let i=1;i<face.points.length-1;i++){
   const [a,b,c]=[face.points[0],face.points[i],face.points[i+1]],e1=sub(b,a),e2=sub(c,a),h=cross(ray.direction,e2),det=dot(e1,h);if(Math.abs(det)<1e-9)continue;
   const v=sub(ray.origin,a),u=dot(v,h)/det;if(u<0||u>1)continue;const q=cross(v,e1),t=dot(ray.direction,q)/det;if(t<0||u+t>1)continue;const distance=dot(e2,q)/det;
   if(distance<1e-5||distance>maxDistance||best&&distance>=best.distance)continue;
   let n=normal(cross(e1,e2));if(dot(n,ray.direction)>0)n=n.map(v=>-v);
   best={...face,point:ray.origin.map((v,i)=>v+distance*ray.direction[i]),normal:n,distance};
  }return best;
 }
 function walkMove(w,forward,right,seconds,faces){
  const length=Math.hypot(forward,right);if(!length)return w;
  const speed=1.8*w.unit*Math.min(.05,seconds),dx=(Math.sin(w.yaw)*forward+Math.cos(w.yaw)*right)/length*speed,dy=(-Math.cos(w.yaw)*forward+Math.sin(w.yaw)*right)/length*speed;
  const out={...w,position:[...w.position]},solids=faces.filter(f=>f.architecture&&!f.ceiling&&f.floorName===w.floorName),floors=faces.filter(f=>f.floor&&f.floorName===w.floorName);
  for(const delta of [[dx,0,0],[0,dy,0]]){
   const distance=Math.hypot(...delta);if(!distance)continue;const direction=delta.map(v=>v/distance),next=out.position.map((v,i)=>v+delta[i]);
   if(!floors.some(f=>inside(next,f.points)))continue;
   if(raycast({origin:out.position,direction},solids,distance+.18*w.unit))continue;
   out.position=next;
  }return out;
 }
 function color(value){return value.startsWith('#')?[1,3,5].map(i=>parseInt(value.slice(i,i+2),16)/255):value.match(/[\d.]+/g).slice(0,3).map(Number).map(v=>v/255)}
 // A depth buffer keeps cushions, legs and cabinet fronts correctly occluded.
 // All input faces are convex, so a triangle fan preserves their exact outlines.
 class DepthRenderer {
  constructor(canvas){
   const gl=canvas.getContext('webgl',{alpha:false,antialias:true,preserveDrawingBuffer:true});if(!gl)throw Error('WebGL unavailable');this.gl=gl;
   const shader=(type,source)=>{const s=gl.createShader(type);gl.shaderSource(s,source);gl.compileShader(s);if(!gl.getShaderParameter(s,gl.COMPILE_STATUS))throw Error('Model shader failed');return s};
   const v=shader(gl.VERTEX_SHADER,'attribute vec3 position; attribute vec4 colour; varying vec4 tint; void main(){gl_Position=vec4(position,1.0);tint=colour;}');
   const f=shader(gl.FRAGMENT_SHADER,'precision mediump float; varying vec4 tint; void main(){gl_FragColor=tint;}');
   this.program=gl.createProgram();gl.attachShader(this.program,v);gl.attachShader(this.program,f);gl.linkProgram(this.program);gl.deleteShader(v);gl.deleteShader(f);if(!gl.getProgramParameter(this.program,gl.LINK_STATUS))throw Error('Model shader link failed');
   this.buffer=gl.createBuffer();this.pos=gl.getAttribLocation(this.program,'position');this.col=gl.getAttribLocation(this.program,'colour');
  }
  draw(faces,w,h,radius,transparent,showEdges=true){
   const gl=this.gl;gl.viewport(0,0,gl.canvas.width,gl.canvas.height);gl.clearColor(241/255,243/255,239/255,1);gl.clear(gl.COLOR_BUFFER_BIT|gl.DEPTH_BUFFER_BIT);gl.enable(gl.DEPTH_TEST);gl.depthFunc(gl.LEQUAL);gl.enable(gl.BLEND);gl.blendFunc(gl.SRC_ALPHA,gl.ONE_MINUS_SRC_ALPHA);gl.useProgram(this.program);gl.bindBuffer(gl.ARRAY_BUFFER,this.buffer);gl.enableVertexAttribArray(this.pos);gl.enableVertexAttribArray(this.col);gl.vertexAttribPointer(this.pos,3,gl.FLOAT,false,28,0);gl.vertexAttribPointer(this.col,4,gl.FLOAT,false,28,12);
   const vertex=(p,c,a)=>[p[0]/w*2-1,1-p[1]/h*2,-p[2]/(radius*1.1),...c,a];
   const batch=(rows,alpha,write)=>{
    const triangles=[],edges=[];
    for(const f of rows){const c=color(f.color),edge=f.selected?[.67,.50,.10]:c.map(v=>v*.72);for(let i=1;i<f.points.length-1;i++)for(const p of [f.points[0],f.points[i],f.points[i+1]])triangles.push(...vertex(p,c,alpha));for(let i=0;i<f.points.length;i++)if((showEdges||f.selected)&&(!f.edge_mask||f.edge_mask[i]))for(const p of [f.points[i],f.points[(i+1)%f.points.length]])edges.push(...vertex(p,edge,alpha))}
    gl.depthMask(write);gl.enable(gl.POLYGON_OFFSET_FILL);gl.polygonOffset(1,1);gl.bufferData(gl.ARRAY_BUFFER,new Float32Array(triangles),gl.DYNAMIC_DRAW);gl.drawArrays(gl.TRIANGLES,0,triangles.length/7);gl.disable(gl.POLYGON_OFFSET_FILL);gl.bufferData(gl.ARRAY_BUFFER,new Float32Array(edges),gl.DYNAMIC_DRAW);gl.drawArrays(gl.LINES,0,edges.length/7);
   };
   batch(faces.filter(f=>!transparent||!f.architecture),1,true);
   if(transparent)batch(faces.filter(f=>f.architecture),.18,false);
   gl.depthMask(true);
  }
  dispose(){this.gl.deleteBuffer(this.buffer);this.gl.deleteProgram(this.program);this.gl.getExtension('WEBGL_lose_context')?.loseContext()}
 }
 // Suppress shared coplanar tessellation seams, retaining real creases and boundaries.
 function cleanEdges(faces){
  const out=faces.map(f=>({...f,edge_mask:f.points.map((_,i)=>f.edge_mask?!!f.edge_mask[i]:true)})),map=new Map();
  out.forEach((f,fi)=>{const n=normal(cross(sub(f.points[1],f.points[0]),sub(f.points[2],f.points[0])));f.points.forEach((p,i)=>{const q=f.points[(i+1)%f.points.length],key=[p,q].map(v=>v.map(x=>x.toFixed(5)).join(',')).sort().join('|');const rows=map.get(key)||[];rows.push({fi,i,n});map.set(key,rows)})});
  for(const rows of map.values())if(rows.length===2&&Math.abs(dot(rows[0].n,rows[1].n))>.9999&&out[rows[0].fi].color===out[rows[1].fi].color)for(const r of rows)out[r.fi].edge_mask[r.i]=false;
  return out;
 }
 function planePoint(ray,point,n){const den=dot(ray.direction,n);if(Math.abs(den)<1e-7)return null;const t=dot(sub(point,ray.origin),n)/den;if(t<0)return null;return ray.origin.map((v,i)=>v+t*ray.direction[i])}
 function pick(p,faces){
  let best=null,depth=-Infinity;
  for(const f of faces)for(let i=1;i<f.points.length-1;i++){
   const [a,b,c]=[f.points[0],f.points[i],f.points[i+1]],den=(b[1]-c[1])*(a[0]-c[0])+(c[0]-b[0])*(a[1]-c[1]);if(Math.abs(den)<1e-9)continue;
   const u=((b[1]-c[1])*(p[0]-c[0])+(c[0]-b[0])*(p[1]-c[1]))/den,v=((c[1]-a[1])*(p[0]-c[0])+(a[0]-c[0])*(p[1]-c[1]))/den;
   if(u>=0&&v>=0&&u+v<=1){const z=u*(a[2]||0)+v*(b[2]||0)+(1-u-v)*(c[2]||0);if(z>depth){best=f;depth=z}}
  }return best;
 }
 class Viewer {
  constructor(canvas,view,onSelect,options={}){this.options=options;this.keys=new Set();this.canvas=canvas;this.view=view;this.onSelect=onSelect;this.faces=[];this.hits=[];this.bind();this.observer=new ResizeObserver(()=>this.draw());this.observer.observe(canvas)}
  update(faces,focus=null){this.faces=cleanEdges(faces);this.bounds=focus||frame(faces.filter(f=>!f.ceiling));this.draw()}
  enterWalk(walk){this.view.projection='perspective';this.view.walk=walk;this.keys.clear();this.draw();this.canvas.focus()}
  leaveWalk(){delete this.view.walk;this.keys.clear();this.draw()}
  visibleFaces(){return this.faces.filter(f=>(!f.ceiling||this.view.walk)&&(!this.view.cutaway||!f.architecture||!['wall','joined_wall'].includes(f.surfaceKind)||f.points.every(p=>p[2]===f.points[0][2])||rotate(f.points.reduce((s,p)=>s.map((v,i)=>v+p[i]/f.points.length),[0,0,0]).map((v,i)=>v-this.bounds.center[i]),this.view)[2]<=0))}
  surfaceAt(p){const ray=rayFor(p,this.view,this.bounds,this.canvas.clientWidth,this.canvas.clientHeight),faces=this.visibleFaces();return (this.view.transparent?raycast(ray,faces.filter(f=>!f.architecture||f.surface_design&&f.object_key?.startsWith('design:item:'))):null)||raycast(ray,faces)}
  tick(time){if(!this.view.walk||!this.keys.size){this.animation=null;this.lastTime=null;return}const dt=this.lastTime?Math.min(.05,(time-this.lastTime)/1000):.016;this.lastTime=time;const k=this.keys;this.view.walk=walkMove(this.view.walk,Number(k.has('w')||k.has('arrowup'))-Number(k.has('s')||k.has('arrowdown')),Number(k.has('d')||k.has('arrowright'))-Number(k.has('a')||k.has('arrowleft')),dt,this.faces);this.draw();this.animation=requestAnimationFrame(t=>this.tick(t))}
  reset(top=false){delete this.view.walk;Object.assign(this.view,defaults(),{transparent:this.view.transparent,edges:this.view.edges,cutaway:this.view.cutaway,projection:this.view.projection});if(top){this.view.yaw=0;this.view.pitch=Math.PI/2}this.draw()}
  zoom(factor){this.view.zoom=clamp(this.view.zoom*factor,.25,12);this.draw()}
  bind(){const c=this.canvas;
   c.onpointerdown=e=>{if(![0,1,2].includes(e.button))return;e.preventDefault();c.focus();c.setPointerCapture(e.pointerId);const r=c.getBoundingClientRect(),p=[e.clientX-r.left,e.clientY-r.top],hit=this.bounds?this.surfaceAt(p):null;const edit=e.button===0&&!e.shiftKey?this.options.beginEdit?.(hit,p):null;this.drag={edit,id:e.pointerId,x:e.clientX,y:e.clientY,pan:e.button!==0||e.shiftKey,button:e.button,moved:false,start:{...this.view,pan:[...this.view.pan]}};c.style.cursor='grabbing'};
   c.onpointermove=e=>{const d=this.drag;if(!d||d.id!==e.pointerId)return;const dx=e.clientX-d.x,dy=e.clientY-d.y;if(Math.hypot(dx,dy)>4)d.moved=true;if(d.moved){if(d.edit){const r=c.getBoundingClientRect(),p=[e.clientX-r.left,e.clientY-r.top];this.options.moveEdit?.(d.edit,rayFor(p,this.view,this.bounds,c.clientWidth,c.clientHeight),[dx,dy],e);return}if(this.view.walk){this.view.walk={...this.view.walk,yaw:d.start.walk.yaw+dx*.006,pitch:clamp(d.start.walk.pitch-dy*.006,-Math.PI*.48,Math.PI*.48)}}else Object.assign(this.view,gesture(d.start,dx,dy,d.pan,c.clientWidth,c.clientHeight));this.draw()}};
   c.onpointerup=e=>{const d=this.drag;if(!d||d.id!==e.pointerId)return;this.drag=null;c.style.cursor='grab';if(d.edit){this.options.endEdit?.(d.edit,!d.moved);if(c.hasPointerCapture(e.pointerId))c.releasePointerCapture(e.pointerId);return}if(c.hasPointerCapture(e.pointerId))c.releasePointerCapture(e.pointerId);if(!d.moved&&(d.button===0||!d.pan)){const r=c.getBoundingClientRect(),p=[e.clientX-r.left,e.clientY-r.top],hit=this.bounds?this.surfaceAt(p):pick(p,this.hits);if(!this.options.onSurface?.(hit))this.onSelect(hit?.id?hit:null,{shiftKey:e.shiftKey,ctrlKey:e.ctrlKey,metaKey:e.metaKey})}};
   c.onpointercancel=c.onlostpointercapture=()=>{if(this.drag?.edit)this.options.endEdit?.(this.drag.edit,true);this.drag=null;c.style.cursor='grab'};
   c.oncontextmenu=e=>e.preventDefault();
   c.ondragover=e=>{if(e.dataTransfer.types.includes('application/x-pixeloid-furniture')){e.preventDefault();e.dataTransfer.dropEffect='copy'}};
   c.ondrop=e=>{const id=e.dataTransfer.getData('application/x-pixeloid-furniture');if(!id)return;e.preventDefault();const r=c.getBoundingClientRect();this.options.onDrop?.(id,this.surfaceAt([e.clientX-r.left,e.clientY-r.top]))};
   c.onblur=()=>{this.keys.clear()};c.onkeyup=e=>this.keys.delete(e.key.toLowerCase());
   c.onwheel=e=>{e.preventDefault();if(this.view.walk)return;this.zoom(Math.exp(-clamp(e.deltaY*(e.deltaMode===1?16:e.deltaMode===2?c.clientHeight:1),-180,180)*.002))};
   c.onkeydown=e=>{if(e.key==='Escape'&&this.drag?.edit){const d=this.drag;this.drag=null;this.options.endEdit?.(d.edit,true);if(c.hasPointerCapture(d.id))c.releasePointerCapture(d.id);e.preventDefault();e.stopPropagation();return}if(this.view.walk){const key=e.key.toLowerCase();if(['w','a','s','d','arrowup','arrowdown','arrowleft','arrowright'].includes(key)){e.preventDefault();e.stopPropagation();if(!this.keys.has(key)){this.view.walk=walkMove(this.view.walk,Number(['w','arrowup'].includes(key))-Number(['s','arrowdown'].includes(key)),Number(['d','arrowright'].includes(key))-Number(['a','arrowleft'].includes(key)),.05,this.faces);this.draw()}this.keys.add(key);if(!this.animation)this.animation=requestAnimationFrame(t=>this.tick(t));return}if(key==='escape'){this.leaveWalk();this.options.onModeChange?.();return}}if(['ArrowLeft','ArrowRight','ArrowUp','ArrowDown','+','=','-','0'].includes(e.key)){e.preventDefault();e.stopPropagation();if(e.key==='0')this.reset();else if(['+','=','-'].includes(e.key))this.zoom(e.key==='-'?1/1.2:1.2);else{this.view.yaw=angle(this.view.yaw+(e.key==='ArrowRight'?-.15:e.key==='ArrowLeft'?.15:0));this.view.pitch=angle(this.view.pitch+(e.key==='ArrowDown'?.1:e.key==='ArrowUp'?-.1:0));this.draw()}}};
  }
  draw(){const c=this.canvas;if(!c.isConnected){this.dispose();return}const w=c.clientWidth,h=c.clientHeight;if(!w||!h||!this.bounds)return;const dpr=window.devicePixelRatio||1;if(c.width!==Math.round(w*dpr))c.width=Math.round(w*dpr);if(c.height!==Math.round(h*dpr))c.height=Math.round(h*dpr);
   const walking=!!this.view.walk,transparent=walking?false:this.view.transparent;
   const faces=this.visibleFaces().map(f=>({...f,points:walking?walkProject(f.points,this.view.walk,w,h,this.bounds.radius):f.points.map(p=>project(p,this.view,this.bounds,w,h))})).filter(f=>f.points.length>=3).sort((a,b)=>(Number(!!b.floor)-Number(!!a.floor))||a.points.reduce((s,p)=>s+p[2],0)/a.points.length-b.points.reduce((s,p)=>s+p[2],0)/b.points.length);
   if(this.renderer===undefined){try{this.renderer=new DepthRenderer(c)}catch(_){this.renderer=null}}
   c.dataset.faceCount=faces.length;c.dataset.worldBounds=JSON.stringify(frame(this.visibleFaces()));c.dataset.drawBounds=JSON.stringify(this.bounds);c.dataset.contextLost=String(this.renderer?.gl.isContextLost()||false);this.hits=faces.filter(f=>f.id||!f.architecture||!this.view.transparent);
   if(this.renderer)this.renderer.draw(faces,w,h,this.bounds.radius,transparent,this.view.edges);
   else{const g=c.getContext('2d');if(!g)return;g.setTransform(dpr,0,0,dpr,0,0);g.fillStyle='#f1f3ef';g.fillRect(0,0,w,h);for(const f of faces){g.beginPath();f.points.forEach((p,i)=>i?g.lineTo(p[0],p[1]):g.moveTo(p[0],p[1]));g.closePath();g.globalAlpha=f.architecture&&transparent?.24:1;g.fillStyle=f.color;g.fill();g.strokeStyle=f.selected?'#ac801a':'#78847c';g.lineWidth=f.selected?1.1:.6;if(f.edge_mask){g.beginPath();f.points.forEach((p,i)=>{if(f.edge_mask[i]){g.moveTo(p[0],p[1]);const q=f.points[(i+1)%f.points.length];g.lineTo(q[0],q[1]);}});}if(this.view.edges||f.selected)g.stroke()}g.globalAlpha=1}
   this.options.afterDraw?.(this);c.dataset.renderer=this.renderer?'depth':'basic';c.dataset.walking=String(walking);if(walking)c.dataset.walkPosition=JSON.stringify(this.view.walk.position);else delete c.dataset.walkPosition;
   c.setAttribute('aria-label',walking?'Walk inside · WASD or arrow keys to move · Drag to look · Escape to exit':`3D floor model, ${this.view.projection||'orthographic'}, ${Math.round(this.view.zoom*100)}% zoom. Drag to rotate 360 degrees, Shift-drag or middle-drag to pan. Scroll to zoom.`);
  }
  dispose(){if(this.animation)cancelAnimationFrame(this.animation);this.animation=null;this.keys?.clear();this.observer?.disconnect();this.renderer?.dispose();this.renderer=undefined;this.drag=null}
 }
 const api={Viewer,defaults,cleanEdges,planePoint,rotate,frame,project,gesture,inside,pick,walkBasis,cameraPoint,clipNear,walkProject,rayFor,raycast,walkMove};if(typeof module!=='undefined')module.exports=api;else window.BlockModelViewer=api;
})();
