'use strict';
// Canonical drawing features in original plan pixels; metric calibration is separate.
(()=>{
const copy=x=>JSON.parse(JSON.stringify(x)), dist=(a,b)=>Math.hypot(b[0]-a[0],b[1]-a[1]);
function hosted(features){const rows=copy(features),walls=new Map(rows.filter(f=>f.kind==='wall').map(f=>[f.id,f]));for(const f of rows){const w=walls.get(f.host_wall_id);if(!w)continue;const [a,b]=w.points,L=dist(a,b),u=b.map((v,i)=>(v-a[i])/L);f.points=[f.offset,f.offset+f.width].map(t=>a.map((v,i)=>v+u[i]*t+[-u[1],u[0]][i]*(f.normal_offset||0)));if(f.hinge_end)f.points.reverse();f.thickness=f.frame_thickness??w.thickness;}return rows;}
function project(p,w){const [a,b]=w.points,L=dist(a,b),u=b.map((v,i)=>(v-a[i])/L),t=p.reduce((s,v,i)=>s+(v-a[i])*u[i],0),point=a.map((v,i)=>v+u[i]*Math.max(0,Math.min(L,t)));return {t,point,distance:dist(p,point),length:L};}
// Position is always measured from host points[0], independently of door hinge/swing.
function openingHost(fs,o){const w=fs.find(w=>w.id===o.host_wall_id&&w.kind==='wall');if(!w)throw Error('Attach this opening to a wall before sliding it.');return w;}
function openingPeers(fs,o,w){return fs.filter(q=>q.id!==o.id&&['door','window','sliding_door'].includes(q.kind)).flatMap(q=>{
 if(q.host_wall_id)return q.host_wall_id===w.id?[q]:[];
 // Protect parallel source openings within this wall, without assigning a host.
 const ps=q.points.map(p=>project(p,w)),L=dist(...w.points),u=w.points[1].map((v,i)=>(v-w.points[0][i])/L),ns=q.points.map(p=>(p[1]-w.points[0][1])*u[0]-(p[0]-w.points[0][0])*u[1]);return Math.abs(ns[0]-ns[1])<1e-6&&Math.abs(ns[0])+(q.thickness||0)/2<=w.thickness/2+1e-6?[{offset:Math.min(...ps.map(p=>p.t)),width:dist(...q.points)}]:[];
});}
function checkOpening(fs,o,offset=o.offset,width=o.width){const w=openingHost(fs,o),L=dist(...w.points);
 if(!Number.isFinite(o.normal_offset??0)||!Number.isFinite(o.frame_thickness??w.thickness)||(o.frame_thickness??w.thickness)<=0||Math.abs(o.normal_offset||0)+(o.frame_thickness??w.thickness)/2>w.thickness/2+1e-6)throw Error('The preserved opening frame must fit within the host wall thickness.');
 if(!Number.isFinite(offset)||!Number.isFinite(width)||width<=0||offset<0||offset+width>L+1e-8)throw Error('Opening must fit between wall ends A and B.');
 if((w.junction_nodes||[]).some(n=>{const t=project(n.point,w).t;return offset<t-1e-8&&offset+width>t+1e-8;}))throw Error('Opening cannot cross a retained branch junction.');
 if(openingPeers(fs,o,w).some(q=>Math.min(offset+width,q.offset+q.width)>Math.max(offset,q.offset)+1e-8))throw Error('Position overlaps another opening on this wall.');
 return {wall:w,length:L};}
function openingRange(fs,o){const {wall,length}=checkOpening(fs,o);let min=0,max=length-o.width;
 for(const q of openingPeers(fs,o,wall)){if(q.offset+q.width<=o.offset+1e-8)min=Math.max(min,q.offset+q.width);else if(q.offset>=o.offset+o.width-1e-8)max=Math.min(max,q.offset-o.width);}
 for(const n of wall.junction_nodes||[]){const t=project(n.point,wall).t;if(t<=o.offset+1e-8)min=Math.max(min,t);else if(t>=o.offset+o.width-1e-8)max=Math.min(max,t-o.width);}
 return {min,max};}
function slideOpening(fs,id,offset,range){const out=copy(fs),o=out.find(f=>f.id===id);range=range||openingRange(fs,o);o.offset=Math.max(range.min,Math.min(range.max,offset));checkOpening(out,o);return hosted(out);}
function snap(p,features,tolerance,enabled=true){if(!enabled)return {point:p,hit:false};let best=tolerance,out=p;for(const w of features.filter(f=>f.kind==='wall'))for(const q of w.points){let d=dist(p,q);if(d<best){best=d;out=q;}}return {point:[...out],hit:out!==p};}
function trace(a,b,t,face){const L=dist(a,b);if(L<.001)return [a,b];const sign=face==='inside'?1:face==='outside'?-1:0,n=[-(b[1]-a[1])/L*t/2*sign,(b[0]-a[0])/L*t/2*sign];return [a,b].map(p=>p.map((v,i)=>v+n[i]));}
// Persist endpoint topology separately from thickness/footprint rendering. Legacy exact
// coincidences keep their old shared behaviour; nearby faces never imply a connection.
function junctions(fs){const out=copy(fs);for(const w of out.filter(f=>f.kind==='wall'))w.junction_ids=w.points.map((p,i)=>w.junction_ids?.[i]||'j:legacy:'+p.map(v=>v.toFixed(6)).join(':'));return out;}
function members(fs,id,index){const rows=junctions(fs),w=rows.find(w=>w.id===id),key=anchors(w).find(a=>a.index===index)?.id;return rows.filter(w=>w.kind==='wall').flatMap(w=>anchors(w).flatMap(a=>a.id===key?[{id:w.id,index:a.index,point:a.point}]:[]));}
function junctionTarget(p,fs,tolerance,exclude=[],enabled=true){if(!enabled)return null;const omitted=new Set(exclude.map(e=>e.id+':'+e.index)),walls=fs.filter(f=>f.kind==='wall');let best=null;
 for(const w of walls)for(let i=0;i<2;i++){if(omitted.has(w.id+':'+i))continue;const distance=dist(p,w.points[i]);if(distance<=tolerance&&(!best||distance<best.distance))best={wall:w.id,index:i,point:[...w.points[i]],distance};}
 if(best)return best;
 for(const w of walls){if(exclude.some(e=>e.id===w.id))continue;const q=project(p,w);if(q.t>.01&&q.t<q.length-.01&&q.distance<=tolerance&&(!best||q.distance<best.distance))best={wall:w.id,t:q.t,point:q.point,distance:q.distance};}return best;
}
function checkJunctionChange(before,after){for(const w of after.filter(f=>f.kind==='wall'))if(dist(...w.points)<.01)throw Error('This would collapse a wall. Choose another junction.');for(const o of after.filter(f=>f.host_wall_id)){const prior=before.find(f=>f.id===o.id);let wasValid=true;try{if(prior)checkOpening(before,prior);}catch(_){wasValid=false;}if(wasValid)checkOpening(after,o);}return after;}
function detachEndpoint(fs,id,index,newId){const out=junctions(fs),w=out.find(w=>w.id===id);w.junction_ids[index]='j:detached:'+newId;return out;}
function connectEndpoint(fs,id,index,target,newId){let out=junctions(fs),w=out.find(w=>w.id===id);const sourceKey=anchors(w).find(a=>a.index===index).id;out=materialize(out,new Set([sourceKey]));w=out.find(w=>w.kind==='wall'&&w.junction_ids.includes(sourceKey));index=w.junction_ids.indexOf(sourceKey);if(!target)return out;const own=w.junction_ids[index];let host=out.find(w=>w.id===target.wall);if(!host)throw Error('Junction target is missing.');let ti=target.index>1?undefined:target.index;
 if(ti===undefined){const root=host.split_root||host.id;host=out.filter(f=>f.kind==='wall'&&(f.id===root||f.split_root===root)).find(f=>project(target.point,f).distance<1e-6);if(!host)throw Error('Junction target changed. Select it again.');const q=project(target.point,host);if(q.t<.01)ti=0;else if(q.t>q.length-.01)ti=1;else{out=split(out,host.id,q.t,newId);host=out.find(f=>f.id===host.id);ti=1;}}
 const key=host.junction_ids[ti],point=host.points[ti];if(own===key)return out;
 for(const row of out.filter(f=>f.kind==='wall'))row.points=row.points.map((p,i)=>{if(row.junction_ids[i]!==own)return p;row.junction_ids[i]=key;return [...point];});return checkJunctionChange(fs,hosted(out));
}
function moveEndpoint(fs,id,index,p){const base=junctions(fs),original=base.find(f=>f.id===id);if(original.kind!=='wall'){original.points[index]=[...p];return base;}const key=anchors(original).find(a=>a.index===index)?.id,out=materialize(base,new Set([key]));for(const f of out.filter(f=>f.kind==='wall'))f.points=f.points.map((q,i)=>f.junction_ids[i]===key?[...p]:q);return checkJunctionChange(fs,hosted(out));}
function split(fs,id,t,newId){const out=junctions(fs),w=out.find(f=>f.id===id),L=dist(...w.points);if(t<=.01||t>=L-.01)throw Error('Choose a point inside the wall.');const attached=out.filter(f=>f.host_wall_id===id);if(attached.some(f=>f.offset<t&&f.offset+f.width>t))throw Error('Cannot form a junction through an attached opening.');
 for(const o of out.filter(f=>!f.host_wall_id&&['door','window','sliding_door'].includes(f.kind))){const ps=o.points.map(p=>project(p,w));if(ps.every(p=>p.distance<=Math.max(w.thickness,o.thickness||0)/2+.001)&&Math.min(...ps.map(p=>p.t))<t&&Math.max(...ps.map(p=>p.t))>t)throw Error('Cannot form a junction through a source opening.');}
 const [a,b]=w.points,q=a.map((v,i)=>v+(b[i]-v)*t/L),key=w.junction_nodes?.find(n=>dist(n.point,q)<1e-6)?.id||'j:split:'+newId,root=w.split_root||w.id,next={...copy(w),id:newId,points:[q,b],junction_ids:[key,w.junction_ids[1]],split_root:root};next.junction_nodes=(w.junction_nodes||[]).filter(n=>project(n.point,w).t>t+1e-6);w.junction_nodes=(w.junction_nodes||[]).filter(n=>project(n.point,w).t<t-1e-6);w.points=[a,q];w.junction_ids[1]=key;w.split_root=root;out.push(next);for(const f of attached)if(f.offset>=t){f.host_wall_id=newId;f.offset-=t;}return hosted(out);}
function issues(fs){const out=[],walls=fs.filter(f=>f.kind==='wall'),open=fs.filter(f=>f.host_wall_id);for(const o of open){const w=walls.find(w=>w.id===o.host_wall_id);if(!w||o.offset<-.001||o.offset+o.width>dist(...w.points)+.001)out.push({id:o.id,message:'Opening extends beyond its host wall.'});for(const q of open)if(q.id<o.id&&q.host_wall_id===o.host_wall_id&&Math.min(q.offset+q.width,o.offset+o.width)>Math.max(q.offset,o.offset)+.001)out.push({id:o.id,message:'Openings overlap on their host wall.'});}
for(let i=0;i<walls.length;i++){const w=walls[i];for(const p of w.points){const near=walls.filter(q=>q!==w).map(q=>({q,...project(p,q)})).sort((a,b)=>a.distance-b.distance)[0];if(near&&near.distance>.001&&near.distance<Math.max(w.thickness,near.q.thickness)*1.1)out.push({id:w.id,message:'Near junction / short gap: inspect; not automatically closed.'});}for(let j=i+1;j<walls.length;j++){const q=walls[j],pa=project(q.points[0],w),pb=project(q.points[1],w);if(pa.distance<.001&&pb.distance<.001&&Math.min(pa.t,pb.t)<dist(...w.points)-.01&&Math.max(pa.t,pb.t)>.01)out.push({id:w.id,message:'Collinear wall overlap: review duplicates.'});}}
return out;}
// Rooms are bounded faces of an explicitly connected centreline graph. Split at exact
// T/cross junctions; never snap near misses or infer missing walls. Report centreline area.
function rooms(fs,mpp){if(!mpp)return [];const walls=fs.filter(f=>f.kind==='wall'),edges=[],nodes=new Map(),key=p=>p.map(v=>v.toFixed(4)).join(',');for(const w of walls){const cuts=[0,1],a=w.points[0],b=w.points[1],u=b.map((v,i)=>v-a[i]);for(const q of walls){if(q===w)continue;const c=q.points[0],v=q.points[1].map((v,i)=>v-c[i]),den=u[0]*v[1]-u[1]*v[0];if(Math.abs(den)<1e-10)continue;const z=c.map((v,i)=>v-a[i]),t=(z[0]*v[1]-z[1]*v[0])/den,s=(z[0]*u[1]-z[1]*u[0])/den;if(t>1e-8&&t<1-1e-8&&s>=-1e-8&&s<=1+1e-8)cuts.push(t);}const ts=[...new Set(cuts)].sort((a,b)=>a-b);for(let i=1;i<ts.length;i++){const ps=[ts[i-1],ts[i]].map(t=>a.map((v,i)=>v+t*u[i])),ks=ps.map(key);ps.forEach((p,i)=>{if(!nodes.has(ks[i]))nodes.set(ks[i],{p,neighbours:[]});});if(!nodes.get(ks[0]).neighbours.includes(ks[1])){nodes.get(ks[0]).neighbours.push(ks[1]);nodes.get(ks[1]).neighbours.push(ks[0]);edges.push(ks);}}}
for(const n of nodes.values())n.neighbours.sort((a,b)=>Math.atan2(nodes.get(a).p[1]-n.p[1],nodes.get(a).p[0]-n.p[0])-Math.atan2(nodes.get(b).p[1]-n.p[1],nodes.get(b).p[0]-n.p[0]));const visited=new Set(),result=[];for(const [a,b] of edges)for(const start of [[a,b],[b,a]]){let [u,v]=start,poly=[],ks=[],safe=0;while(!visited.has(u+'>'+v)&&safe++<edges.length*2+1){visited.add(u+'>'+v);poly.push(nodes.get(u).p);ks.push(u);const nn=nodes.get(v).neighbours,i=nn.indexOf(u),next=nn[(i-1+nn.length)%nn.length];u=v;v=next;if(u===start[0]&&v===start[1])break;}const area=poly.reduce((s,p,i)=>{const q=poly[(i+1)%poly.length];return s+p[0]*q[1]-q[0]*p[1];},0)/2;if(u===start[0]&&v===start[1]&&area>1&&new Set(ks).size===ks.length)result.push({id:ks.slice().sort().join('|'),points:poly,area:area*mpp*mpp});}return result;}
function parseLength(s,unit='m'){s=String(s).trim().toLowerCase();let v;if(/['"ftin]/.test(s)&&!s.endsWith('mm')){const match=s.match(/^\s*(?:(\d+(?:\.\d+)?)\s*(?:ft|'))?\s*(?:(\d+(?:\.\d+)?)\s*(?:in|"))?\s*$/);if(!match)throw Error('Use 6\' 8" or a numeric length.');v=(Number(match[1]||0)*12+Number(match[2]||0))*.0254;}else{const m=s.match(/^(\d+(?:\.\d+)?)\s*(mm|cm|m)?$/);if(!m)throw Error('Enter a positive length.');v=Number(m[1])*(m[2]==='mm'?.001:m[2]==='cm'?.01:m[2]==='m'?1:unit==='ft'?.3048:unit==='in'?.0254:1);}if(!(v>0))throw Error('Enter a positive length.');return v;}
// Interior branch anchors retain the same junction IDs when collinear boundaries
// disappear. Editing such a corner materializes only those boundaries again.
function anchors(w){return w.points.map((p,i)=>({point:p,id:w.junction_ids?.[i],index:i})).concat((w.junction_nodes||[]).map((n,i)=>({...n,index:i+2})));}
function materialize(fs,keys=null){let out=junctions(fs);for(const initial of [...out.filter(w=>w.kind==='wall'&&w.junction_nodes?.length&&(!keys||anchors(w).some(a=>keys.has(a.id))))]){let current=initial.id;for(const n of [...initial.junction_nodes].sort((a,b)=>project(a.point,initial).t-project(b.point,initial).t)){const w=out.find(w=>w.id===current),q=project(n.point,w),next=initial.id.slice(0,48)+':part:'+Array.from(n.id).reduce((h,c)=>((h*31+c.charCodeAt(0))>>>0),0).toString(36);out=split(out,w.id,q.t,next);current=next;}}return out;}
function mergeWalls(fs,ids,newId,defaultHeight=2.5){
 let out=junctions(fs);const set=new Set(ids),ws=out.filter(w=>set.has(w.id)&&w.kind==='wall');if(ws.length<2)throw Error('Select at least two walls.');
 const props=w=>{const p={...w,height_m:w.height_m??defaultHeight};for(const k of ['id','points','junction_ids','junction_nodes','split_root','wall_chain_id'])delete p[k];return p;},base=props(ws[0]);
 const links=new Map();for(const w of ws)for(const a of anchors(w)){if(!links.has(a.id))links.set(a.id,[]);links.get(a.id).push(w.id);}
 const reached=new Set([ws[0].id]);let size;do{size=reached.size;for(const members of links.values())if(members.some(id=>reached.has(id)))members.forEach(id=>reached.add(id));}while(reached.size!==size);
 if(reached.size!==ws.length)throw Error('Cannot merge disconnected walls. Join the intended corners first; gaps are preserved.');
 const first=ws[0],L=dist(...first.points),u=first.points[1].map((v,i)=>(v-first.points[0][i])/L),t=p=>p.reduce((v,x,i)=>v+(x-first.points[0][i])*u[i],0),lineDistance=p=>Math.abs((p[0]-first.points[0][0])*u[1]-(p[1]-first.points[0][1])*u[0]);
 const straight=ws.every(w=>w.points.every(p=>lineDistance(p)<1e-6));
 if(!straight){if([...links.values()].some(a=>a.length>2))throw Error('Select a single connected wall chain, not multiple branches.');for(const w of ws)w.wall_chain_id=newId;return {features:out,ids:ws.map(w=>w.id),kind:'chain',message:'Joined wall chain. Every turn and individual segment is preserved.'};}
 for(const w of ws.slice(1)){const p=props(w),different=[...new Set([...Object.keys(base),...Object.keys(p)])].filter(k=>JSON.stringify(base[k])!==JSON.stringify(p[k]));if(different.length)throw Error('Cannot merge: different '+different.join(', ')+'. Match these properties first; no properties were discarded.');}
 const intervals=ws.map(w=>({w,lo:Math.min(...w.points.map(t)),hi:Math.max(...w.points.map(t))})).sort((a,b)=>a.lo-b.lo);
 for(let i=1;i<intervals.length;i++)if(Math.abs(intervals[i].lo-intervals[i-1].hi)>1e-6)throw Error('Cannot merge overlapping segments or bridge a gap.');
 const lo=intervals[0].lo,hi=intervals.at(-1).hi,at=x=>first.points[0].map((v,i)=>v+u[i]*x),all=ws.flatMap(anchors),outer=x=>all.find(a=>Math.abs(t(a.point)-x)<1e-6),a=outer(lo),b=outer(hi);
 const merged={...copy(first),points:[at(lo),at(hi)],junction_ids:[a.id,b.id],wall_chain_id:newId};delete merged.split_root;
 const outsideKeys=new Set(out.filter(w=>w.kind==='wall'&&!set.has(w.id)).flatMap(w=>anchors(w).map(a=>a.id)));
 merged.junction_nodes=[...new Map(all.filter(n=>t(n.point)>lo+1e-6&&t(n.point)<hi-1e-6&&outsideKeys.has(n.id)).map(n=>[n.id,{id:n.id,point:copy(n.point)}])).values()];
 const original=hosted(out);
 for(const o of out.filter(o=>set.has(o.host_wall_id))){const old=original.find(f=>f.id===o.id),host=ws.find(w=>w.id===o.host_wall_id),reversed=t(host.points[1])<t(host.points[0]);o.offset=Math.min(...old.points.map(t))-lo;o.host_wall_id=merged.id;if(reversed){o.hinge_end=!o.hinge_end;if(o.normal_offset!==undefined)o.normal_offset=-o.normal_offset;}}
 out=out.filter(f=>!set.has(f.id));out.push(merged);out=hosted(out);for(const o of out.filter(f=>f.host_wall_id===merged.id))checkOpening(out,o);
 return {features:out,ids:[merged.id],kind:'wall',message:'Merged into one wall. Openings and branch junctions retained.'};
}
function moveWalls(fs,ids,delta){const base=junctions(fs),keys=new Set(base.filter(w=>ids.includes(w.id)).flatMap(w=>anchors(w).map(a=>a.id))),out=materialize(base,keys);for(const w of out.filter(w=>w.kind==='wall'))w.points=w.points.map((p,i)=>keys.has(w.junction_ids[i])?p.map((v,j)=>v+delta[j]):p);return checkJunctionChange(fs,hosted(out));}
function boxSelect(fs,a,b){const lo=a.map((v,i)=>Math.min(v,b[i])),hi=a.map((v,i)=>Math.max(v,b[i]));return fs.filter(w=>w.kind==='wall'&&w.points.every(p=>p.every((v,i)=>v>=lo[i]&&v<=hi[i]))).map(w=>w.id);}
function crossing(a,b){const p=a.points[0],q=b.points[0],u=a.points[1].map((v,i)=>v-p[i]),v=b.points[1].map((x,i)=>x-q[i]),den=u[0]*v[1]-u[1]*v[0];if(Math.abs(den)<1e-9)return null;const d=q.map((x,i)=>x-p[i]),t=(d[0]*v[1]-d[1]*v[0])/den,s=(d[0]*u[1]-d[1]*u[0])/den;return t>=0&&t<=1&&s>=0&&s<=1?p.map((x,i)=>x+t*u[i]):null;}
// All tolerances are supplied by the view in source pixels per screen pixel.
// X/Y and face alignment never imply a topological connection. Reference-line
// point targets (including perpendicular feet) may explicitly form junctions.
function smartSnap(p,fs,{tolerance=8,exclude=[],enabled=true,origin=null,face=false,previous=null,connections=true,align=true}={}){
 if(!enabled)return {point:[...p],hint:'',guides:[],key:null,target:null};
 const walls=junctions(fs).filter(w=>w.kind==='wall'),omitted=new Set(exclude.map(e=>e.id+':'+e.index)),candidates=[],refs=[];
 const add=(q,key,hint,target=null,guide=null)=>{const d=dist(p,q);if(d<=tolerance*(previous===key?1.35:1))candidates.push({point:q,key,hint,target:connections?target:null,guides:guide?[guide]:[],distance:d-(previous===key?tolerance*.25:0)});};
 for(const w of walls){const whole=exclude.some(e=>e.id===w.id);for(const a of anchors(w)){if(omitted.has(w.id+':'+a.index))continue;refs.push({point:a.point,key:w.id+':'+a.index});add(a.point,w.id+':e'+a.index,'Endpoint · reference line',{wall:w.id,index:a.index,point:a.point});}if(whole)continue;
  const mid=w.points[0].map((v,i)=>(v+w.points[1][i])/2);refs.push({point:mid,key:w.id+':mid'});add(mid,w.id+':mid','Midpoint · reference line',{wall:w.id,t:dist(w.points[0],mid),point:mid});
  if(origin){const q=project(origin,w);if(q.t>=0&&q.t<=q.length)add(q.point,w.id+':perp','Perpendicular · reference line',{wall:w.id,t:q.t,point:q.point},[origin,q.point]);}
  if(face){for(const side of [-1,1]){const faceWall={...w,points:trace(...w.points,w.thickness,side<0?'inside':'outside')},q=project(p,faceWall);if(q.t>=0&&q.t<=q.length)add(q.point,w.id+':face'+side,'Wall face · alignment only',null,faceWall.points);}}
 }
 for(let i=0;i<walls.length;i++)for(let j=i+1;j<walls.length;j++){const a=walls[i],b=walls[j];if(exclude.some(e=>e.id===a.id||e.id===b.id))continue;const q=crossing(a,b);if(q)add(q,a.id+':x:'+b.id,'Intersection · reference lines',{wall:a.id,t:project(q,a).t,point:q,others:[{wall:b.id,t:project(q,b).t,point:q}]});}
 candidates.sort((a,b)=>Math.abs(a.distance-b.distance)>1e-6?a.distance-b.distance:(a.hint.startsWith('Intersection')?-1:b.hint.startsWith('Intersection')?1:a.key.localeCompare(b.key))); if(candidates.length){const best=candidates[0];if(connections&&best.hint.startsWith('Wall face')){const q=junctionTarget(p,fs,tolerance,exclude);if(q&&q.distance<best.distance)return {point:q.point,target:q,hint:'Reference line · T junction',key:q.wall+':line',guides:[]};}if(!best.guides.length&&origin)best.guides=[[origin,best.point]];return best;}
 // Interior projection comes after identifiable points, and before X/Y alignment.
 if(connections){const q=junctionTarget(p,fs,tolerance,exclude);if(q)return {point:q.point,target:q,hint:'Reference line · T junction',key:q.wall+':line',guides:[]};}
 if(!align)return {point:[...p],guides:[],target:null,hint:'',key:null};
 const result={point:[...p],guides:[],target:null,hint:'',key:null};for(let axis=0;axis<2;axis++){const nearby=refs.map(r=>({...r,d:Math.abs(p[axis]-r.point[axis])-(previous==='align:'+r.key?tolerance*.2:0)})).filter(r=>r.d<=tolerance).sort((a,b)=>a.d-b.d||a.key.localeCompare(b.key));if(nearby.length){result.point[axis]=nearby[0].point[axis];result.guides.push([nearby[0].point,[...result.point]]);result.hint='Aligned · reference line';result.key='align:'+nearby[0].key;}}
 return result;
}
function snapOpening(fs,id,wanted,options){
 const o=fs.find(o=>o.id===id),w=openingHost(fs,o),L=dist(...w.points),u=w.points[1].map((v,i)=>(v-w.points[0][i])/L),range=openingRange(fs,o),candidates=[];
 if(!options.enabled)return {offset:wanted,guides:[],hint:'',key:null};
 const add=(t,edge,key,hint,ref)=>{const offset=t-edge,p=w.points[0].map((v,i)=>v+u[i]*t),distance=Math.abs(offset-wanted),tol=options.tolerance*(options.previous===key?1.35:1);if(distance<=tol&&offset>=range.min&&offset<=range.max)candidates.push({offset,point:p,hintPoint:p.map((v,i)=>v+[u[1],-u[0]][i]*(w.thickness/2+options.tolerance/8*24)),guides:[[ref,p]],hint,key,distance:distance-(options.previous===key?options.tolerance*.25:0)});};
 for(const wall of junctions(fs).filter(f=>f.kind==='wall')){
  const refs=[...anchors(wall).map(n=>({...n,type:'Endpoint'})),{point:wall.points[0].map((v,i)=>(v+wall.points[1][i])/2),id:'mid',type:'Midpoint'}];
  for(const r of refs)for(const edge of [0,o.width]){const base=wall.id+':'+r.id+':'+edge,q=project(r.point,w);
   if(q.distance<1e-6)add(q.t,edge,base+':point',r.type+' · on host',r.point);
   else{for(let axis=0;axis<2;axis++)if(Math.abs(u[axis])>1e-8)add((r.point[axis]-w.points[0][axis])/u[axis],edge,base+':axis'+axis,'Aligned · on host',r.point);
    if(q.t>=0&&q.t<=L)add(q.t,edge,base+':perp','Perpendicular · on host',r.point);}
  }
  if(options.face&&wall.id!==w.id)for(const side of ['inside','outside']){const face={...wall,points:trace(...wall.points,wall.thickness,side)},p=crossing(w,face);if(p)for(const edge of [0,o.width])add(project(p,w).t,edge,wall.id+':face:'+side+':'+edge,'Wall face · on host',face.points[0]);}
 }
 for(const q of openingPeers(fs,o,w))for(const [t,label] of [[q.offset,'Opening edge'],[q.offset+q.width/2,'Opening centre'],[q.offset+q.width,'Opening edge']])for(const edge of [0,o.width/2,o.width])add(t,edge,'opening:'+t+':'+edge,label,w.points[0].map((v,i)=>v+u[i]*t));
 // Other nearby walls can provide edge/centre alignment without changing host.
 for(const q of hosted(fs).filter(q=>q.id!==o.id&&['door','window','sliding_door'].includes(q.kind)&&q.host_wall_id!==w.id)){
  const refs=[...q.points,q.points[0].map((v,i)=>(v+q.points[1][i])/2)];
  for(const [index,r] of refs.entries())for(const edge of [0,o.width/2,o.width]){const projected=project(r,w);if(projected.distance>Math.max(L,dist(...q.points))*1.5)continue;for(let axis=0;axis<2;axis++)if(Math.abs(u[axis])>1e-8)add((r[axis]-w.points[0][axis])/u[axis],edge,'opening:'+q.id+':'+index+':'+axis+':'+edge,(index===2?'Opening centre':'Opening edge')+' · aligned',r);}
 }
 add(L/2,o.width/2,'host-centre','Centred on wall',w.points[0].map((v,i)=>v+u[i]*L/2));
 candidates.sort((a,b)=>a.distance-b.distance||a.key.localeCompare(b.key));return candidates[0]||{offset:wanted,guides:[],hint:'',key:null};
}

// Membership is explicit and independent of shared junction topology.
function chainMembers(fs,id){const w=fs.find(w=>w.id===id&&w.kind==='wall');if(!w)return [];return w.wall_chain_id?fs.filter(f=>f.kind==='wall'&&f.wall_chain_id===w.wall_chain_id).map(f=>f.id):[id];}
function expandChains(fs,ids){return [...new Set(ids.flatMap(id=>chainMembers(fs,id)))];}
function mergeChain(fs,ids,newId){
 // Object membership retains every segment and its properties. Do not validate it
 // through mergeWalls: that operation removes segments and must reject data loss.
 const selected=expandChains(fs,ids),normalized=junctions(fs),ws=normalized.filter(w=>selected.includes(w.id));
 if(ws.length<2)throw Error('Select at least two walls.');
 const links=new Map();for(const w of ws)for(const a of anchors(w)){if(!links.has(a.id))links.set(a.id,new Set());links.get(a.id).add(w.id);}
 const reached=new Set([ws[0].id]);let size;do{size=reached.size;for(const members of links.values())if([...members].some(id=>reached.has(id)))members.forEach(id=>reached.add(id));}while(reached.size!==size);
 if(reached.size!==ws.length)throw Error('Cannot merge disconnected walls. Join the intended corners first; gaps are preserved.');
 if([...links.values()].some(a=>a.size>2))throw Error('Select a single connected wall chain, not multiple branches.');
 // A connected selection can still double back over another member. Thick faces
 // touching is fine; duplicated reference-line spans are not a valid chain.
 for(let i=0;i<ws.length;i++)for(const other of ws.slice(i+1)){
  const w=ws[i],L=dist(...w.points),u=w.points[1].map((v,j)=>(v-w.points[0][j])/L),relative=other.points.map(p=>p.map((v,j)=>v-w.points[0][j]));
  if(relative.every(p=>Math.abs(p[0]*u[1]-p[1]*u[0])<1e-6)){
   const ts=relative.map(p=>p[0]*u[0]+p[1]*u[1]);
   if(Math.min(L,Math.max(...ts))-Math.max(0,Math.min(...ts))>1e-6)throw Error('Cannot merge overlapping wall segments. Remove duplicate spans first.');
  }
 }
 const out=copy(fs);for(const w of out)if(selected.includes(w.id)){w.junction_ids=normalized.find(n=>n.id===w.id).junction_ids;w.wall_chain_id=newId;}
 return {features:out,ids:selected};
}
function unmergeChain(fs,chain){const out=copy(fs);for(const w of out)if(w.wall_chain_id===chain)delete w.wall_chain_id;return out;}
function externalConnections(fs,ids){const rows=junctions(fs),selected=new Set(ids),keys=new Set(rows.filter(w=>selected.has(w.id)).flatMap(w=>anchors(w).map(a=>a.id)));return rows.filter(w=>w.kind==='wall'&&!selected.has(w.id)).flatMap(w=>anchors(w).filter(a=>keys.has(a.id)).map(a=>({wall:w.id,junction:a.id,point:a.point})));}
function detachOutside(fs,ids,newId){const out=junctions(fs),keys=new Set(externalConnections(out,ids).map(c=>c.junction)),map=new Map([...keys].map((k,i)=>[k,'j:object:'+newId+':'+i]));for(const w of out.filter(w=>ids.includes(w.id))){w.junction_ids=w.junction_ids.map(k=>map.get(k)||k);for(const a of w.junction_nodes||[])a.id=map.get(a.id)||a.id;}return out;}
function moveObject(fs,ids,delta){const selected=new Set(expandChains(fs,ids));if(externalConnections(fs,[...selected]).length)throw Error('Move blocked: this object is connected to outside walls. Detach outside connections or cancel; no walls have moved.');const out=copy(fs);for(const w of out.filter(w=>w.kind==='wall'&&selected.has(w.id))){w.points=w.points.map(p=>p.map((v,i)=>v+delta[i]));for(const a of w.junction_nodes||[])a.point=a.point.map((v,i)=>v+delta[i]);}return checkJunctionChange(fs,hosted(out));}

const api={chainMembers,expandChains,mergeChain,unmergeChain,externalConnections,detachOutside,moveObject,anchors,materialize,mergeWalls,moveWalls,boxSelect,smartSnap,snapOpening,junctions,members,junctionTarget,connectEndpoint,detachEndpoint,copy,dist,hosted,project,checkOpening,openingRange,slideOpening,snap,trace,moveEndpoint,split,issues,rooms,parseLength};if(typeof module!=='undefined')module.exports=api;else window.TraceGeometry=api;
})();
