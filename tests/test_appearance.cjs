const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync(require.resolve('../static/appearance.js'),'utf8');
function fixture(saved=null,dark=false,blocked=false){
 const listeners={},mediaListeners={},events={},select={value:null},meta={},root={dataset:{},style:{}};
 const storage={value:saved,getItem(){if(blocked)throw Error('blocked');return this.value},setItem(k,v){if(blocked)throw Error('blocked');this.value=v}};
 const media={matches:dark,addEventListener:(k,f)=>mediaListeners[k]=f};
 const doc={documentElement:root,querySelectorAll:selector=>selector==='[data-appearance-choice]'?[select]:[],querySelector:()=>meta,addEventListener:(k,f)=>events[k]=f,getElementById:()=>null};
 const context={document:doc,localStorage:storage,window:{matchMedia:()=>media,addEventListener:(k,f)=>listeners[k]=f}};
 vm.runInNewContext(source,context);
 return {root,storage,media,mediaListeners,listeners,select,meta};
}
let n=0;
for(const osDark of [false,true]){const f=fixture(null,osDark);assert.equal(f.root.dataset.theme,'dark');assert.equal(f.storage.value,null);assert.equal(f.root.style.colorScheme,'dark');n++;}
for(const saved of ['dark','light']){const f=fixture(saved,saved==='light');assert.equal(f.root.dataset.theme,saved);f.media.matches=!f.media.matches;f.mediaListeners.change();assert.equal(f.root.dataset.theme,saved);n++;}
{const f=fixture('system',false);assert.equal(f.root.dataset.theme,'light');f.media.matches=true;f.mediaListeners.change();assert.equal(f.root.dataset.theme,'dark');n++;}
for(const value of ['invalid','',null]){assert.equal(fixture(value).root.dataset.theme,'dark');n++;}
{assert.equal(fixture('light',false,true).root.dataset.theme,'dark');n++;}
{const f=fixture();f.listeners.storage({key:'pixeloid.appearance',newValue:'light'});assert.equal(f.root.dataset.theme,'light');f.listeners.storage({key:'other',newValue:'dark'});assert.equal(f.root.dataset.theme,'light');f.listeners.storage({key:null,newValue:null});assert.equal(f.root.dataset.theme,'dark');n++;}
for(const file of ['index','floor-plan','login','local-guide']){const html=fs.readFileSync(require.resolve('../static/'+file+'.html'),'utf8');assert(html.indexOf('/appearance.js')<html.indexOf('rel="stylesheet"'));assert(!html.match(/<script[^>]*(?:defer|async)[^>]*appearance/));assert(html.includes('data-theme="dark"'));n++;}
const css=fs.readFileSync(require.resolve('../static/appearance.css'),'utf8');
function tokens(theme){const text=theme==='dark'?css.match(/:root\[data-theme=dark\]\s*\{([^}]+)/)[1]:css.match(/:root\s*\{([^}]+)/)[1];return Object.fromEntries([...text.matchAll(/--([\w-]+):\s*(#[\da-f]{6})/g)].map(m=>[m[1],m[2]]));}
function lum(hex){const v=hex.slice(1).match(/../g).map(x=>parseInt(x,16)/255).map(x=>x<=.04045?x/12.92:((x+.055)/1.055)**2.4);return v[0]*.2126+v[1]*.7152+v[2]*.0722;}
for(const theme of ['dark','light']){const t=tokens(theme);for(const [fg,bg] of [['ink','bg'],['ink','surface'],['ink','raised'],['muted','surface'],['accent','soft'],['warning','warning-bg'],['error','error-bg'],['success','success-bg'],['#ffffff','primary'],['#ffffff','primary-hover']]){const a=lum(t[fg]||fg),b=lum(t[bg]);assert((Math.max(a,b)+.05)/(Math.min(a,b)+.05)>=4.5,`${theme} ${fg}/${bg}`);n++;}}
assert(!css.includes('img {filter'));assert(!css.includes('video {filter'));
console.log(`Appearance: ${n} default/persistence/system/bootstrap/contrast checks passed`);
