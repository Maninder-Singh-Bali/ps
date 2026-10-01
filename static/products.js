(()=>{
 let found=[],request=0;
 const money=p=>p.price==null?'Price not supplied':(p.currency?p.currency+' ':'')+Number(p.price).toLocaleString(undefined,{maximumFractionDigits:2});
 function cards(items){return items.map(p=>`<article class="product-card"><a href="${esc(p.url)}" target="_blank" rel="noopener noreferrer"><img src="/product-photo/${p.id}" alt="${esc(p.title)}" loading="lazy"></a><div><small>${esc(p.retailer)}${p.brand?' · '+esc(p.brand):''}</small><h3>${esc(p.title)}</h3><div class="product-price">${esc(money(p))}</div><p class="help">${esc(p.availability)} · Checked ${new Date(p.checked*1000).toLocaleString()}</p><p class="help">${esc(p.local_note||'Confirm delivery with the retailer.')}</p><p>${esc(p.match_note||'Verified from retailer product metadata. Compare the exact variant before buying.')}</p>${p.dimensions?`<p class="help">${esc(p.dimensions)}</p>`:'<p class="help">Dimensions: check the retailer page before placement.</p>'}<div class="actions"><a class="btn small" href="${esc(p.url)}" target="_blank" rel="noopener noreferrer">View product ↗</a><button class="btn small primary" data-product="add" data-id="${p.id}">Use as reference</button></div></div></article>`).join('')}
 async function open(){
  if(!R())return;found=[];request++;
  showModal('Discover furniture & looks',`<p class="help">Search real retailer products, then add your chosen piece to this room. Online lookup sends your search words; your floor plan and room photos stay local.</p><div class="product-search"><label class="field"><span>Furniture or look</span><input id="product-query" placeholder="e.g. lounge chair, marble coffee table, blue vase" value="lounge chair"></label><label class="field"><span>Market</span><select id="product-market"><option value="IN">India · INR</option><option value="international">International · original currency</option><option value="both">Both markets</option></select></label><button class="btn primary" data-product="search">Find products</button></div><div class="product-links"><a id="pinterest-discovery" class="btn ghost small" href="https://www.pinterest.com/search/pins/?q=lounge%20chair%20interior" target="_blank" rel="noopener noreferrer">Explore looks on Pinterest ↗</a><span class="help">Pinterest is inspiration. Verify a retailer listing before treating it as purchasable.</span></div><details class="product-link-entry"><summary>Already found a product? Paste its retailer link</summary><div class="actions"><input id="product-link" type="url" placeholder="https://retailer.com/products/…" aria-label="Retailer product link"><button class="btn" data-product="lookup">Verify product</button></div></details><p role="status" id="product-status">Choose a market and search. Current sources: Dekor Company (India), Olive + Wild (international); other retailers can be checked by product link.</p><div class="product-grid" id="product-results"></div>`,btn('Close','close-modal'),'product-discovery');
  $('#product-market').value=localStorage.getItem('pixeloid-market')||'IN';
  $('#product-query').addEventListener('input',()=>{$('#pinterest-discovery').href='https://www.pinterest.com/search/pins/?q='+encodeURIComponent($('#product-query').value+' interior furniture')});
  const current=request;
  $('#product-status').insertAdjacentHTML('beforebegin','<div class="notice" id="product-local-area">Reading the saved project area locally…</div>');
  try{const area=await api(`/api/projects/${pid}/rooms/${rid}/local-area`,{},'GET');if(current!==request||modalType!=='product-discovery')return;$('#product-local-area').textContent=area.label+' · Coordinates stay on this PC. Delivery is not yet verified.';if(area.city){$('#product-local-area').insertAdjacentHTML('beforeend',' <small>Area data: <a href="https://www.geonames.org/" target="_blank" rel="noopener noreferrer">GeoNames</a> · CC BY 4.0.</small>');const q=area.city+' '+area.region+' furniture showroom';$('#product-local-area').insertAdjacentHTML('beforeend',` <a href="https://www.google.com/maps/search/${encodeURIComponent(q)}" target="_blank" rel="noopener noreferrer">Find nearby shops ↗</a>`)}
  }catch(e){if($('#product-local-area'))$('#product-local-area').textContent=e.message}
 }
 window.augmentProductDiscovery=()=>{if(tab!=='references'||!R())return;const button=$('[data-action="upload-reference"]');if(button&&!$('[data-product="open"]'))button.parentElement.insertAdjacentHTML('beforeend','<button class="btn small" data-product="open">Discover products</button>');
  document.querySelectorAll('.refs [data-action="remove-ref"]').forEach(b=>{const a=A(b.dataset.id);if(a?.source_product&&!b.parentElement.querySelector('.product-source')){const p=a.source_product;b.parentElement.insertAdjacentHTML('afterend',`<a class="product-source help" href="${esc(p.url)}" target="_blank" rel="noopener noreferrer">${esc(p.retailer)} · View product ↗</a>`)}});
 };
 document.addEventListener('click',async e=>{
  const b=e.target.closest('[data-product]');if(!b)return;
  if(b.dataset.product==='open')return open();
  if(modalType!=='product-discovery')return;
  const token=++request,project=pid,room=rid;const status=$('#product-status');b.disabled=true;
  try{
   if(b.dataset.product==='add'){
    status.textContent='Saving the product image and purchase details to this room…';await api(`/api/projects/${project}/rooms/${room}/add-product`,{product_id:b.dataset.id});await refresh(true);if(modalType==='product-discovery')status.textContent='Reference saved with retailer link. Set its placement before generating.';toast('Product added as a reference.');
   }else{
    status.textContent='Checking retailer listings, prices and availability…';$('#product-results').innerHTML='';
    if(b.dataset.product==='search'){
     const market=$('#product-market').value;localStorage.setItem('pixeloid-market',market);
     const result=await api('/api/products/search',{project_id:project,room_id:room,query:$('#product-query').value,market});if(token!==request||modalType!=='product-discovery')return;
     found=result.items;status.textContent=`${found.length} product listings found. ${result.note} ${result.warnings.join(' ')}`;
    }else{const result=await api('/api/products/lookup',{url:$('#product-link').value});if(token!==request||modalType!=='product-discovery')return;found=[result];status.textContent='Retailer details checked. Confirm the variant, delivery and current price with the seller.'}
    $('#product-results').innerHTML=cards(found);
   }
  }catch(err){if(modalType==='product-discovery')status.textContent=err.message}finally{b.disabled=false}
 });
})();
