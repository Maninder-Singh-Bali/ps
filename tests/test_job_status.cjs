const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync('static/app.js','utf8');
const start=source.indexOf('function jobMarkup('),end=source.indexOf('\n',start);
const ctx={P:()=>({rooms:[]}),A:()=>null,esc:x=>String(x),active:['queued','waiting','running'],generationProgressMarkup:()=>''};vm.createContext(ctx);vm.runInContext(source.slice(start,end),ctx);
for(const status of ['failed','cancelled']){
 const terminal={id:'job',kind:'vision_study',status,stage:'Detector exhausted',report:{coverage_complete:false,coverage:{pending_regions:0,failed_regions:0}}};
 assert(!ctx.jobMarkup(terminal).includes('recover-job'),'Exhausted analysis must not offer retry');
 assert(ctx.jobMarkup({...terminal,report:{coverage_complete:false,coverage:{pending_regions:1}}}).includes('recover-job'));
 assert(ctx.jobMarkup({...terminal,report:{coverage_complete:false,coverage:{failed_regions:1}}}).includes('recover-job'));
}
assert(ctx.jobMarkup({id:'render',kind:'image',status:'failed'}).includes('recover-job'));
console.log('Activity recovery: exhausted detection hidden; resumable regions and render failures retain recovery');
