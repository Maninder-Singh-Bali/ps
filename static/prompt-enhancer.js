'use strict';

// Conservative local editing: retain the brief rather than inventing design details.
function enhanceStudioPrompt(input, context = {}) {
  if (typeof input !== 'string' || input.trim().length < 3) throw Error('Write a short prompt first.');
  if (input.length > 6000) throw Error('Keep the prompt within 6,000 characters.');
  const corrections = {refrence:'reference',referance:'reference',refrences:'references',furnitures:'furniture',detials:'details',deatils:'details',qaulity:'quality',quailty:'quality',geometery:'geometry',geomatry:'geometry',ligthing:'lighting',realstic:'realistic',relastic:'realistic',enviroment:'environment',backgroud:'background',chandller:'chandelier',chandlier:'chandelier',kitechen:'kitchen',curtian:'curtain',curtians:'curtains',sead:'seed',horisontal:'horizontal',distroyed:'distorted',distryed:'distorted',blochiness:'blotchiness',upscalled:'upscaled',teh:'the',dont:'do not',cant:'cannot',pls:'please'};
  let text = input.trim().replace(/[\t ]+/g, ' ').replace(/\n{3,}/g, '\n\n');
  let corrected = 0;
  text = text.replace(/\b[a-z]+\b/gi, word => {
    const replacement = corrections[word.toLowerCase()];
    if (!replacement) return word;
    corrected++;
    return /^[A-Z]/.test(word) ? replacement[0].toUpperCase()+replacement.slice(1) : replacement;
  });
  const sections = [];
  const append = (title, body) => { if (!text.includes(title+':')) sections.push(title+':\n'+body); };
  if (context.scope === 'reference' && context.category) append('Reference subject', context.category.trim());
  if (context.scope !== 'project' && context.room) append('Room context', context.room+(context.floor?' · '+context.floor:''));
  if (context.keepEnvironment) append('Continuity', 'Use the current room image as the reference for the background, camera viewpoint, walls, openings, stairs and unchanged furniture. Keep these consistent except where the request above explicitly asks for a change.');
  append('Design fidelity', 'Follow the specified object shapes, materials, colours, dimensions, counts and placement. Preserve stated exclusions. Do not add unspecified decorative objects or change other elements.');
  if (!/\b(cartoon|watercolou?r|illustration|stylized|stylised|anime)\b/i.test(text)) append('Photographic finish', 'Use believable material texture, realistic scale and contact shadows, natural reflections, restrained contrast and soft highlight rolloff. Avoid artificial maze patterns, oversharpened edges and waxy smoothing.');
  const prompt = [text,...sections].join('\n\n');
  if (prompt.length > 6000) throw Error('The enhanced version would exceed 6,000 characters. Shorten the original slightly and try again.');
  return {prompt, changes:[corrected ? 'Corrected '+corrected+' common spelling or wording issue'+(corrected===1?'': 's')+'.' : 'Kept your original wording.', 'Added relevant structure and design constraints for review.']};
}

if (typeof module !== 'undefined') module.exports = {enhanceStudioPrompt};
if (typeof document !== 'undefined') {
  const promptUndo = new WeakMap();
  let promptTarget = null, originalPrompt = '';
  const dialog = document.createElement('dialog');
  dialog.id = 'prompt-enhancer';
  dialog.setAttribute('aria-labelledby','enhancer-title');
  document.body.append(dialog);

  window.attachPromptEnhancers = function() {
    [['#reference-prompt-form textarea[name="prompt"]','reference'],['#room-notes','room'],['#project-style','project']].forEach(([selector,scope])=>{
      const target=document.querySelector(selector);
      if(!target || target.dataset.enhancer) return;
      target.dataset.enhancer=scope;
      const bar=document.createElement('div');bar.className='prompt-tools';
      const button=document.createElement('button');button.type='button';button.className='btn small';button.textContent='✧ Enhance prompt';
      const undo=document.createElement('button');undo.type='button';undo.className='btn small ghost';undo.textContent='Undo enhancement';undo.hidden=true;
      bar.append(button,undo);target.closest('.field').after(bar);
      undo.onclick=()=>{target.value=promptUndo.get(target);promptUndo.delete(target);undo.hidden=true;target.dispatchEvent(new Event('input',{bubbles:true}));target.focus()};
      button.onclick=()=>{
        try {
          const form=document.querySelector('#reference-prompt-form'),room=R();
          const result=enhanceStudioPrompt(target.value,{scope,category:scope==='reference'?form.elements.category.value:'',room:scope==='reference'&&!form.elements.use_environment.checked?'':room?.name,floor:room?.floor,keepEnvironment:scope==='reference'?form.elements.use_environment.checked:scope==='room'&&Boolean(room?.anchor_id)});
          promptTarget=target;originalPrompt=target.value;
          dialog.innerHTML=`<div class="modal-head"><h2 id="enhancer-title">Review enhanced prompt</h2><button type="button" class="btn small ghost" data-enhance="close" aria-label="Close prompt enhancement">×</button></div><div class="modal-body"><p class="enhancer-method">Local wording & structure helper</p><p class="help">${esc(result.changes.join(' '))} This helper does not analyse images or infer room geometry.</p><div class="prompt-comparison"><label class="field"><span>Your original</span><textarea readonly aria-label="Original prompt">${esc(originalPrompt)}</textarea></label><label class="field"><span>Enhanced · editable</span><textarea id="enhanced-prompt" aria-label="Enhanced prompt">${esc(result.prompt)}</textarea></label></div><p class="help" id="enhanced-length" role="status"></p></div><div class="modal-footer"><button type="button" class="btn ghost" data-enhance="close">Keep original</button><button type="button" class="btn primary" data-enhance="apply">Use enhanced prompt</button></div>`;
          dialog.querySelector('#enhanced-prompt').addEventListener('input',updateLength);updateLength();dialog.showModal();
        }catch(e){toast(e.message)}
      };
      target._promptUndoButton=undo;
    });
  };
  function updateLength(){const n=dialog.querySelector('#enhanced-prompt').value.length;dialog.querySelector('#enhanced-length').textContent=n.toLocaleString()+' / 6,000 characters · Apply only changes you want.';dialog.querySelector('[data-enhance="apply"]').disabled=n>6000||n<3}
  dialog.addEventListener('click',e=>{
    const action=e.target.closest('[data-enhance]')?.dataset.enhance;if(!action)return;
    if(action==='apply'){
      if(!promptTarget?.isConnected){dialog.close();return}
      if(promptTarget.value!==originalPrompt){toast('Your original changed. Close this preview and enhance the updated text.');return}
      promptUndo.set(promptTarget,originalPrompt);promptTarget.value=dialog.querySelector('#enhanced-prompt').value;promptTarget._promptUndoButton.hidden=false;promptTarget.dispatchEvent(new Event('input',{bubbles:true}));
      toast('Enhanced prompt applied. Save or generate when you are ready.');
    }
    dialog.close();promptTarget?.focus();
  });
}
