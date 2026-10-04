'use strict';

// Review the saved generation inputs, not a potentially newer room layout.
function planComparisonData(job) {
  const scene=job?.scene_ticket?.content||job?.scene_manifest?.content;
  if(!scene?.plan?.id||!scene.room?.bbox)return null;
  return {planId:scene.plan.id,bbox:scene.room.bbox,features:scene.drawing?.features||[],
    items:scene.room.furniture_layout?.items||[],products:scene.products||[],
    heading:scene.room.furniture_layout?.camera_heading??null,
    notes:scene.room.notes||'',guideId:job.layout_guide_id||null,
    assumptions:job.perspective_layout?.assumptions||[],dimensions:job.perspective_layout?.dimensions||null};
}
if(typeof module!=='undefined')module.exports={planComparisonData};

if(typeof document!=='undefined'){
  function mapMarkup(data,plan){
    const width=plan.width,height=plan.height,b=data.bbox;
    const lines=data.features.map(f=>`<line x1="${f.points[0][0]}" y1="${f.points[0][1]}" x2="${f.points[1][0]}" y2="${f.points[1][1]}" class="pc-${esc(f.kind)}"/>`).join('');
    const size=Math.max(b[2]*width,b[3]*height)*.034;
    const points=data.items.map((v,i)=>{
      const x=(b[0]+v.x*b[2])*width,y=(b[1]+v.y*b[3])*height;
      return `<g transform="translate(${x} ${y})"><g transform="rotate(${v.angle||0})"><path d="M0 0 V${-size*2.4} m${-size*.45} ${size*.65} L0 ${-size*2.4} l${size*.45} ${size*.65}" class="pc-facing"/></g><circle r="${size}"/><text y="${size*.34}" font-size="${size*1.1}">${i+1}</text></g>`;
    }).join('');
    return `<svg viewBox="${b[0]*width} ${b[1]*height} ${b[2]*width} ${b[3]*height}" role="img" aria-label="Saved corrected lines and furniture markers"><rect x="${b[0]*width}" y="${b[1]*height}" width="${b[2]*width}" height="${b[3]*height}" fill="white"/>${lines}${points}</svg>`;
  }
  document.addEventListener('click',e=>{
    const button=e.target.closest('[data-action="compare-plan"]');if(!button)return;
    const asset=A(button.dataset.id),job=state.jobs[asset?.job_id],data=planComparisonData(job);
    if(!data){toast('This older image has no saved plan snapshot. Review its original project inputs.');return}
    const plan=A(data.planId),room=P().rooms.find(r=>r.id===button.dataset.room);
    if(!plan){toast('The source plan is unavailable.');return}
    const b=data.bbox,legend=data.items.map((item,i)=>`<li><b>${i+1}</b> ${esc(data.products.find(p=>p.id===item.asset_id)?.category||'Furniture')}</li>`).join('');
    const media=(id,alt)=>`<img src="${url(id)}" alt="${esc(alt)}" data-action="view" data-id="${id}">`;
    showModal('Plan comparison · '+esc(room?.name||'Room'),`<p class="pc-intro">These are the saved inputs for this image version. Check openings, connections, furniture count and placement. A guided render can still depart from the plan.</p><div class="pc-grid"><section><h3>1 · Source plan section</h3><div class="pc-plan-crop" style="aspect-ratio:${plan.width*b[2]/(plan.height*b[3])}"><img src="${url(plan.id)}" alt="Original floor-plan section used for this image" style="width:${100/b[2]}%;height:${100/b[3]}%;left:${-100*b[0]/b[2]}%;top:${-100*b[1]/b[3]}%"></div><p>${Math.round(plan.width*b[2])} × ${Math.round(plan.height*b[3])} source pixels. No new measured detail is recovered by enlargement.</p><details><summary>Saved drawing corrections & furniture</summary><div class="pc-corrected">${mapMarkup(data,plan)}</div><ul class="pc-legend">${legend}</ul><p>Corrected line overlay only; original vector details are shown in the source plan. Dashed gold = door segment; blue = window.</p></details></section><section><h3>2 · Camera layout guide</h3>${data.guideId?media(data.guideId,'Perspective layout guide used for generation'):'<p>No perspective guide was supplied for this version.</p>'}<p>${data.heading===null?'Camera direction not set.':`Camera looks ${data.heading}° clockwise from plan-up.`} ${data.dimensions?'Scale uses saved calibration.':'Proportions only — room dimensions are unmeasured.'}</p><p>Heights and lens are illustrative defaults. This is a layout sketch, not a verified 3D reconstruction.</p></section><section><h3>3 · Generated image</h3>${media(asset.id,'Generated image compared with floor plan')}<p class="pc-verdict">${asset.status==='rejected'?'Needs revision':asset.status==='approved'?'Approved for this version':'Awaiting visual review'}</p>${asset.review_note?`<p>${esc(asset.review_note)}</p>`:''}<p>Video stays locked until an image is approved.</p></section></div><details class="pc-notes"><summary>Saved room direction</summary><p>${esc(data.notes)}</p></details>`,btn('Close','close-modal','','ghost'),'plan-comparison');
    $('#modal').classList.add('plan-comparison-dialog');
  });
}
