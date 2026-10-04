'use strict';
(() => {
 let data=null,pending=null;
 async function load(){
  if(data)return data;
  if(!pending)pending=fetch('/furniture-meshes.json').then(r=>{if(!r.ok)throw Error('Could not load furniture models.');return r.json()}).then(v=>data=v).catch(e=>{pending=null;throw e});
  return pending;
 }
 const component=(x,y,z,w,d,h,material='fabric',role='body',type='box')=>({bounds:[x,y,z,w,d,h],material,role,type});
 function sofa(item){
  const isL=item.shape==='l',m=item.sofa_modules||{},total=Math.max(1,Math.min(12,Math.trunc(item.seat_count||3))),main=m.main_seats??(isL?Math.max(2,total-1):total),ret=m.return_seats??(isL?Math.max(1,total-main):0);
  const lw=Math.min(1,(m.leg_width??item.width*.4)/item.width),ld=isL?Math.min(1,(m.leg_depth??item.depth*.4)/item.depth):1,px=isL?(1-lw)/(main-1):1/main,py=(1-ld)/Math.max(1,ret),p=[];
  const add=(x,y,z,w,d,h,material='fabric',role='body',type='box')=>{if(w>0&&d>0&&h>0)p.push(component(x,y,z,w,d,h,material,role,type))};
  const base=(x,y,w,d)=>{add(x,y,.15,w,d,.3);for(const a of [x+w*.1,x+w*.84])for(const b of [y+d*.1,y+d*.84])add(a,b,0,w*.06,d*.06,.15,'wood','leg')};
  const seat=(x,y,w,d)=>add(x,y,.45,w,d,.2,'cushion','seat','bevel');
  if(isL){
   base(0,1-ld,1,ld);base(0,0,lw,1-ld);const bx=lw*.13,by=ld*.13;
   add(0,0,.4,bx,1,.6,'fabric','back');add(bx,1-by,.4,1-bx,by,.6,'fabric','back');add(0,0,.45,lw,by,.32,'fabric','arm');add(1-bx,1-ld,.45,bx,ld,.32,'fabric','arm');
   seat(bx+.02*lw,1-ld+.03*ld,lw-bx-.04*lw,ld-by-.06*ld);
   for(let i=0;i<main-1;i++){const x=lw+i*px;seat(x+.035*px,1-ld+.03*ld,px*.93-(i===main-2?bx:0),ld-by-.06*ld)}
   for(let i=0;i<ret;i++){const y=i*py;seat(bx+.02*lw,y+.035*py+(i===0?by:0),lw-bx-.04*lw,py*.93-(i===0?by:0))}
   if(item.return_side==='right')for(const q of p)q.bounds[0]=1-q.bounds[0]-q.bounds[3];
  }else{
   base(0,0,1,1);const arm=Math.min(.09,.18/main);add(0,0,.4,1,.15,.6,'fabric','back');add(0,.15,.4,arm,.85,.38,'fabric','arm');add(1-arm,.15,.4,arm,.85,.38,'fabric','arm');const pitch=(1-2*arm)/main;
   for(let i=0;i<main;i++)seat(arm+i*pitch+pitch*.035,.18,pitch*.93,.78);
  }
  const seatZ=z=>z<=.65?z*(.45/.85)/.65:.45/.85+(z-.65)*(1-.45/.85)/.35;
  for(const q of p){const z=q.bounds[2],h=q.bounds[5];q.bounds[2]=seatZ(z);q.bounds[5]=seatZ(z+h)-seatZ(z)}
  return p;
 }
 function components(item){
  if(item.kind==='sofa')return sofa(item);
  if(item.preset_id==='staircase-spiral'){
   const n=Math.max(8,Math.ceil((item.height_m||3)/.18)),turn=Math.PI*11/6,parts=[component(.46,.46,0,.08,.08,1,'metal','column','cylinder')];
   for(let i=0;i<n;i++){const a=i*turn/n,b=(i+1)*turn/n;parts.push({...component(0,0,Math.max(0,(i+1)/n-.025),1,1,.025,'wood','step','sector'),start:a,end:b},component(.5+.46*Math.cos(b)-.012,.5+.46*Math.sin(b)-.012,(i+1)/n,.024,.024,.25,'metal','railing','cylinder'))}return parts;
  }
  if(item.preset_id==='staircase-l'){
   const n=Math.max(4,Math.ceil((item.height_m||3)/.18)),first=Math.ceil(n*.65),last=n-first,w=.48,d=.28;
   return [...Array.from({length:first},(_,i)=>component(0,d+i*(1-d)/first,0,w,(1-d)/first,(first-i)/n,'stone','step')),component(0,0,0,w,d,first/n,'stone','landing'),...Array.from({length:last},(_,i)=>component(w+i*(1-w)/last,0,0,(1-w)/last,d,(first+i+1)/n,'stone','step'))];
  }
  if(item.kind==='stair'){const n=Math.max(2,Math.ceil((item.height_m||3)/.18));return Array.from({length:n},(_,i)=>component(0,i/n,0,1,1/n,(n-i)/n,'stone','step'))}
  let key=data.recipes[item.preset_id]?item.preset_id:(data.defaults[item.kind]||'unknown');
  if(item.shape==='round'&&['table','pillar'].includes(item.kind))key=item.kind==='table'?'table-round':'pillar-round';
  return data.recipes[key];
 }
 function instances(item,plan){
  const m=item.chair_modules;if(item.kind!=='chair'||!m)return [item];
  const a=(item.angle||0)*Math.PI/180,c=Math.cos(a),s=Math.sin(a),out=[];
  for(let row=0;row<m.rows;row++)for(let col=0;col<m.columns;col++){
   const x=(-item.width/2+m.width/2+col*m.width*1.15)*plan.width,y=(-item.depth/2+m.depth/2+row*m.depth*1.15)*plan.height;
   out.push({...item,chair_modules:null,width:m.width,depth:m.depth,x:item.x+(x*c-y*s)/plan.width,y:item.y+(x*s+y*c)/plan.height});
  }return out;
 }
 function primitive(p){
  let [x,y,z,w,d,h]=p.bounds;const axis=p.axis||'z';if(axis==='y')[y,z,d,h]=[z,y,h,d];
  const angles=p.type==='sector'?Array.from({length:4},(_,i)=>p.start+(p.end-p.start)*i/3):[];
  const poly=p.type==='sector'?[...angles.map(a=>[.5+.46*Math.cos(a),.5+.46*Math.sin(a)]),...angles.slice().reverse().map(a=>[.5+.055*Math.cos(a),.5+.055*Math.sin(a)])]:p.type==='cylinder'?Array.from({length:12},(_,i)=>[(Math.cos(i*Math.PI/6)+1)/2,(Math.sin(i*Math.PI/6)+1)/2]):p.type==='bevel'?[[.1,0],[.9,0],[1,.1],[1,.9],[.9,1],[.1,1],[0,.9],[0,.1]]:[[0,0],[1,0],[1,1],[0,1]],scale=p.top_scale??1;
  const bottom=poly.map(([a,b])=>[x+a*w,y+b*d,z]),top=poly.map(([a,b])=>[x+(.5+(a-.5)*scale)*w,y+(.5+(b-.5)*scale)*d,z+h]);
  let faces=[[bottom,.65],[top,1],...poly.map((_,i)=>[[bottom[i],bottom[(i+1)%poly.length],top[(i+1)%poly.length],top[i]],.76+.12*(i%3)/2])];
  if(axis==='y')faces=faces.map(([pts,shade])=>[pts.map(([a,b,c])=>[a,c,b]),shade]);return faces;
 }
 function mesh(item,plan){
  if(!data)throw Error('Furniture models have not loaded.');
  const out=[];
  for(const unit of instances(item,plan)){
   const a=(unit.angle||0)*Math.PI/180,c=Math.cos(a),s=Math.sin(a),W=unit.width*plan.width,D=unit.depth*plan.height,H=unit.height_m??(unit.kind==='table'?.45:.8);
   for(const part of components(unit))for(const [points,shade] of primitive(part))out.push({points:points.map(([x,y,z])=>{x=((unit.flip_x?1-x:x)-.5)*W;y=((unit.flip_y?1-y:y)-.5)*D;return [unit.x+(x*c-y*s)/plan.width,unit.y+(x*s+y*c)/plan.height,z*H+(unit.elevation_m||0)]}),color:data.materials[part.material].map(v=>Math.floor(v*shade+.5)),part:part.role});
  }return out;
 }
 function building(floors,plan,blocks,selection={},visible=()=>true){
  floors=floors.filter(({scene})=>!scene.selection_required);
  if(!floors.length)return {faces:[],levels:[]};
  const base=floors[0].scene,unit=(base.bounds[2]-base.bounds[0])*plan.width/base.width;
  const faces=[],levels=[];let elevation=0;
  for(const [index,{scene,room_id}] of floors.entries()){
   const z=elevation; elevation+=(scene.height||3)*unit;
   if(!visible(scene.floor)||scene.selection_required)continue;
   const b=scene.bounds,sx=(b[2]-b[0])*plan.width/scene.width,sy=(b[3]-b[1])*plan.height/scene.depth;
   levels.push({name:scene.floor,elevation:z/unit});
   const point=p=>[p[0]*sx,p[1]*sy,z+p[2]*unit];
   for(const s of scene.surfaces){
    if(['block','furniture'].includes(s.kind))continue;
    const chosen=!!s.source_id&&(selection.wall===s.source_id||selection.multi?.includes('w:'+s.source_id));
    const color=chosen?s.color.map((c,i)=>Math.round(c*.4+[244,203,100][i]*.6)):s.color;
    faces.push({id:s.source_id,sourceId:s.source_id,roomId:room_id,floorName:scene.floor,selected:chosen,points:s.points.map(point),surfaceKind:s.kind,architecture:s.kind!=='floor',floor:s.kind==='floor',color:`rgb(${color.join(',')})`});
   }
   // Ceiling underside follows the slab above, including open-to-below courtyards.
   const lid=floors[index+1]?.scene||scene,lb=lid.bounds,lx=(lb[2]-lb[0])*plan.width/lid.width,ly=(lb[3]-lb[1])*plan.height/lid.depth;
   for(const surface of lid.surfaces.filter(f=>f.kind==='floor'))faces.push({roomId:room_id,floorName:scene.floor,ceiling:true,architecture:true,surfaceKind:'ceiling',points:surface.points.map(p=>[p[0]*lx,p[1]*ly,z+((scene.height||3)-.01)*unit]),color:'rgb(239,236,225)'});
   for(const {v,owner} of blocks.filter(({owner,v})=>owner.floor===scene.floor&&(!scene.construction_selection||(scene.products.some(p=>p.object_key===owner.id+':'+v.id)&&window.ConstructionArea?.includesBlock(v,plan,scene.construction_selection))))){
    const chosen=owner.id===selection.room&&v.id===selection.object||selection.multi?.includes('f:'+owner.id+':'+v.id);
    for(const f of mesh(v,plan)){
     const color=chosen?f.color.map((c,i)=>Math.round(c*.45+[244,203,100][i]*.55)):f.color;
     faces.push({id:v.id,roomId:owner.id,floorName:scene.floor,selected:chosen,points:f.points.map(p=>[(p[0]-b[0])*plan.width,(p[1]-b[1])*plan.height,z+p[2]*unit]),color:`rgb(${color.join(',')})`});
    }
   }
  }
  return {faces,levels};
 }
 window.FurnitureMeshes={load,mesh,components,instances,building};
})();
