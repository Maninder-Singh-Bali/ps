const fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const root=path.join(__dirname,'..'),library=require('../static/furniture-library.js');
const context={window:{},fetch:async()=>({ok:true,json:async()=>JSON.parse(fs.readFileSync(path.join(root,'static/furniture-meshes.json'),'utf8'))})};
vm.createContext(context);vm.runInContext(fs.readFileSync(path.join(root,'static/furniture-meshes.js'),'utf8'),context);
(async()=>{
 await context.window.FurnitureMeshes.load();const plan={width:1000,height:600};
 const items=library.presets.map(p=>library.create(p.id,[.1,.1,.8,.8],plan,{width_m:10,depth_m:6},[.5,.5],p.id));
 for(const angle of [0,30,90,170,270])for(const side of ['left','right']){
  const v=library.create('sofa-l',[.1,.1,.8,.8],plan,null,[.5,.5],`L-${angle}-${side}`);v.angle=angle;v.return_side=side;library.seats(v,7);items.push(v);
 }
 for(const count of [1,2,6,12]){const v=library.create('sofa-2',[.1,.1,.8,.8],plan,null,[.5,.5],`sofa-${count}`);library.seats(v,count);items.push(v)}
 const chair=library.create('chair',[.1,.1,.8,.8],plan,null,[.5,.5],'group');
 chair.chair_modules={width:chair.width,depth:chair.depth,columns:3,rows:2};chair.width*=3*1.15-.15;chair.depth*=2*1.15-.15;chair.angle=37;items.push(chair);
 for(const item of [...items])for(const [flip_x,flip_y] of [[true,false],[false,true],[true,true]])items.push({...item,id:item.id+'-'+flip_x+'-'+flip_y,flip_x,flip_y});
 process.stdout.write(JSON.stringify({plan,models:items.map(item=>({item,components:context.window.FurnitureMeshes.components(item),mesh:context.window.FurnitureMeshes.mesh(item,plan)}))}));
})().catch(e=>{console.error(e);process.exitCode=1});
