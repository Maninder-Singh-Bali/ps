'use strict';
// Labels remain the same screen size through wheel zoom, panning and resizing.
(() => {
 const bound=new WeakMap();
 let objectsVisible=true;
 const names={wall:'Wall',window:'Window',door:'Door',sliding_door:'Sliding door',opening:'Opening',line:'Detail line',detail:'Outline',unknown:'Unclassified object',unclassified:'Unclassified object',sofa:'Sofa',chair:'Chair',table:'Table',bed:'Bed',storage:'Storage',refrigerator:'Refrigerator',comforter:'Comforter',pillar:'Pillar',fixture:'Fixture',appliance:'Appliance',desk:'Desk',plant:'Plant',rug:'Rug',stair:'Staircase'};
 function objectName(item){
  if(item.kind==='sofa')return `${item.seat_count?item.seat_count+'-seater ':''}${item.shape==='l'?'L-shaped ':''}sofa`;
  const preset=window.FurnitureLibrary?.presets.find(p=>p.id===item.preset_id);
  if(!preset&&item.kind==='table'){const label=(item.label||'').toLowerCase();if(label.includes('coffee table'))return 'Coffee table';if(label.includes('dining table'))return 'Dining table';if(label.includes('side table'))return 'Side table'}
  return preset?.label||names[item.kind]||'Unclassified object';
 }
 function overlap(a,b){return Math.max(0,Math.min(a.x+a.w,b.x+b.w)-Math.max(a.x,b.x))*Math.max(0,Math.min(a.y+a.h,b.y+b.h)-Math.max(a.y,b.y))}
 function labelPosition(anchor,w,h,occupied,viewport){
  const trials=[];
  for(const gap of [5,20,38,60])for(const [x,y] of [[anchor.x-w/2,anchor.bottom+gap],[anchor.right+gap,anchor.y-h/2],[anchor.left-gap-w,anchor.y-h/2],[anchor.x-w/2,anchor.top-gap-h]]){
   const row={x:Math.max(viewport.x+3,Math.min(viewport.x+viewport.w-w-3,x)),y:Math.max(viewport.y+3,Math.min(viewport.y+viewport.h-h-3,y)),w,h};
   row.score=(overlap(row,{x:anchor.left,y:anchor.top,w:anchor.right-anchor.left,h:anchor.bottom-anchor.top})*2+occupied.reduce((sum,b)=>sum+overlap(row,b),0))*100+Math.hypot(row.x+w/2-anchor.x,row.y+h/2-anchor.y);trials.push(row);
  }
  return trials.sort((a,b)=>a.score-b.score)[0];
 }
 function drawObjects(svg,group,scale){
  if(!objectsVisible)return;
  const rect=svg.getBoundingClientRect(),viewport={x:rect.left,y:rect.top,w:rect.width,h:rect.height},matrix=svg.getScreenCTM().inverse(),occupied=[...group.querySelectorAll('text')].map(e=>{const b=e.getBoundingClientRect();return{x:b.left,y:b.top,w:b.width,h:b.height}});
  const nodes=[...svg.querySelectorAll('[data-object-label],[data-plan-kind]')].filter(e=>!e.dataset.skipLabel&&(e.dataset.objectLabel||['wall','window','door','sliding_door','opening'].includes(e.dataset.planKind)));
  for(const el of nodes){
   const doorArc=el.dataset.planKind==='opening'&&[...el.querySelectorAll('path[d]')].some(p=>/[aA]/.test(p.getAttribute('d')));
   const label=el.dataset.objectLabel||(doorArc?'Door':names[el.dataset.planKind]),b=el.getBoundingClientRect();
   if(!label||!b.width&&!b.height||b.right<rect.left||b.left>rect.right||b.bottom<rect.top||b.top>rect.bottom)continue;
   const anchor={x:(b.left+b.right)/2,y:(b.top+b.bottom)/2,left:b.left,right:b.right,top:b.top,bottom:b.bottom};
   const placed=labelPosition(anchor,label.length*5.4+10,17,occupied,viewport);occupied.push(placed);
   const p=new DOMPoint(placed.x,placed.y).matrixTransform(matrix),a=new DOMPoint(anchor.x,anchor.y).matrixTransform(matrix);
   const g=document.createElementNS(group.namespaceURI,'g');g.setAttribute('class','plan-object-label');g.setAttribute('data-label-kind',el.dataset.objectKind||el.dataset.planKind||'object');g.setAttribute('transform',`translate(${p.x} ${p.y}) scale(${1/scale})`);
   const line=document.createElementNS(group.namespaceURI,'line');line.setAttribute('x1',(a.x-p.x)*scale);line.setAttribute('y1',(a.y-p.y)*scale);line.setAttribute('x2',placed.w/2);line.setAttribute('y2',placed.h/2);g.append(line);
   const box=document.createElementNS(group.namespaceURI,'rect');box.setAttribute('width',placed.w);box.setAttribute('height',placed.h);box.setAttribute('rx',3);g.append(box);
   const text=document.createElementNS(group.namespaceURI,'text');text.setAttribute('x',5);text.setAttribute('y',12);text.textContent=label;g.append(text);group.append(g);
  }
 }
 function attach(svg,rooms,plan,selected){
  let binding=bound.get(svg);
  if(!binding){
   binding={};bound.set(svg,binding);
   binding.draw=()=>{
    if(!svg.isConnected){binding.resize.disconnect();binding.observe.disconnect();bound.delete(svg);return}
    svg.querySelector('.plan-section-labels')?.remove();
    const scale=Math.abs(svg.getScreenCTM()?.a||1),rows=binding.rooms||[],a=binding.plan;
    const group=document.createElementNS('http://www.w3.org/2000/svg','g');group.setAttribute('class','plan-section-labels');group.setAttribute('pointer-events','none');
    for(const r of rows){
     if(r.bbox[2]*a.width*scale<72||r.bbox[3]*a.height*scale<32)continue;
     const text=document.createElementNS(group.namespaceURI,'text');text.setAttribute('x',r.bbox[0]*a.width+8/scale);text.setAttribute('y',r.bbox[1]*a.height+17/scale);text.setAttribute('font-size',12/scale);text.setAttribute('stroke-width',4/scale);text.setAttribute('class',r.id===binding.selected?'selected':'');text.textContent=r.name;group.append(text);
    }
    svg.append(group);drawObjects(svg,group,scale);
   };
   binding.observe=new MutationObserver(binding.draw);binding.observe.observe(svg,{attributes:true,attributeFilter:['viewBox']});
   binding.resize=new ResizeObserver(binding.draw);binding.resize.observe(svg);
  }
  Object.assign(binding,{rooms,plan,selected});binding.draw();
 }
 window.PlanLabels={attach,objectName,get objectsVisible(){return objectsVisible},setObjects(value){objectsVisible=!!value;document.querySelectorAll('#block-plan,#camera-plan').forEach(svg=>bound.get(svg)?.draw())}};
 if(typeof module!=='undefined')module.exports={labelPosition,overlap};
})();
