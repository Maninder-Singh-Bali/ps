'use strict';
(() => {
 // Group inner cushion/pillow strokes into their outer symbol, never architecture.
 function convert(probes,rooms,plan){
  const furniture=probes.filter(p=>p.kind==='furniture'&&p.box.every(Number.isFinite));
  const contains=(a,b)=>b[0]>=a[0]-.6&&b[1]>=a[1]-.6&&b[0]+b[2]<=a[0]+a[2]+.6&&b[1]+b[3]<=a[1]+a[3]+.6;
  const candidates=furniture.filter(p=>p.box[2]>.2&&p.box[3]>.2&&p.closed);
  const roots=candidates.filter(p=>p.atomic||!candidates.some(q=>q!==p&&!q.atomic&&q.box[2]*q.box[3]>p.box[2]*p.box[3]*1.1&&contains(q.box,p.box)));
  const replacements=[],hide=new Set(),unassigned=[];
  for(const p of roots){
   const [x,y,w,h]=p.box,cx=(x+w/2)/plan.width,cy=(y+h/2)/plan.height;
   const matches=rooms.filter(r=>r.bbox&&cx>=r.bbox[0]&&cx<=r.bbox[0]+r.bbox[2]&&cy>=r.bbox[1]&&cy<=r.bbox[1]+r.bbox[3]);
   const room=matches.sort((a,b)=>a.bbox[2]*a.bbox[3]-b.bbox[2]*b.bbox[3])[0];
   if(!room){unassigned.push(p.id);continue}
   const members=furniture.filter(q=>q===p||!q.atomic&&contains(p.box,q.box));members.forEach(q=>hide.add(q.id));
   // A room with deliberate user placements keeps that complete arrangement.
   if(room.block_layout?.items?.length)continue;
   const pillows=members.filter(q=>q.closed&&q.id!==p.id&&q.box[2]*q.box[3]<w*h*.25);
   const paths=members.filter(q=>!q.closed).length;
   let preset='coffee-table',kind='table',label='Table',seats=null,height=.45,angle=0,width=w,depth=h;
   if(p.atomic){preset='chair';kind='chair';label='Chair';height=.85}
   else if(pillows.length>=2&&Math.min(w,h)>12){preset='bed-double';kind='bed';label='Double bed';height=.55}
   else if(paths>=3&&p.rounded){seats=Math.max(1,Math.min(12,paths-2));preset='sofa-'+Math.min(3,seats);kind='sofa';label=seats+'-seater sofa';height=.85;if(h>w){angle=90;width=h;depth=w}}
   else if(Math.max(w,h)/Math.min(w,h)>3){preset='wardrobe';kind='storage';label='Storage / counter · check type';height=1;if(h>w){angle=90;width=h;depth=w}}
   if(/kitchen/i.test(room.name||'')&&!p.atomic&&kind!=='bed'&&kind!=='sofa'){preset='kitchen-counter';kind='storage';label='Kitchen counter';height=.9}
   if(/dining/i.test(room.name||'')&&kind==='table'){preset='kitchen-table';label='Dining table';height=.75}
   const item={id:'library-'+p.id,preset_id:preset,kind,label,x:cx,y:cy,width:Math.max(.005,width/plan.width),depth:Math.max(.005,depth/plan.height),angle,height_m:height,shape:'box',return_side:'left',seat_count:seats,asset_id:null,source:'traced-furniture-library',prompt:''};
   replacements.push({room_id:room.id,item,source_ids:members.map(q=>q.id)});
  }
  // Loose cushion/divider strokes can survive a separately moved outer symbol.
  // Remove them only where a saved library arrangement already replaces the traces.
  for(const p of furniture.filter(p=>!p.closed)){
   const cx=(p.box[0]+p.box[2]/2)/plan.width,cy=(p.box[1]+p.box[3]/2)/plan.height;
   if(rooms.some(r=>r.block_layout?.items?.length&&r.bbox&&cx>=r.bbox[0]&&cx<=r.bbox[0]+r.bbox[2]&&cy>=r.bbox[1]&&cy<=r.bbox[1]+r.bbox[3]))hide.add(p.id);
  }
  return {replacements,hide_ids:[...hide],unassigned};
 }
 if(typeof module!=='undefined')module.exports={convert};else window.TracedFurniture={convert};
})();
