const assert=require('node:assert/strict');const lib=require('../static/furniture-library.js');const plan={width:400,height:200},bbox=[0,0,1,1],dims={width_m:20,depth_m:10};
for(const id of ['chair','armchair','bar-stool','sofa-2','sofa-l','bed-double','kitchen-counter','kitchen-table']){
 const v=lib.create(id,bbox,plan,dims,[.4,.5],id),bad=lib.scale(v,1.6),b=lib.balance(bad,plan,.05);
 assert.equal(b.x,bad.x);assert.equal(b.y,bad.y);assert.equal(b.angle,bad.angle);assert.equal(b.seat_count,bad.seat_count);
 assert.deepEqual(lib.balance(b,plan,.05),b,'Balancing is idempotent');
 if(id==='chair')assert(Math.abs(b.width*20-.55)<1e-8);
 if(id==='bar-stool')assert.equal(b.height_m,.65);
 if(id==='kitchen-table')assert.equal(b.height_m,.75);
}
let chairs=lib.create('chair',bbox,plan,dims,[.4,.5],'chairs');chairs.chair_modules={columns:2,rows:3,width:chairs.width,depth:chairs.depth};chairs.width*=2.15;chairs.depth*=3.3;
const group=lib.balance(chairs,plan,.05);assert.equal(group.chair_modules.rows,3);assert.equal(group.chair_modules.columns,2);
const table=lib.create('coffee-table',bbox,plan,dims,[.5,.5],'table');const product={dimensions_m:{length:{metres:1.02},width:{metres:1.02},height:{metres:.36}}};const linked=lib.balance(table,plan,.05,product);assert.equal(linked.height_m,.36);assert(Math.abs(linked.depth*10-1.02)<1e-8);
assert(!lib.balance(table,plan,.05,{...product,dimension_notes:['Variant discrepancy']}).physical_size);
console.log('Human-scale furniture: library sizes, positions, counts, seat groups, dimensions priority, conflicting products and repeat application passed.');
