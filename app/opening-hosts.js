'use strict';
// Conservative draft-only reconstruction. Every added interval must be covered
// by a recorded aperture; pixel proximity and perpendicular faces are not hosts.
(()=>{
const G=typeof module!=='undefined'?require('./trace-geometry'):window.TraceGeometry;
const O=typeof module!=='undefined'?require('./opening-editor'):window.OpeningEditor;
const EPS=1e-6;
function basis(w){const a=w.points[0],L=G.dist(...w.points),u=w.points[1].map((x,i)=>(x-a[i])/L);return {L,u,at:t=>a.map((v,i)=>v+u[i]*t),t:p=>p.reduce((s,v,i)=>s+(v-a[i])*u[i],0),n:p=>(p[1]-a[1])*u[0]-(p[0]-a[0])*u[1]};}
function fits(o,w,b){return Math.abs(b.n(o.points[0])-b.n(o.points[1]))<=EPS&&Math.abs(b.n(o.points[0]))+o.thickness/2<=w.thickness/2+EPS;}
function properties(w,H){const p={...w,height_m:w.height_m??H,thickness:Number(w.thickness.toFixed(6))};for(const k of ['id','points','junction_ids','junction_nodes','split_root','evidence','attachment_extension','automatic_host_repair'])delete p[k];return Object.fromEntries(Object.entries(p).sort(([a],[b])=>a.localeCompare(b)));}
function proposal(features,id,seedId,H=2.5){
 const original=G.hosted(features),opening=original.find(f=>f.id===id&&O.isOpening(f)),seed=original.find(f=>f.id===seedId&&f.kind==='wall');
 if(!opening||!seed)throw Error('Choose an opening and an aligned wall.');
 const b=basis(seed);if(!fits(opening,seed,b))throw Error('Opening orientation or frame position is incompatible with this wall. Perpendicular contact is not a host.');
 const profile=JSON.stringify(properties(seed,H));
 const walls=original.filter(w=>w.kind==='wall'&&w.points.every(p=>Math.abs(b.n(p))<=EPS)&&JSON.stringify(properties(w,H))===profile);
 const wallIds=new Set(walls.map(w=>w.id));
 const opens=original.filter(o=>O.isOpening(o)&&fits(o,seed,b)&&(!o.host_wall_id||wallIds.has(o.host_wall_id)));
 const rows=[...walls,...opens].map(f=>({f,lo:Math.min(...f.points.map(b.t)),hi:Math.max(...f.points.map(b.t))}));
 let lo=Math.min(...opening.points.map(b.t)),hi=Math.max(...opening.points.map(b.t)),component=[],prior;
 do{prior=lo+':'+hi;component=rows.filter(r=>r.lo<=hi+EPS&&r.hi>=lo-EPS);lo=Math.min(lo,...component.map(r=>r.lo));hi=Math.max(hi,...component.map(r=>r.hi));}while(prior!==lo+':'+hi);
 const ws=component.filter(r=>r.f.kind==='wall').sort((a,b)=>a.lo-b.lo||a.f.id.localeCompare(b.f.id)),os=component.filter(r=>O.isOpening(r.f));
 if(!ws.some(r=>r.f.id===seedId))throw Error('No aligned wall reaches this opening through recorded wall or aperture spans. The missing gap is unsupported.');
 for(let i=1;i<ws.length;i++)if(ws[i].lo<ws[i-1].hi-EPS)throw Error('Overlapping wall references need review; no duplicate host was chosen.');
 // A contained aperture needs no reconstruction or segment consolidation.
 // Preserve a merged object's underlying members and explicit detach state.
 const contained=opening.points.every(p=>b.t(p)>=-EPS&&b.t(p)<=b.L+EPS);
 if(contained&&seed.wall_chain_id){const out=O.attach(original,id,seed.id,H);return {key:seed.id,wallId:seed.id,wallIds:[seed.id],features:out,points:G.copy(seed.points),openingPoints:G.copy(opening.points),openingIds:[id],extended:false,extension:0,normalOffset:b.n(opening.points[0]),frameThickness:opening.thickness,wallThickness:seed.thickness,width:G.dist(...opening.points),maxDisplacement:0};}
 if(ws.length>1&&ws.some(r=>r.f.wall_chain_id))throw Error('Existing merged wall membership needs an explicit host choice; it will not be collapsed automatically.');
 // Select the same root from either side of a split host; retain an existing
 // opening host when possible, otherwise use stable identity, never nearest.
 const used=new Set(os.map(r=>r.f.host_wall_id).filter(Boolean));
 const root=[...ws].sort((a,b)=>(used.has(b.f.id)-used.has(a.f.id))||a.f.id.localeCompare(b.f.id))[0].f;
 const rb=basis(root),rlo=Math.min(...component.flatMap(r=>r.f.points.map(rb.t))),rhi=Math.max(...component.flatMap(r=>r.f.points.map(rb.t))),at=rb.at;
 const ids=new Set(ws.map(r=>r.f.id)),normalized=G.junctions(original),all=normalized.filter(w=>ids.has(w.id)).flatMap(G.anchors),outside=normalized.filter(w=>w.kind==='wall'&&!ids.has(w.id)),external=new Set(outside.flatMap(G.anchors).map(a=>a.id));
 // Coincident but explicitly detached corners are not automatic joins.
 for(let i=1;i<ws.length;i++)if(Math.abs(ws[i].lo-ws[i-1].hi)<=EPS){const p=b.at(ws[i].lo),keys=new Set(all.filter(a=>G.dist(a.point,p)<=EPS).map(a=>a.id));if(keys.size>1)throw Error('These coincident wall ends are explicitly separate. Join them first.');}
 const endKey=(t,i)=>{const found=[...new Set([...all,...outside.flatMap(G.anchors)].filter(a=>G.dist(a.point,at(t))<=EPS).map(a=>a.id))];if(found.length>1)throw Error('Separate junctions occupy the host end; review them first.');return found[0]||'j:auto-host:'+root.id+':'+i;};
 const w={...G.copy(root),points:[at(rlo),at(rhi)],junction_ids:[endKey(rlo,0),endKey(rhi,1)]};
 w.junction_nodes=[...new Map(all.filter(a=>external.has(a.id)&&rb.t(a.point)>rlo+EPS&&rb.t(a.point)<rhi-EPS).map(a=>[a.id,{id:a.id,point:G.copy(a.point)}])).values()];
 const reconstructed=Math.max(0,rhi-rlo-ws.reduce((s,r)=>s+r.hi-r.lo,0));
 const changed=ws.length>1||G.dist(w.points[0],root.points[0])>EPS||G.dist(w.points[1],root.points[1])>EPS;
 if(changed){w.automatic_host_repair={version:1,method:'aligned wall run; added spans covered by saved openings only',support_ids:ws.map(r=>r.f.id).sort(),opening_ids:os.map(r=>r.f.id).sort(),previous_walls:ws.map(r=>G.copy(r.f)),added_span:reconstructed};delete w.split_root;}
 let out=original.filter(f=>!ids.has(f.id));out.push(changed?w:G.copy(root));
 // Reproject every opening on this run from its original oriented world points.
 // Frame offsets are retained, including a thin window beside a thicker door.
 for(const r of os){const before=r.f;out=O.attach(out,before.id,root.id,H);const after=out.find(f=>f.id===before.id);if(after.points.some((p,i)=>G.dist(p,before.points[i])>EPS)||Math.abs(after.thickness-before.thickness)>EPS)throw Error('Attachment would move or resize an opening.');}
 for(const o of out.filter(f=>ids.has(f.host_wall_id)||f.host_wall_id===root.id))O.check(out,o,H);
 return {key:ws.map(r=>r.f.id).sort().join('|'),wallId:root.id,wallIds:[...ids],features:out,points:G.copy(w.points),openingPoints:G.copy(opening.points),openingIds:os.map(r=>r.f.id),extended:changed,extension:reconstructed,normalOffset:rb.n(opening.points[0]),frameThickness:opening.thickness,wallThickness:root.thickness,width:G.dist(...opening.points),maxDisplacement:0};
}
function candidates(fs,id,H=2.5){const choices=new Map(),excluded=[];for(const w of fs.filter(w=>w.kind==='wall'))try{const p=proposal(fs,id,w.id,H);choices.set(p.key,p);}catch(e){excluded.push({wallId:w.id,reason:e.message});}return {candidates:[...choices.values()].sort((a,b)=>a.key.localeCompare(b.key)),excluded};}
function explanation(r){return r.excluded.find(e=>/merged wall membership|explicitly separate|Separate junctions|retained branch|wall height|overlap/i.test(e.reason))?.reason||'Missing aligned host geometry: a parallel wall of compatible thickness must reach this span through recorded wall or opening segments. Perpendicular contact and unexplained gaps are not support.';}
function repair(fs,H=2.5){let out=G.copy(fs);const repaired=[],unresolved=[];
 for(const id of fs.filter(o=>O.isOpening(o)&&!o.host_wall_id).map(o=>o.id).sort()){
  if(out.find(o=>o.id===id)?.host_wall_id)continue;
  const r=candidates(out,id,H);if(r.candidates.length===1){const p=r.candidates[0];for(const oid of p.openingIds)if(!out.find(o=>o.id===oid)?.host_wall_id)repaired.push(oid);out=p.features;}
 }
 for(const o of out.filter(o=>O.isOpening(o)&&!o.host_wall_id)){const r=candidates(out,o.id,H);unresolved.push({id:o.id,count:r.candidates.length,reason:r.candidates.length?'Multiple supported wall runs remain. Choose a highlighted host.':explanation(r)});}
 return {features:out,repaired,unresolved};
}
const api={proposal,candidates,repair,explanation};if(typeof module!=='undefined')module.exports=api;else window.OpeningHosts=api;
})();
