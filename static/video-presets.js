'use strict';
(() => {
 const native='ltx-native-1080p-v1', preview='ltx-preview-768x432-2s-v1';
 const choices={
  'native-5':{video_preset:native,duration:5,label:'Native 1080p · 5 seconds'},
  'native-8':{video_preset:native,duration:8,label:'Native 1080p · 8 seconds'},
  'preview-2':{video_preset:preview,duration:2,label:'Preview · 768 × 432 · 2 seconds'}
 };
 function controls(key){return `<div class="card-controls"><label class="field">Video preset<select aria-label="Video preset" id="video-preset-${esc(key)}" data-video-choice="${esc(key)}">${Object.entries(choices).map(([value,c])=>`<option value="${value}">${c.label}</option>`).join('')}</select></label><label class="field">Camera movement<select aria-label="Camera movement" id="video-motion-${esc(key)}"><option value="still">Locked camera</option><option value="push">Gentle push in</option><option value="slide">Subtle lateral slide</option></select></label></div><p class="help" id="video-preset-note-${esc(key)}">Native 1080p · no output upscaling. Generation still requires approval and an available phase.</p>`}
 function read(key){const choice=choices[document.getElementById('video-preset-'+key)?.value||'native-5'];if(!choice)throw Error('Choose a supported video preset.');return {video_preset:choice.video_preset,duration:choice.duration,motion:choice.video_preset===preview?'still':document.getElementById('video-motion-'+key)?.value||'still'}}
 function describe(a){if(a?.video_preset===preview)return 'Preview · 768 × 432 · 2 seconds · no output upscaling';if(a?.video_preset===native||a?.native_sampling?.[0]===1920&&a?.native_sampling?.[1]===1088)return `Native 1080p · ${a.duration} seconds · no output upscaling`;return a?.width&&a?.height?`${a.width} × ${a.height} · ${a.duration} seconds`:'Saved clip · resolution not recorded'}
 document.addEventListener('change',e=>{const key=e.target.dataset.videoChoice;if(!key)return;const c=choices[e.target.value],small=c?.video_preset===preview,motion=document.getElementById('video-motion-'+key),note=document.getElementById('video-preset-note-'+key);if(motion){motion.disabled=small;if(small)motion.value='still'}if(note)note.textContent=small?'Preview samples at 768 × 448 and crops to 768 × 432. No upscaling. Frames 0–47 are retained; guided endpoint frame 48 is excluded.':'Native 1080p · no output upscaling. Generation still requires approval and an available phase.';});
 window.VideoPresets={controls,read,describe,choices};
})();
