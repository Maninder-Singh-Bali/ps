const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const windowHandlers = {}, documentHandlers = {};
const modal = {addEventListener(){}};
const context = vm.createContext({
  window:{addEventListener(type,fn){(windowHandlers[type]??=[]).push(fn)}},
  document:{addEventListener(type,fn){(documentHandlers[type]??=[]).push(fn)},querySelector(){return modal}},
});
vm.runInContext(fs.readFileSync('static/furniture-blocks.js','utf8'),context);
// Furniture registers before app.js declares modalType; resize can arrive then.
assert.doesNotThrow(()=>windowHandlers.resize.forEach(fn=>fn()));
vm.runInContext("let modalType='product-review';",context);
assert.doesNotThrow(()=>windowHandlers.resize.forEach(fn=>fn()));
console.log('Early startup and unrelated review resize events are safe.');
