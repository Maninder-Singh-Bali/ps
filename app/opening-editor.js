'use strict';
// Draft opening edits in source pixels (horizontal) and metres (vertical).
// No attachment inference, scene mutation, or renderer-specific geometry.
(function(){
const G=typeof module!=='undefined'?require('./trace-geometry.js'):window.TraceGeometry;
const isOpening=f=>['door','window','sliding_door'].includes(f.kind);
function levels(o){const base=o.kind==='window'?(o.sill_m??.9):(o.base_m??0),head=o.head_m??(o.kind==='door'?2.2:2.4);return {base,head,height:head-base};}
function check(fs,o,defaultHeight=2.5){const v=levels(o),w=fs.find(w=>w.id===o.host_wall_id),H=w?.height_m??o.height_m??defaultHeight;
 if(![v.base,v.head,v.height].every(Number.isFinite)||v.base<0||v.height<=0||v.head>H+1e-8)throw Error('Use a positive opening height; its base and head must fit within the wall height.');
 if(o.host_wall_id)G.checkOpening(fs,o);return v;
}
function edit(fs,id,patch={},anchor='left',defaultHeight=2.5){const out=G.copy(fs),o=out.find(f=>f.id===id);if(!o||!isOpening(o))throw Error('Select a door or window.');const old=levels(o);
 if(patch.width!==undefined){if(!o.host_wall_id)throw Error('Attach this opening to a wall before resizing its width.');const fraction={left:0,centre:.5,right:1}[anchor];if(fraction===undefined)throw Error('Choose a resize anchor.');o.offset+=(o.width-patch.width)*fraction;o.width=patch.width;}
 if(patch.offset!==undefined)o.offset=patch.offset;
 if(patch.base!==undefined)o[o.kind==='window'?'sill_m':'base_m']=patch.base;
 if(patch.height!==undefined||patch.base!==undefined)o.head_m=(patch.base??old.base)+(patch.height??old.height);
 check(out,o,defaultHeight);return G.hosted(out);
}
function frameFit(o,w){const L=G.dist(...w.points);if(L<1e-6)throw Error('Wall has no usable length.');const u=w.points[1].map((v,i)=>(v-w.points[0][i])/L),ns=o.points.map(p=>(p[1]-w.points[0][1])*u[0]-(p[0]-w.points[0][0])*u[1]);
 if(Math.abs(ns[0]-ns[1])>1e-6)throw Error('Opening and wall are not parallel. No opening was moved.');
 if(Math.abs(ns[0])+o.thickness/2>w.thickness/2+1e-6)throw Error('The saved frame lies outside this wall thickness. No opening was moved or resized.');return ns[0];}
function attach(fs,id,wallId,defaultHeight){const out=G.copy(fs),o=out.find(o=>o.id===id),w=out.find(w=>w.id===wallId&&w.kind==='wall');if(!o||!w)throw Error('Choose an existing wall.');const normal=frameFit(o,w),ps=o.points.map(p=>G.project(p,w));
 o.host_wall_id=w.id;o.offset=Math.min(...ps.map(p=>p.t));o.width=G.dist(...o.points);o.normal_offset=normal;o.frame_thickness=o.thickness;o.hinge_end=ps[0].t>ps[1].t;check(out,o,defaultHeight);return G.hosted(out);
}
function peers(fs,o){const w=fs.find(w=>w.id===o.host_wall_id);if(!w)return [];return fs.filter(q=>q.id!==o.id&&isOpening(q)).flatMap(q=>{if(q.host_wall_id)return q.host_wall_id===w.id?[q]:[];try{frameFit(q,w);}catch(_){return [];}const ps=q.points.map(p=>G.project(p,w));if(Math.min(...ps.map(p=>p.t))>=G.dist(...w.points)-1e-8||Math.max(...ps.map(p=>p.t))<=1e-8)return [];return [{...q,offset:Math.min(...ps.map(p=>p.t)),width:G.dist(...q.points)}];});}
function clearances(fs,o){const w=fs.find(w=>w.id===o.host_wall_id);if(!w)return null;const qs=peers(fs,o),left=qs.filter(q=>q.offset+q.width<=o.offset+1e-8),right=qs.filter(q=>q.offset>=o.offset+o.width-1e-8);return {a:o.offset,b:G.dist(...w.points)-o.offset-o.width,left:left.length?o.offset-Math.max(...left.map(q=>q.offset+q.width)):null,right:right.length?Math.min(...right.map(q=>q.offset))-o.offset-o.width:null};}
function verticalSnap(fs,o,value,edge,tolerance,enabled,previous){if(!enabled)return {value};const candidates=[];for(const q of peers(fs,o))for(const target of ['base','head']){const z=levels(q)[target],key=q.id+':'+target;if(Math.abs(z-value)<=tolerance*(previous===key?1.35:1))candidates.push({value:z,key,hint:(target==='base'?(q.kind==='window'?'Sill':'Base'):'Head')+' aligned',distance:Math.abs(z-value)-(key===previous?tolerance*.25:0)});}return candidates.sort((a,b)=>a.distance-b.distance)[0]||{value};}
function horizontalSnap(fs,o,value,tolerance,enabled,previous){if(!enabled)return {value};const w=fs.find(w=>w.id===o.host_wall_id),L=G.dist(...w.points),targets=[[0,'End A'],[L/2,'Wall centre'],[L,'End B']];for(const q of peers(fs,o))targets.push([q.offset,'Opening edge'],[q.offset+q.width/2,'Opening centre'],[q.offset+q.width,'Opening edge']);const rows=targets.map(([x,hint])=>({value:x,hint,key:'width:'+x,distance:Math.abs(value-x)})).filter(q=>q.distance<=tolerance*(q.key===previous?1.35:1));return rows.sort((a,b)=>(a.distance-(a.key===previous?tolerance*.25:0))-(b.distance-(b.key===previous?tolerance*.25:0)))[0]||{value};}
// Attachment proposals are derived previews. Only apply the returned feature set
// after review; no nearest-wall fallback and no projection across real gaps.
const ATTACH_EPS=1e-6;
function attachmentProposal(fs,id,wallId,defaultHeight=2.5){
 const original=fs.find(f=>f.id===id),wall=fs.find(f=>f.id===wallId&&f.kind==='wall');
 if(!original||!isOpening(original)||original.host_wall_id)throw Error('Select an unattached opening.');
 if(!wall)throw Error('Choose an existing wall.');
 const normal=frameFit(original,wall);
 const L=G.dist(...wall.points),u=wall.points[1].map((v,i)=>(v-wall.points[0][i])/L),project=p=>({t:p.reduce((s,v,i)=>s+(v-wall.points[0][i])*u[i],0),side:Math.abs((p[0]-wall.points[0][0])*u[1]-(p[1]-wall.points[0][1])*u[0])}),ps=original.points.map(project),lo=Math.min(...ps.map(p=>p.t)),hi=Math.max(...ps.map(p=>p.t));
 if(hi<-ATTACH_EPS||lo>L+ATTACH_EPS)throw Error('There is a gap between this wall and the opening. No gap will be closed.');
 const low=Math.min(0,lo),high=Math.max(L,hi),extended=low<-ATTACH_EPS||high>L+ATTACH_EPS;
 const out=G.copy(fs),w=out.find(f=>f.id===wallId),normalized=G.junctions(fs),old=normalized.find(f=>f.id===wallId);
 if(extended){
  // The only extra span is covered by this already recorded opening. This
  // restores its split legacy host, not a new inferred length beyond the trace.
  const at=t=>wall.points[0].map((v,i)=>v+u[i]*t);w.points=[at(low),at(high)];w.junction_ids=[...old.junction_ids];w.junction_nodes=G.copy(w.junction_nodes||[]);
  for(const i of [0,1])if(G.dist(w.points[i],wall.points[i])>ATTACH_EPS){
   const connected=G.members(fs,wallId,i).filter(m=>m.id!==wallId);
   if(connected.length&&!w.junction_nodes.some(n=>n.id===old.junction_ids[i]))w.junction_nodes.push({id:old.junction_ids[i],point:[...wall.points[i]]});
   const ids=[...new Set(normalized.filter(f=>f.kind==='wall'&&f.id!==wallId).flatMap(q=>G.anchors(q).filter(a=>G.dist(a.point,w.points[i])<ATTACH_EPS).map(a=>a.id)))];
   if(ids.length>1)throw Error('Several separate junctions occupy the new host end. Resolve that junction explicitly first.');
   w.junction_ids[i]=ids[0]||'j:attachment:'+wallId+':'+i;
  }
  for(const q of out.filter(q=>q.host_wall_id===wallId))q.offset-=low;
  w.attachment_extension={opening_id:id,previous_points:G.copy(wall.points),method:'explicit extension through recorded opening span only'};
 }
 let attached=attach(out,id,wallId,defaultHeight),o=attached.find(f=>f.id===id);
 // The existing opening's height/notes/identity and oriented world endpoints
 // must survive; numerical equality alone uses a sub-pixel floating tolerance.
 if(o.points.some((p,i)=>G.dist(p,original.points[i])>ATTACH_EPS)||Math.abs(G.dist(...o.points)-G.dist(...original.points))>ATTACH_EPS)throw Error('Attachment would change the opening position or width.');
 for(const q of attached.filter(q=>q.host_wall_id===wallId))check(attached,q,defaultHeight);
 return {wallId,extended,normalOffset:normal,frameThickness:original.thickness,wallThickness:wall.thickness,extension:high-low-L,features:attached,points:G.copy(w.points),openingPoints:G.copy(original.points),width:G.dist(...original.points),maxDisplacement:Math.max(...o.points.map((p,i)=>G.dist(p,original.points[i])))};
}
function attachmentCandidates(fs,id,defaultHeight=2.5){const candidates=[],excluded=[];for(const w of fs.filter(w=>w.kind==='wall')){try{candidates.push(attachmentProposal(fs,id,w.id,defaultHeight));}catch(e){excluded.push({wallId:w.id,reason:e.message});}}return {candidates,excluded};}

const api={attachmentProposal,attachmentCandidates,horizontalSnap,isOpening,levels,check,edit,attach,peers,clearances,verticalSnap};if(typeof module!=='undefined')module.exports=api;else window.OpeningEditor=api;
})();
