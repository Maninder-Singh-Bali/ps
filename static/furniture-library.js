'use strict';
(() => {
 const presets=[
  ['sofa-1','1-seater sofa','sofa',1,.95,.9,.85],
  ['sofa-2','2-seater sofa','sofa',2,1.6,.9,.85],
  ['sofa-3','3-seater sofa','sofa',3,2.2,.9,.85],
  ['sofa-l','L-shaped sofa','sofa',4,2.6,1.8,.85],
  ['chair','Chair','chair',null,.55,.55,.85],
  ['refrigerator','Refrigerator','refrigerator',null,.75,.75,1.8],
  ['bed-single','Single bed','bed',null,.95,2,.55],
  ['bed-double','Double bed','bed',null,1.5,2,.55],
  ['bed-queen','Queen bed','bed',null,1.6,2,.55],
  ['bed-king','King bed','bed',null,1.8,2,.55],
  ['comforter','Comforter','comforter',null,1.6,1.8,.08],
  ['kitchen-table','Kitchen table','table',null,1.5,.8,.75],
  ['coffee-table','Coffee table','table',null,1,.6,.45],
  ['staircase','Staircase','stair',null,1,3,3],
  ['staircase-l','L-shaped staircase','stair',null,2.3,3.9,3],
  ['pillar-square','Square pillar','pillar',null,.4,.4,3],
  ['pillar-round','Round pillar','pillar',null,.4,.4,3],
  ['armchair','Armchair','chair',null,.85,.85,.9],
  ['chaise','Chaise lounge','sofa',1,.8,1.7,.8],
  ['ottoman','Ottoman','chair',null,.65,.65,.45],
  ['bar-stool','Bar stool','chair',null,.45,.45,.65],
  ['dining-4','Dining set · 4 chairs','table',null,1.8,1.8,.75],
  ['dining-6','Dining set · 6 chairs','table',null,2.4,1.8,.75],
  ['table-round','Round table','table',null,1.2,1.2,.75],
  ['nightstand','Nightstand','storage',null,.5,.45,.55],
  ['wardrobe','Wardrobe','storage',null,1.8,.6,2.2],
  ['bookcase','Bookcase','storage',null,1,.35,1.8],
  ['tv-unit','TV unit','storage',null,1.6,.4,.6],
  ['desk','Desk','desk',null,1.2,.6,.75],
  ['kitchen-counter','Kitchen counter','storage',null,1.8,.6,.9],
  ['kitchen-island','Kitchen island','table',null,1.8,.9,.9],
  ['kitchen-sink','Sink cabinet','fixture',null,.8,.6,.9],
  ['cooker','Cooker / hob','appliance',null,.6,.6,.9],
  ['dishwasher','Dishwasher','appliance',null,.6,.6,.85],
  ['washer','Washing machine','appliance',null,.6,.65,.85],
  ['toilet','Toilet','fixture',null,.4,.7,.8],
  ['basin','Washbasin','fixture',null,.6,.5,.85],
  ['bathtub','Bathtub','fixture',null,.75,1.7,.6],
  ['shower','Shower enclosure','fixture',null,.9,.9,2],
  ['staircase-spiral','Spiral staircase','stair',null,2,2,3],
  ['painting-landscape','Landscape painting','decor',null,1,.045,.65],
  ['painting-portrait','Portrait painting','decor',null,.65,.045,1],
  ['painting-square','Square painting','decor',null,.8,.045,.8],
  ['floor-lamp','Floor lamp','light',null,.45,.45,1.65],
  ['table-lamp','Table lamp','light',null,.3,.3,.5],
  ['pendant-light','Pendant light','light',null,.45,.45,.85],
  ['ceiling-light','Ceiling light','light',null,.5,.5,.15],
  ['wall-light','Wall light','light',null,.22,.18,.4],
  ['chandelier','Chandelier','light',null,.9,.9,.85],
  ['plant','Plant','plant',null,.5,.5,1.2],
  ['rug','Rug','rug',null,2,3,.02]
 ].map(([id,label,kind,seats,width,depth,height])=>({id,label,kind,seats,width,depth,height,shape:id==='sofa-l'?'l':['pillar-round','table-round','plant','bar-stool','staircase-spiral','floor-lamp','table-lamp','pendant-light','ceiling-light','chandelier'].includes(id)?'round':'box'}));
 // Independently drawn schematic symbols; conventions checked against:
 // https://help.roomsketcher.com/hc/en-us/articles/4410088626193-Blueprint-Symbols-Explained
 // https://www.roomsketcher.com/blog/floor-plan-symbols/
 // Dimensions are editable example defaults, never measurements inferred from a scan.
 const categories={Living:['sofa-1','sofa-2','sofa-3','sofa-l','chair','armchair','chaise','ottoman','coffee-table','tv-unit','plant','rug'],Bedroom:['bed-single','bed-double','bed-queen','bed-king','comforter','nightstand','wardrobe'],Dining:['kitchen-table','dining-4','dining-6','table-round','bar-stool'],Kitchen:['refrigerator','kitchen-counter','kitchen-island','kitchen-sink','cooker','dishwasher'],Bathroom:['toilet','basin','bathtub','shower','washer'],Office:['desk','bookcase'],Art:['painting-landscape','painting-portrait','painting-square'],Lighting:['floor-lamp','table-lamp','pendant-light','ceiling-light','wall-light','chandelier'],Structure:['pillar-square','pillar-round','staircase','staircase-l','staircase-spiral']};
 for(const p of presets)p.category=Object.keys(categories).find(k=>categories[k].includes(p.id))||'Living';
 function symbol(v){
  if(v.flip_x||v.flip_y)return `<g transform="translate(${v.flip_x?100:0} ${v.flip_y?100:0}) scale(${v.flip_x?-1:1} ${v.flip_y?-1:1})">${symbol({...v,flip_x:false,flip_y:false})}</g>`;
  const rect=(x,y,w,h,rx=3)=>`<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="${rx}"/>`;
  if(v.kind==='chair'&&v.chair_modules){
   const m=v.chair_modules,unit=symbol({...v,chair_modules:null}),sx=m.width/v.width,sy=m.depth/v.depth;
   return Array.from({length:m.rows},(_,row)=>Array.from({length:m.columns},(_,col)=>`<g data-chair-instance="true" transform="translate(${col*m.width*1.15/v.width*100} ${row*m.depth*1.15/v.depth*100}) scale(${sx} ${sy})">${unit}</g>`).join('')).join('');
  }
  const id=v.preset_id||v.id;
  if(id==='staircase-spiral'){
   const spokes=Array.from({length:17},(_,i)=>{const a=i/16*Math.PI*11/6;return `<path d="M${50+7*Math.cos(a)} ${50+7*Math.sin(a)}L${50+45*Math.cos(a)} ${50+45*Math.sin(a)}"/>`}).join('');
   return '<circle cx="50" cy="50" r="46"/><circle cx="50" cy="50" r="7"/>'+spokes+'<path class="stair-up" d="M83 50A33 33 0 0 1 21.42 66.5M19 57L21.42 66.5 31 65"/>';
  }
  if(v.kind==='decor')return rect(5,28,90,44,0)+rect(11,35,78,30,0)+'<path d="M11 61L32 42 50 57 66 45 89 61"/><circle cx="72" cy="42" r="4"/>';
  if(v.kind==='light'){
   if(id==='wall-light')return rect(16,5,68,13,0)+'<path d="M50 18V34M18 34H82L92 88H8Z"/>';
   const ring='<circle cx="50" cy="50" r="39"/><circle cx="50" cy="50" r="9"/>';
   if(id==='chandelier')return ring+[0,60,120,180,240,300].map(a=>{const x=50+32*Math.cos(a*Math.PI/180),y=50+32*Math.sin(a*Math.PI/180);return `<path d="M50 50L${x} ${y}"/><circle cx="${x}" cy="${y}" r="9"/>`}).join('');
   return ring+(id==='ceiling-light'?'<path d="M23 23L77 77M77 23L23 77"/>':id==='pendant-light'?'<circle cx="50" cy="50" r="28"/>':'<path d="M50 11V89M11 50H89"/>');
  }
  if(id==='staircase-l')return '<path d="M4 4H96V28H48V96H4Z"/>'+Array.from({length:8},(_,i)=>`<path d="M4 ${36+i*8}H48"/>`).join('')+Array.from({length:4},(_,i)=>`<path d="M${58+i*10} 4V28"/>`).join('')+'<path class="stair-up" d="M26 86V16H86M77 9L86 16 77 23"/>';
  if(id==='staircase'||v.kind==='stair')return rect(4,2,92,96,0)+Array.from({length:11},(_,i)=>`<path d="M4 ${10+i*8}H96"/>`).join('')+'<path class="stair-up" d="M50 86V14M39 27L50 14 61 27"/>';
  if(id==='toilet')return rect(23,5,54,23)+'<path d="M28 28H72V62C72 103 28 103 28 62Z"/><ellipse cx="50" cy="58" rx="16" ry="26"/>';
  if(id==='basin'||id==='kitchen-sink')return rect(4,7,92,86)+rect(13,26,74,54,13)+'<circle cx="50" cy="55" r="4"/><path d="M50 14V34M40 17H60"/>';
  if(id==='bathtub')return rect(8,3,84,94,18)+rect(17,13,66,75,22)+'<circle cx="50" cy="22" r="3"/>';
  if(id==='shower')return rect(5,5,90,90,0)+'<path d="M5 5 95 95M95 5 5 95M40 5V18H60"/><circle cx="50" cy="50" r="4"/>';
  if(id==='cooker')return rect(5,5,90,90)+[ [29,30],[71,30],[29,70],[71,70] ].map(([x,y])=>`<circle cx="${x}" cy="${y}" r="15"/>`).join('');
  if(id==='washer')return rect(5,5,90,90)+rect(10,10,80,15)+'<circle cx="50" cy="60" r="26"/>';
  if(id==='dishwasher')return rect(5,5,90,90)+'<path d="M5 23H95M37 14H63M20 40H80M20 55H80M20 70H80"/>';
  if(id==='wardrobe'||id==='bookcase'||id==='kitchen-counter'||id==='nightstand')return rect(5,5,90,90,0)+'<path d="M50 5V95M5 35H95M5 65H95"/>';
  if(id==='tv-unit')return rect(5,35,90,50)+rect(10,12,80,15,0)+'<path d="M50 27V35M50 35V85"/>';
  if(id==='desk')return rect(4,10,92,68)+rect(65,16,23,53)+'<path d="M28 78V96H58V78"/>';
  if(id==='dining-4'||id==='dining-6'){const n=id==='dining-4'?2:3;return rect(25,15,50,70,8)+Array.from({length:n},(_,i)=>rect(3,17+i*68/n,17,68/n-7)+rect(80,17+i*68/n,17,68/n-7)).join('')}
  if(id==='rug')return rect(6,6,88,88,0)+rect(12,12,76,76,0)+'<path d="M6 20H94M6 80H94"/>';
  if(id==='plant')return '<circle cx="50" cy="50" r="42"/><path d="M50 80V22M50 45Q15 10 23 50L50 65Q86 27 73 23Z"/>';
  if(id==='table-round'||id==='bar-stool'||id==='ottoman')return '<circle cx="50" cy="50" r="42"/><circle cx="50" cy="50" r="34"/>';
  if(v.kind==='pillar')return v.shape==='round'?'<circle cx="50" cy="50" r="43"/>':rect(7,7,86,86,0);
  if(v.kind==='sofa'&&v.sofa_modules){
   const m=v.sofa_modules,l=v.shape==='l',X=100/v.width,Y=100/v.depth;
   const lw=m.leg_width*X,ld=m.leg_depth*Y,px=m.pitch_width*X,py=m.pitch_depth*Y;
   const ix=lw*.1,iy=ld*.1;
   let art=l?`<path d="M0 0H${lw}V${100-ld}H100V100H0Z"/>`:rect(0,0,100,100,0);
   const cushion=(x,y,w,h)=>`<rect data-sofa-seat="true" x="${x}" y="${y}" width="${w}" height="${h}" rx="${ix}" ry="${iy}"/>`;
   if(l){
    art+=cushion(ix,100-ld+iy,lw-2*ix,ld-2*iy);
    for(let i=0;i<m.main_seats-1;i++)art+=cushion(lw+i*px+ix,100-ld+iy,px-2*ix,ld-2*iy);
    for(let i=0;i<m.return_seats;i++)art+=cushion(ix,i*py+iy,lw-2*ix,py-2*iy);
   }else{
    art+=rect(ix,iy,100-2*ix,iy,0)+rect(ix*.2,iy*2,ix*.6,100-iy*3,0)+rect(100-ix*.8,iy*2,ix*.6,100-iy*3,0);
    for(let i=0;i<m.main_seats;i++)art+=cushion(i*px+ix,iy*3,px-2*ix,100-4*iy);
   }
   return l&&v.return_side==='right'?`<g transform="translate(100 0) scale(-1 1)">${art}</g>`:art;
  }
  if(v.kind==='sofa'){
   const n=Math.max(1,Math.min(12,v.seat_count||v.seats||3)),bottom=v.shape==='l'?55:90;
   if(v.shape==='l'){const path='<path d="M4 4H40V60H96V96H4Z"/>'+Array.from({length:n},(_,i)=>rect(9+i*82/n,67,82/n-2,22)).join('')+rect(10,10,23,49);return v.return_side==='right'?`<g transform="translate(100 0) scale(-1 1)">${path}</g>`:path}
   return rect(4,4,92,92,7)+rect(12,10,76,12)+rect(7,23,8,bottom-23)+rect(85,23,8,bottom-23)+Array.from({length:n},(_,i)=>rect(17+i*66/n,26,66/n-2,bottom-28)).join('')+(v.shape==='l'?rect(v.return_side==='right'?62:17,55,21,36):'');
  }
  if(v.kind==='bed'){const n=(v.preset_id||v.id)==='bed-single'?1:2;return rect(5,3,90,94)+rect(8,7,84,7)+Array.from({length:n},(_,i)=>rect(12+i*78/n,19,78/n-5,20)).join('')+rect(9,43,82,50)+'<path d="M9 52H91"/>'}
  if(v.kind==='chair')return rect(18,7,64,20,7)+rect(14,32,72,52,9)+'<path d="M14 44H7V74M86 44H93V74M23 84V95M77 84V95"/>';
  if(v.kind==='refrigerator')return rect(10,5,80,90,3)+'<path d="M10 36H90M78 16V27M78 46V67"/>';
  if(v.kind==='comforter')return '<path d="M8 8Q25 2 50 8T92 8V92Q75 98 50 92T8 92ZM8 23Q25 17 50 23T92 23M30 24V92M61 24V92"/>';
  return rect(6,10,88,80,6)+'<path d="M15 15V85M85 15V85"/>';
 }
 function create(id,b,plan,dimensions,position,uid){
  const p=presets.find(v=>v.id===id);if(!p)throw Error('Choose a furniture shape from the library.');
  let width,depth;
  if(dimensions){width=p.width/dimensions.width_m*b[2];depth=p.depth/dimensions.depth_m*b[3]}
  else{const scale=Math.min(b[2]*plan.width*.4/(['light','decor'].includes(p.kind)?2:p.width),b[3]*plan.height*.4/(['light','decor'].includes(p.kind)?2:p.depth));width=p.width*scale/plan.width;depth=p.depth*scale/plan.height}
  const v={id:uid,preset_id:p.id,kind:p.kind,label:p.label,seat_count:p.seats,shape:p.shape,return_side:'left',x:position?.[0]??b[0]+b[2]/2,y:position?.[1]??b[1]+b[3]/2,width:Math.max(.005,Math.min(1,width)),depth:Math.max(.005,Math.min(1,depth)),height_m:p.height,angle:0,source:'furniture_library'};
  if(v.kind==='decor')v.elevation_m=1.2;
  if(v.kind==='light')v.elevation_m=({'table-lamp':.75,'pendant-light':2.15,'ceiling-light':2.85,'wall-light':1.6,'chandelier':2.15})[p.id]||0;
  if(v.kind==='sofa')v.sofa_modules=modules(v);
  return consistentSofa(v,plan);
 }
 function seats(item,value){delete item.sofa_modules;item.seat_count=value===''?null:Number(value);if(item.kind==='sofa'&&item.seat_count&&/^(\d+-seater (L-shaped )?sofa|L-shaped sofa)$/.test(item.label))item.label=`${item.seat_count}-seater ${item.shape==='l'?'L-shaped ':''}sofa`;return item}
 function modules(item){
  if(item.sofa_modules)return structuredClone(item.sofa_modules);
  const l=item.shape==='l',total=Math.max(l?3:1,Math.min(12,item.seat_count||(l?4:3))),main=l?total-1:total;
  return {main_seats:main,return_seats:l?1:0,leg_width:item.width*(l?.4:1/main),leg_depth:item.depth*(l?.4:1),pitch_width:item.width*(l?.6/(main-1):1/main),pitch_depth:item.depth*(l?.6:1)};
 }
 function consistentSofa(item,plan){
  if(item.kind!=='sofa'||item.shape!=='l')return item;
  const m=modules(item),W=plan.width,H=plan.height;
  // One square seat module in source-plan space, shared by both legs.
  // Fit within the current footprint rather than expanding into neighbouring objects.
  const size=Math.min(item.width*W/m.main_seats,item.depth*H/(m.return_seats+1));
  const width=size*m.main_seats/W,depth=size*(m.return_seats+1)/H;
  const close=(a,b)=>Math.abs(a-b)<1e-10;
  if(item.sofa_modules&&close(m.leg_width*W,size)&&close(m.leg_depth*H,size)&&close(m.pitch_width*W,size)&&close(m.pitch_depth*H,size))return item;
  const out=structuredClone(item);out.width=width;out.depth=depth;
  out.sofa_modules={main_seats:m.main_seats,return_seats:m.return_seats,leg_width:size/W,leg_depth:size/H,pitch_width:size/W,pitch_depth:size/H};
  out.seat_count=m.main_seats+m.return_seats;
  if(out.physical_size){out.physical_size.width*=width/item.width;out.physical_size.depth*=depth/item.depth}
  return out;
 }
 function chairInstances(item,plan){
  const m=item.chair_modules;if(item.kind!=='chair'||!m)return [item];
  const a=item.angle*Math.PI/180,c=Math.cos(a),s=Math.sin(a),result=[];
  for(let row=0;row<m.rows;row++)for(let col=0;col<m.columns;col++){
   const x=(-item.width/2+m.width/2+col*m.width*1.15)*plan.width,y=(-item.depth/2+m.depth/2+row*m.depth*1.15)*plan.height;
   result.push({...item,chair_modules:null,width:m.width,depth:m.depth,x:item.x+(x*c-y*s)/plan.width,y:item.y+(x*s+y*c)/plan.height});
  }
  return result;
 }
 function quantityLabel(v){return v?.chair_modules?`${v.chair_modules.columns*v.chair_modules.rows} chairs`:v?.sofa_modules?`${v.seat_count} seat${v.seat_count===1?'':'s'}`:''}
 function scaleModules(item,x,y){if(item.sofa_modules){for(const key of ['leg_width','pitch_width'])item.sofa_modules[key]*=x;for(const key of ['leg_depth','pitch_depth'])item.sofa_modules[key]*=y}if(item.chair_modules){item.chair_modules.width*=x;item.chair_modules.depth*=y}}
 function duplicate(item,plan,id){
  const copy=structuredClone(item);copy.id=id;copy.label=item.label+' copy';copy.asset_id=null;
  copy.x=Math.max(0,Math.min(1,item.x+(item.x>.95?-1:1)*10/plan.width));
  copy.y=Math.max(0,Math.min(1,item.y+(item.y>.95?-1:1)*10/plan.height));
  return copy;
 }
 function scale(item,factor){
  if(!Number.isFinite(factor)||factor<=0)throw Error('Enter a scale greater than 0%.');
  const copy=structuredClone(item);copy.width*=factor;copy.depth*=factor;
  if(copy.width<.005||copy.depth<.005||copy.width>1||copy.depth>1)throw Error('This scale exceeds the supported block size.');
  if(copy.height_m!=null){copy.height_m*=factor;if(copy.height_m<.01||copy.height_m>5)throw Error('Scaled height must be between 0.01 and 5 metres.')}
  if(copy.physical_size){copy.physical_size.width*=factor;copy.physical_size.depth*=factor}
  scaleModules(copy,factor,factor);
  return copy;
 }
 function transform(item,plan,handle,start,point,snap=true){
  item=consistentSofa(item,plan);
  const out=structuredClone(item),cx=item.x*plan.width,cy=item.y*plan.height,a=item.angle*Math.PI/180,c=Math.cos(a),s=Math.sin(a);
  if(handle==='rotate'){
   let angle=item.angle+(Math.atan2(point[1]-cy,point[0]-cx)-Math.atan2(start[1]-cy,start[0]-cx))*180/Math.PI;
   if(snap)angle=Math.round(angle/10)*10;out.angle=(angle%360+360)%360;return out;
  }
  const sides={nw:[-1,-1],n:[0,-1],ne:[1,-1],e:[1,0],se:[1,1],s:[0,1],sw:[-1,1],w:[-1,0]},side=sides[handle];if(!side)return out;
  const [sx,sy]=side,W=item.width*plan.width,D=item.depth*plan.height,dx=point[0]-start[0],dy=point[1]-start[1],lx=dx*c+dy*s,ly=-dx*s+dy*c;
  let w=W,d=D;
  if(sx&&sy){const factor=Math.max(Math.max(.005/item.width,.005/item.depth),Math.min(Math.min(1/item.width,1/item.depth),1+(lx*sx*W+ly*sy*D)/(W*W+D*D)));w=W*factor;d=D*factor}
  else if(item.kind==='stair'&&item.preset_id!=='staircase-spiral'){if(sx)w=Math.max(.005*plan.width,Math.min(plan.width,W+sx*lx));if(sy)d=Math.max(.005*plan.height,Math.min(plan.height,D+sy*ly))}
  else if(!['sofa','chair'].includes(item.kind)||item.kind==='sofa'&&item.shape==='round'){
   const requested=1+(sx?sx*lx/W:sy*ly/D);
   const factor=Math.max(Math.max(.005/item.width,.005/item.depth),Math.min(Math.min(1/item.width,1/item.depth),requested));
   w=W*factor;d=D*factor;
  }else if(sx)w=Math.max(.005*plan.width,Math.min(plan.width,W+sx*lx));
  else d=Math.max(.005*plan.height,Math.min(plan.height,D+sy*ly));
  if(item.kind==='sofa'&&item.shape!=='round'&&!(sx&&sy)){
   const m=modules(item),l=item.shape==='l';
   if(sx){const fixed=l?m.leg_width:0,offset=l?1:0;
    const max=Math.min(12-m.return_seats,Math.floor((1-fixed)/m.pitch_width+1e-8)+offset);
    m.main_seats=Math.max(l?2:1,Math.min(max,Math.round((w/plan.width-fixed)/m.pitch_width)+offset));
    w=(fixed+(m.main_seats-offset)*m.pitch_width)*plan.width;
   }else if(l){
    const max=Math.min(12-m.main_seats,Math.floor((1-m.leg_depth)/m.pitch_depth+1e-8));
    m.return_seats=Math.max(1,Math.min(max,Math.round((d/plan.height-m.leg_depth)/m.pitch_depth)));
    d=(m.leg_depth+m.return_seats*m.pitch_depth)*plan.height;
   }else d=D;
   out.sofa_modules=m;out.seat_count=m.main_seats+m.return_seats;
   if(/^(\d+-seater (L-shaped )?sofa|L-shaped sofa)$/.test(out.label))out.label=`${out.seat_count}-seater ${l?'L-shaped ':''}sofa`;
  }else if(item.kind==='chair'&&!(sx&&sy)){
   const m=structuredClone(item.chair_modules||{columns:1,rows:1,width:item.width,depth:item.depth});
   if(sx)m.columns=Math.max(1,Math.min(Math.floor(40/m.rows),Math.floor((1/m.width+.15)/1.15+1e-8),Math.round((w/plan.width/m.width+.15)/1.15)));
   else m.rows=Math.max(1,Math.min(Math.floor(40/m.columns),Math.floor((1/m.depth+.15)/1.15+1e-8),Math.round((d/plan.height/m.depth+.15)/1.15)));
   w=m.width*(m.columns*1.15-.15)*plan.width;d=m.depth*(m.rows*1.15-.15)*plan.height;
   out.chair_modules=m;
  }else scaleModules(out,w/W,d/D);
  const ox=sx*(w-W)/2,oy=sy*(d-D)/2;
  out.x=(cx+ox*c-oy*s)/plan.width;out.y=(cy+ox*s+oy*c)/plan.height;
  if(out.x<0||out.x>1||out.y<0||out.y>1)return structuredClone(item);
  out.width=w/plan.width;out.depth=d/plan.height;
  if(out.physical_size){out.physical_size.width*=w/W;out.physical_size.depth*=d/D}
  return out;
 }
 function snapToWall(item,plan,walls,tolerance){
  if(item.kind!=='decor'&&item.preset_id!=='wall-light')return null;
  const p=[item.x*plan.width,item.y*plan.height],width=item.width*plan.width,depth=item.depth*plan.height;let best=null;
  for(const wall of walls){
   if(wall.kind!=='wall')continue;
   const [a,b]=wall.points,dx=b[0]-a[0],dy=b[1]-a[1],len=Math.hypot(dx,dy);if(len<width||len<.2)continue;
   const t=Math.max(width/2,Math.min(len-width/2,((p[0]-a[0])*dx+(p[1]-a[1])*dy)/len)),q=[a[0]+t*dx/len,a[1]+t*dy/len],distance=Math.hypot(p[0]-q[0],p[1]-q[1]);
   if(distance>tolerance||best&&distance>=best.distance)continue;
   const sign=dx*(p[1]-q[1])-dy*(p[0]-q[0])>=0?1:-1,offset=(wall.thickness||1.5)/2+depth/2+.05;
   const x=(q[0]-sign*dy/len*offset)/plan.width,y=(q[1]+sign*dx/len*offset)/plan.height;
   if(x<0||x>1||y<0||y>1)continue;
   best={item:{...item,x,y,angle:((Math.atan2(dy,dx)*180/Math.PI+(sign<0?180:0))%360+360)%360},wall,distance};
  }return best;
 }
 function resizeDirection(item,plan,x,y){
  // Corner scaling travels along the actual diagonal, including aspect ratio.
  return ((Math.atan2(y*item.depth*plan.height,x*item.width*plan.width)*180/Math.PI+item.angle)%180+180)%180;
 }
 const cursorCache=new Map();
 function resizeCursor(item,plan,x,y){
  const angle=Math.round(resizeDirection(item,plan,x,y)),fallback=['ew','nwse','ns','nesw'][Math.round(angle/45)%4]+'-resize';
  if(!cursorCache.has(angle)){
   const path='M5 16H27M10 11L5 16L10 21M22 11L27 16L22 21';
   const svg=`<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 32 32"><g transform="rotate(${angle} 16 16)" fill="none" stroke-linecap="round" stroke-linejoin="round"><path d="${path}" stroke="white" stroke-width="3.5"/><path d="${path}" stroke="#26372b" stroke-width="1.5"/></g></svg>`;
   cursorCache.set(angle,`url("data:image/svg+xml,${encodeURIComponent(svg)}") 16 16, ${fallback}`);
  }
  return cursorCache.get(angle);
 }
 function groupBounds(rows,plan){
  const points=rows.flatMap(row=>{const v=row.value;if(row.type==='wall')return v.points;const a=v.angle*Math.PI/180,c=Math.cos(a),s=Math.sin(a);return [[-1,-1],[1,-1],[1,1],[-1,1]].map(([x,y])=>{x*=v.width*plan.width/2;y*=v.depth*plan.height/2;return[v.x*plan.width+x*c-y*s,v.y*plan.height+x*s+y*c]})});
  const x=Math.min(...points.map(p=>p[0])),y=Math.min(...points.map(p=>p[1])),right=Math.max(...points.map(p=>p[0])),bottom=Math.max(...points.map(p=>p[1]));return{x,y,width:Math.max(.2,right-x),depth:Math.max(.2,bottom-y),center:[(x+right)/2,(y+bottom)/2]};
 }
 function transformGroup(rows,plan,{delta=[0,0],rotation=0,factor=1,flip=null,pivot=null}={}){
  pivot=pivot||groupBounds(rows,plan).center;const a=rotation*Math.PI/180,c=Math.cos(a),s=Math.sin(a);
  const point=p=>{let x=(p[0]-pivot[0])*factor*(flip==='x'?-1:1),y=(p[1]-pivot[1])*factor*(flip==='y'?-1:1);return[pivot[0]+x*c-y*s+delta[0],pivot[1]+x*s+y*c+delta[1]]};
  const result=rows.map(row=>{let v=structuredClone(row.value);
   if(row.type==='wall'){v.points=v.points.map(point);v.thickness=(v.thickness||1.5)*factor;if(flip&&v.kind==='door')v.flip=!v.flip;if(v.thickness<.1||v.thickness>50)throw Error('The selection exceeds supported wall sizes.');}
   else{v=scale(v,factor);const p=point([v.x*plan.width,v.y*plan.height]);v.x=p[0]/plan.width;v.y=p[1]/plan.height;if(flip){v.angle=-v.angle;v[flip==='x'?'flip_x':'flip_y']=!v[flip==='x'?'flip_x':'flip_y']}v.angle=((v.angle+rotation)%360+360)%360;}
   return {...row,value:v};
  });
  const b=groupBounds(result,plan);if(b.x<-.00001||b.y<-.00001||b.x+b.width>plan.width+.00001||b.y+b.depth>plan.height+.00001)throw Error('Keep the whole selection inside the plan.');return result;
 }
 function balance(item,plan,mpp,product){
  const v=structuredClone(item),p=presets.find(p=>p.id===v.preset_id),dims=product?.dimensions_m||{},conflict=(product?.dimension_notes||[]).some(n=>/discrepancy/i.test(n));
  let size=v.physical_size?{...v.physical_size}:null;
  if(!size&&!conflict){const w=dims.length?.metres??dims.width?.metres,d=dims.depth?.metres??(dims.length?dims.width?.metres:null);if(w>0&&d>0&&v.kind!=='sofa'&&v.kind!=='chair')size={width:w,depth:d,unit:'m'}}
  if(size){v.width=size.width/(plan.width*mpp);v.depth=size.depth/(plan.height*mpp);v.physical_size=size;if(!conflict&&dims.height?.metres>0)v.height_m=dims.height.metres;return v}
  if(!p||['light','decor','stair','pillar','rug','plant'].includes(v.kind)||['plant','rug','comforter'].includes(p.id))return v;
  v.height_m=p.height;
  if(v.kind==='chair'){
   const m=v.chair_modules,w=p.width/(plan.width*mpp),d=p.depth/(plan.height*mpp);
   if(m){v.chair_modules={...m,width:w,depth:d};v.width=w*(m.columns*1.15-.15);v.depth=d*(m.rows*1.15-.15)}else{v.width=w;v.depth=d}
  }else if(v.kind==='sofa'&&v.shape!=='round'&&p.id!=='chaise'){
   const m=modules(v),l=v.shape==='l',pitch=l?.85:.75,depth=.9;
   v.sofa_modules={...m,leg_width:pitch/(plan.width*mpp),leg_depth:(l?pitch:depth)/(plan.height*mpp),pitch_width:pitch/(plan.width*mpp),pitch_depth:(l?pitch:depth)/(plan.height*mpp)};
   v.width=pitch*m.main_seats/(plan.width*mpp);v.depth=(l?pitch*(m.return_seats+1):depth)/(plan.height*mpp);
  }else{
   // Built-in cabinetry keeps its user-defined run; only normalize its depth and height.
   if(!['kitchen-counter','wardrobe','tv-unit','bookcase'].includes(p.id))v.width=p.width/(plan.width*mpp);
   v.depth=p.depth/(plan.height*mpp);
  }
  return v;
 }
 const api={balance,groupBounds,transformGroup,presets,symbol,create,categories,snapToWall,seats,duplicate,scale,transform,resizeDirection,resizeCursor,consistentSofa,chairInstances,quantityLabel};if(typeof module!=='undefined')module.exports=api;else window.FurnitureLibrary=api;
})();
