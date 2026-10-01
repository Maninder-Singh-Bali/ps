'use strict';

function placementPoint(clientX,clientY,rect,bbox,full=false,clamp=false){
  let x=(clientX-rect.left)/rect.width,y=(clientY-rect.top)/rect.height;
  if(full){x=(x-bbox[0])/bbox[2];y=(y-bbox[1])/bbox[3]}
  if(!clamp&&(x<0||x>1||y<0||y>1))return null;
  return {x:Math.max(0,Math.min(1,x)),y:Math.max(0,Math.min(1,y))};
}
if(typeof module!=='undefined')module.exports={placementPoint};

if(typeof document!=='undefined'){
  let editor=null;
  function enabledItems(){return editor.refs.filter(a=>a.enabled!==false)}
  function setDirty(){editor.dirty=true;const el=$('#placement-save-note');if(el)el.textContent='Unsaved changes'}
  function renderMarkers(){
    const layer=$('#placement-markers');if(!layer||!editor)return;
    const b=editor.room.bbox;
    layer.innerHTML=Object.entries(editor.positions).map(([id,p])=>{
      const asset=editor.refs.find(a=>a.id===id);if(!asset)return '';
      const x=editor.full?b[0]+p.x*b[2]:p.x,y=editor.full?b[1]+p.y*b[3]:p.y;
      return `<button type="button" class="furniture-marker ${id===editor.selected?'selected':''} ${asset.enabled===false?'inactive':''}" data-marker="${id}" style="left:${x*100}%;top:${y*100}%" aria-label="Move ${esc(asset.category||'furniture')} marker"><i style="transform:rotate(${p.angle}deg)" aria-hidden="true">↑</i><span>${editor.refs.indexOf(asset)+1}</span></button>`;
    }).join('');
    const p=editor.positions[editor.selected];
    const fields=$('#placement-size-fields');if(fields){const size=p?.size||{};fields.innerHTML=`<label class="field"><span>Width</span><input type="number" min="0.01" step="any" data-placement-size="width" value="${size.width||''}" ${p?'':'disabled'}></label><label class="field"><span>Depth</span><input type="number" min="0.01" step="any" data-placement-size="depth" value="${size.depth||''}" ${p?'':'disabled'}></label><select aria-label="Furniture dimension units" data-placement-size="unit"><option value="m">Metres</option><option value="ft" ${size.unit==='ft'?'selected':''}>Feet</option></select>`;}

    const label=$('#placement-facing');if(label)label.textContent=p?`Facing ${p.angle}° clockwise from plan-up`:'Click inside the room to place this item';
    document.querySelectorAll('[data-placement-rotate],[data-placement-remove]').forEach(b=>b.disabled=!p);
    document.querySelectorAll('[data-placement-select]').forEach(b=>{
      b.classList.toggle('selected',b.dataset.placementSelect===editor.selected);
      b.setAttribute('aria-pressed',String(b.dataset.placementSelect===editor.selected));
      b.querySelector('small').textContent=editor.positions[b.dataset.placementSelect]?'Placed on map':'Not placed';
    });
  }
  function controlCompass(plan){return (window.planCompassMarkup?planCompassMarkup(plan):'')+btn('Refine drawing','refine-drawing','','small ghost')}
  function renderEditor(){
    const e=editor,b=e.room.bbox,plan=e.plan;
    const view=e.full?[0,0,1,1]:b,ratio=plan.width*view[2]/(plan.height*view[3]);
    const displayId=e.originalPlan?plan.id:plan.cad_redraw_id||plan.vector_preview_id||plan.clear_preview_id||plan.id;
    $('#placement-canvas-host').innerHTML=`<div class="placement-stage" id="placement-stage" style="aspect-ratio:${ratio};width:min(100%,${60*ratio}vh)" role="group" aria-label="${esc(e.room.name)} furniture placement map"><img src="${url(displayId)}" draggable="false" alt="Floor-plan section for ${esc(e.room.name)}" style="width:${100/view[2]}%;height:${100/view[3]}%;left:${-100*view[0]/view[2]}%;top:${-100*view[1]/view[3]}%">${e.full?`<div class="placement-room-outline" style="left:${b[0]*100}%;top:${b[1]*100}%;width:${b[2]*100}%;height:${b[3]*100}%"></div>`:''}<div id="placement-markers"></div></div>`;
    document.querySelectorAll('[data-placement-view]').forEach(b=>b.classList.toggle('selected',(b.dataset.placementView==='full')===e.full));
    renderMarkers();bindMapPointer();
  }
  function bindMapPointer(){
    const stage=$('#placement-stage');let drag=null;
    stage.onpointerdown=event=>{
      if(event.button!==0||!editor.selected)return;
      const marker=event.target.closest('[data-marker]');
      if(marker)editor.selected=marker.dataset.marker;
      const point=placementPoint(event.clientX,event.clientY,stage.getBoundingClientRect(),editor.room.bbox,editor.full);
      if(!point){toast('Place furniture inside the highlighted room.');return}
      event.preventDefault();stage.setPointerCapture(event.pointerId);
      drag={id:editor.selected,pointer:event.pointerId,previous:editor.positions[editor.selected]?{...editor.positions[editor.selected]}:null};
      editor.positions[drag.id]={...editor.positions[drag.id],...point,angle:editor.positions[drag.id]?.angle||0};
      renderMarkers();
    };
    stage.onpointermove=event=>{
      if(!drag||event.pointerId!==drag.pointer)return;
      const point=placementPoint(event.clientX,event.clientY,stage.getBoundingClientRect(),editor.room.bbox,editor.full,true);
      editor.positions[drag.id]={...editor.positions[drag.id],...point};renderMarkers();
    };
    stage.onpointerup=event=>{
      if(!drag||event.pointerId!==drag.pointer)return;
      if(JSON.stringify(editor.positions[drag.id])!==JSON.stringify(drag.previous))setDirty();
      drag=null;stage.releasePointerCapture(event.pointerId);
    };
    stage.onpointercancel=()=>{if(drag){if(drag.previous)editor.positions[drag.id]=drag.previous;else delete editor.positions[drag.id];drag=null;renderMarkers()}};
    stage.onkeydown=event=>{
      const marker=event.target.closest('[data-marker]');if(!marker||!['ArrowUp','ArrowDown','ArrowLeft','ArrowRight'].includes(event.key))return;
      event.preventDefault();editor.selected=marker.dataset.marker;const p=editor.positions[editor.selected],step=event.shiftKey?.05:.01;
      p.x=Math.max(0,Math.min(1,p.x+(event.key==='ArrowLeft'?-step:event.key==='ArrowRight'?step:0)));
      p.y=Math.max(0,Math.min(1,p.y+(event.key==='ArrowUp'?-step:event.key==='ArrowDown'?step:0)));
      setDirty();renderMarkers();$('#placement-markers').querySelector('[data-marker="'+editor.selected+'"]').focus();
    };
  }
  window.openPlacementMap=async function(selected){
    const r=R(),plan=A(r?.plan_id);
    if(!r)return;
    if(!plan||!r.bbox){
      showModal('Furniture placement map','<p>Mark this section on your floor plan first. Then you can place furniture directly on its map.</p>',btn('Open floor plan','placement-open-plan','','primary'));
      return;
    }
    if(!plan.cad_redraw_id&&!plan.vector_preview_id&&Math.max(plan.width,plan.height)<2000){
      try{await api(`/api/projects/${pid}/plans/${plan.id}/enhance`);await refresh(true);if(R()?.id!==r.id)return;return openPlacementMap(selected)}
      catch(error){toast('Using the original plan: '+error.message)}
    }
    const layout=r.furniture_layout,valid=layout?.plan_id===r.plan_id&&JSON.stringify(layout.bbox)===JSON.stringify(r.bbox);
    const refs=r.references.map(A).filter(Boolean);
    editor={project:pid,room:structuredClone(r),plan,refs,positions:Object.fromEntries((valid?layout.items:[]).filter(p=>r.references.includes(p.asset_id)).map(p=>[p.asset_id,{x:p.x,y:p.y,angle:p.angle,...(p.size?{size:structuredClone(p.size)}:{})}])),selected:refs.some(a=>a.id===selected)?selected:refs.find(a=>a.enabled!==false)?.id||refs[0]?.id,full:false,dirty:false,cameraHeading:layout?.camera_heading||0};
    showModal('Furniture placement · '+esc(r.name),`<p class="placement-intro">Select an item, then click its position on the plan. Drag its marker to move it; the arrow shows which way it faces.</p>${layout?.items?.length&&!valid?'<p class="notice">The room boundary changed. Please place the items again on this updated section.</p>':''}<div class="placement-editor"><section><div class="placement-toolbar"><div class="actions"><button class="btn small selected" data-placement-view="room">Room section</button><button class="btn small" data-placement-view="full">Full plan</button></div>${controlCompass(plan)}</div><div class="placement-canvas-host" id="placement-canvas-host"></div></section><aside class="placement-items"><label class="field"><span>Camera looks toward</span><select id="placement-camera">${[[0,'↑ Top of plan'],[90,'→ Right of plan'],[180,'↓ Bottom of plan'],[270,'← Left of plan']].map(([v,l])=>`<option value="${v}" ${editor.cameraHeading===v?'selected':''}>${l}</option>`).join('')}</select><small>Relates the map to the photograph.</small></label><h3>Furniture in this room</h3>${refs.length?refs.map((a,i)=>`<button class="placement-item" data-placement-select="${a.id}" aria-pressed="false"><img src="${url(a.id)}" alt=""><span><strong>${i+1}. ${esc(a.category||'Furniture')}</strong><small>Not placed</small>${a.enabled===false?'<em>Disabled for generation</em>':''}</span></button>`).join(''):'<p>Add furniture reference images to this room first.</p>'}<div class="placement-direction"><p id="placement-facing"></p><div class="actions"><button class="btn small" data-placement-rotate="-45">↶ Rotate</button><button class="btn small" data-placement-rotate="45">Rotate ↷</button><button class="btn small ghost" data-placement-remove>Clear position</button></div></div><details class="placement-size"><summary>Optional furniture dimensions</summary><div id="placement-size-fields"></div></details><p class="help">Your visual markers define relative positions and facing directions. The dashboard converts them into camera-relative instructions automatically. Dimensions add physical scale when available. Review the rendered placement before approval.</p></aside></div>`,`<span id="placement-save-note">${valid&&layout.items.length?'Saved placements loaded':'No positions saved yet'}</span>${btn('Cancel','close-modal','','ghost')}${btn('Save placements','save-placement-map','','primary')}`,'placement');
    $('#modal').classList.add('placement-dialog');
    if(plan.cad_redraw_id||plan.vector_preview_id||plan.clear_preview_id){const toolbar=$('.placement-toolbar');toolbar.insertAdjacentHTML('afterend',`<label class="placement-plan-quality"><input type="checkbox" data-placement-original> Show original plan <span>${plan.cad_redraw_id?'CAD-style redraw · check openings against original':plan.vector_preview_id?'Vector outlines traced from your drawing':'Enlarged plan preview'}</span>${plan.cad_redraw_id||plan.vector_preview_id?`<a href="${url(plan.cad_redraw_id||plan.vector_preview_id)}" download="floor-plan.svg">Download SVG</a>`:''}</label>`)}
    renderEditor();
  };
  document.addEventListener('change',e=>{if(!editor)return;if(e.target.id==='placement-camera'){editor.cameraHeading=Number(e.target.value);setDirty()}if(e.target.dataset.placementSize){const p=editor.positions[editor.selected];if(p){const w=Number(document.querySelector('[data-placement-size=width]').value),d=Number(document.querySelector('[data-placement-size=depth]').value),u=document.querySelector('[data-placement-size=unit]').value;if(w&&d)p.size={width:w,depth:d,unit:u};else delete p.size;setDirty()}}if(e.target.matches('[data-placement-original]')&&editor){editor.originalPlan=e.target.checked;renderEditor()}});
  document.addEventListener('click',async event=>{
    const select=event.target.closest('[data-placement-select]'),rotate=event.target.closest('[data-placement-rotate]'),view=event.target.closest('[data-placement-view]');
    if(select&&editor){editor.selected=select.dataset.placementSelect;renderMarkers();return}
    if(rotate&&editor){const p=editor.positions[editor.selected];if(p){p.angle=(p.angle+Number(rotate.dataset.placementRotate)+360)%360;setDirty();renderMarkers()}return}
    if(view&&editor){editor.full=view.dataset.placementView==='full';renderEditor();return}
    if(event.target.closest('[data-placement-remove]')&&editor){delete editor.positions[editor.selected];setDirty();renderMarkers();return}
    const action=event.target.closest('[data-action]');if(!action||action.disabled)return;
    if(action.dataset.action==='placement-map'){openPlacementMap(action.dataset.id);return}
    if(action.dataset.action==='placement-open-plan'){$('#modal').close();tab='plan';renderShell();renderMain();return}
    if(action.dataset.action!=='save-placement-map'||!editor)return;
    const e=editor;action.disabled=true;
    try{
      await api(`/api/projects/${e.project}/rooms/${e.room.id}/placement-map`,{revision:e.room.revision,camera_heading:e.cameraHeading,items:Object.entries(e.positions).map(([asset_id,p])=>({asset_id,...p}))});
      $('#modal').close();editor=null;await refresh(true);toast('Furniture placements saved. They will guide the next room image.');
    }catch(err){toast(err.message);action.disabled=false}
  });
}
