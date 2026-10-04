const assert=require('node:assert/strict'),{Viewer,defaults,drawingScale}=require('../static/model-viewer.js');
let observe,callback,frames=0,cancelled=0;global.ResizeObserver=class{constructor(cb){observe=cb}observe(){}disconnect(){}};global.requestAnimationFrame=cb=>{callback=cb;frames++;return frames};global.cancelAnimationFrame=()=>cancelled++;
const canvas={style:{},clientWidth:400,clientHeight:300},viewer=new Viewer(canvas,defaults(),()=>{});let draws=0;viewer.draw=()=>draws++;
for(let i=0;i<50;i++)observe();assert.equal(frames,1);callback();assert.equal(draws,1);observe();viewer.dispose();callback();assert.equal(draws,1);assert.equal(cancelled,1);
for(const [w,h,dpr] of [[800,600,2],[3000,2000,3],[20000,12000,4]])assert(w*h*drawingScale(w,h,dpr)**2<=2097152.00001);
console.log('Viewer resize bursts coalesced, disposed callbacks inert, high-DPI framebuffer bounded');
