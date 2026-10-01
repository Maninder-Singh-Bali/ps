const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const context = {window:{}, document:{addEventListener(){}}, structuredClone,
  esc:String, url:id=>'/assets/'+id};
vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../static/drawing-editor.js'),'utf8'),context);
const doc={base_asset_id:'original',width:1000,height:800,edits:{},
  elements:Array.from({length:3001},(_,i)=>({id:String(i),kind:'detail',svg:'<path d="M0 0 L1 1"/>'})),
  features:[{id:'reviewed-wall',kind:'wall',points:[[10,10],[90,10]],thickness:4}]};
let markup=context.window.DrawingPreview.markup(doc,true);
assert.match(markup,/image href="\/assets\/original"/);
assert.match(markup,/data-plan-element="reviewed-wall"/);
assert.equal((markup.match(/data-plan-element=/g)||[]).length,1);
doc.edits={'0':{hidden:true}};
markup=context.window.DrawingPreview.markup(doc,true);
assert.doesNotMatch(markup,/<image/);
assert.doesNotMatch(markup,/data-plan-element="0"/);
doc.edits={};doc.elements[0].kind='wall';
markup=context.window.DrawingPreview.markup(doc,true);
assert.doesNotMatch(markup,/<image/);
assert.match(markup,/data-plan-element="0"/);
console.log('Large unclassified sheet rendering and editable geometry preservation passed');
