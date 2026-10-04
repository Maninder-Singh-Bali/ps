'use strict';
(() => {
 const native='ltx-native-1080p-v1', preview='ltx-preview-768x432-2s-v1';
 const drafts=new Map();
 const draft=key=>drafts.get(key)||{choice:'native-5',motion:'still'};
 const choices={
  'native-5':{video_preset:native,duration:5,label:'Native 1080p · 5 seconds'},
  'native-8':{video_preset:native,duration:8,label:'Native 1080p · 8 seconds'},
  'preview-2':{video_preset:preview,duration:2,label:'Preview · 768 × 432 · 2 seconds'}
 };
 function controls(key){const d=draft(key),small=d.choice==='preview-2';return `<div class="card-controls"><label class="field">Video preset<select aria-label="Video preset" id="video-preset-${esc(key)}" data-video-choice="${esc(key)}">${Object.entries(choices).map(([value,c])=>`<option value="${value}" ${d.choice===value?'selected':''}>${c.label}</option>`).join('')}</select></label><label class="field">Camera movement<select aria-label="Camera movement" id="video-motion-${esc(key)}" data-video-motion="${esc(key)}" ${small?'disabled':''}>${[['still','Locked camera'],['push','Gentle push in'],['slide','Subtle lateral slide']].map(([v,n])=>`<option value="${v}" ${(small?'still':d.motion)===v?'selected':''}>${n}</option>`).join('')}</select></label></div><p class="help" id="video-preset-note-${esc(key)}">${small?'Preview · 768 × 432 · 2 seconds · locked camera.':'Native 1080p · no output upscaling. Generation still requires approval and an available phase.'}</p>`}
 function read(key){const choice=choices[document.getElementById('video-preset-'+key)?.value||'native-5'];if(!choice)throw Error('Choose a supported video preset.');return {video_preset:choice.video_preset,duration:choice.duration,motion:choice.video_preset===preview?'still':document.getElementById('video-motion-'+key)?.value||'still'}}
 function describe(a){if(a?.video_preset===preview)return 'Preview · 768 × 432 · 2 seconds · no output upscaling';if(a?.video_preset===native||a?.native_sampling?.[0]===1920&&a?.native_sampling?.[1]===1088)return `Native 1080p · ${a.duration} seconds · no output upscaling`;return a?.width&&a?.height?`${a.width} × ${a.height} · ${a.duration} seconds`:'Saved clip · resolution not recorded'}
 document.addEventListener('change',e=>{const motionKey=e.target.dataset.videoMotion;if(motionKey){drafts.set(motionKey,{...draft(motionKey),motion:e.target.value});return}const key=e.target.dataset.videoChoice;if(!key)return;drafts.set(key,{...draft(key),choice:e.target.value});const c=choices[e.target.value],small=c?.video_preset===preview,motion=document.getElementById('video-motion-'+key),note=document.getElementById('video-preset-note-'+key);if(motion){motion.disabled=small;if(small)motion.value='still'}if(note)note.textContent=small?'Preview samples at 768 × 448 and crops to 768 × 432. No upscaling. Frames 0–47 are retained; guided endpoint frame 48 is excluded.':'Native 1080p · no output upscaling. Generation still requires approval and an available phase.';});
 window.VideoPresets={controls,read,describe,choices};
})();
