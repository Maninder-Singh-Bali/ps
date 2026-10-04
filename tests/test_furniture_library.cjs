const assert=require('node:assert/strict');
const {presets,create,symbol,seats}=require('../static/furniture-library.js');
const b=[.1,.2,.4,.6],plan={width:1000,height:500};
for(const p of presets){const v=create(p.id,b,plan,null,[.25,.4],'new-test');assert.equal(v.x,.25);assert.equal(v.y,.4);assert(v.width>0&&v.depth>0);assert.equal(v.kind,p.kind);assert.equal(v.height_m,p.height);assert(symbol(v).length>10)}
assert.equal(create('sofa-3',b,plan,null,null,'a').seat_count,3);
assert.equal(create('sofa-l',b,plan,null,null,'a').shape,'l');
assert.equal(create('pillar-round',b,plan,null,null,'a').shape,'round');
const calibrated=create('bed-double',b,plan,{width_m:4,depth_m:6},null,'a');assert(Math.abs(calibrated.width-.15)<1e-9);assert(Math.abs(calibrated.depth-.2)<1e-9);
assert.throws(()=>create('fake',b,plan,null,null,'a'));
const sofa=create('sofa-3',b,plan,null,null,'a');seats(sofa,'4');assert.equal(sofa.label,'4-seater sofa');assert.equal(sofa.seat_count,4);
console.log('Furniture library presets, drop placement, scale and symbols verified');
const library=require('../static/furniture-library.js');
const original={...sofa,asset_id:'linked-image',physical_size:{width:2,depth:1,unit:'m'}};
const snapshot=JSON.stringify(original),scaled=library.scale(original,1.2),copy=library.duplicate(original,plan,'copy');
assert.equal(JSON.stringify(original),snapshot);
assert.equal(scaled.width,original.width*1.2);assert.equal(scaled.depth,original.depth*1.2);
assert.equal(scaled.height_m,original.height_m*1.2);assert.deepEqual(scaled.physical_size,original.physical_size,'Proxy scaling never rewrites source product evidence');
assert.equal(copy.id,'copy');assert.equal(copy.asset_id,null);assert.equal(copy.seat_count,original.seat_count);
assert.equal(copy.width,original.width);assert.notEqual(copy.x,original.x);
assert.throws(()=>library.scale(original,0));assert.throws(()=>library.scale(original,NaN));assert.throws(()=>library.scale(original,1000));
assert.equal(JSON.stringify(original),snapshot);
console.log('Duplicate and uniform scale preserve the original and reject invalid sizes');
const object={id:'handle-test',x:.5,y:.5,width:.2,depth:.1,angle:90},sheet={width:1000,height:500};
// Local east points down after 90° rotation; its opposite west edge stays fixed.
const wider=library.transform(object,sheet,'e',[500,350],[500,400]);
assert(Math.abs(wider.width-.25)<1e-9);assert(Math.abs(wider.y-.55)<1e-9);
assert(Math.abs(wider.y*500-wider.width*1000/2-150)<1e-9);
const corner=library.transform(object,sheet,'se',[475,350],[450,450]);
assert(Math.abs(corner.width/object.width-corner.depth/object.depth)<1e-9);
const rotated=library.transform(object,sheet,'rotate',[500,200],[550,250]);assert.equal(rotated.angle,180);
assert.equal(rotated.x,object.x);assert.equal(rotated.y,object.y);
assert.deepEqual(library.transform(object,sheet,'e',[500,350],[500,400]),wider);
assert.equal(object.width,.2);assert.equal(object.y,.5);
console.log('Direct handles: rotated fixed-edge resize, proportional scale, rotation and no cumulative drift passed');
assert.equal(library.resizeDirection(object,sheet,1,0),90);
assert.equal(library.resizeDirection(object,sheet,0,1),0);
assert.equal(library.resizeDirection({...object,angle:45},sheet,1,0),45);
assert(Math.abs(library.resizeDirection({...object,angle:0},sheet,1,1)-Math.atan2(50,200)*180/Math.PI)<1e-9);
assert(Math.abs(library.resizeDirection(object,sheet,1,1)-library.resizeDirection(object,sheet,-1,-1))<1e-9);
assert(library.resizeCursor(object,sheet,1,0).endsWith('ns-resize'));
console.log('Resize cursor orientation follows rotation and rectangular corner diagonals');
const zeroAngle={...object,angle:0};
for(const [degrees,expected] of [[14,10],[16,20],[-16,340],[356,0]]){
 const t=degrees*Math.PI/180,point=[500+100*Math.cos(t),250+100*Math.sin(t)];
 assert.equal(library.transform(zeroAngle,sheet,'rotate',[600,250],point).angle,expected);
}
console.log('Default 10-degree rotation snap, negative rotation and full-turn wrap passed');
// Straight sofas grow in whole modules, including a single-seater.
for(const count of [1,2,3]){
 const s={...zeroAngle,kind:'sofa',shape:'box',seat_count:count};
 const pitch=s.width*sheet.width/count;
 const added=library.transform(s,sheet,'e',[0,0],[pitch,0]);
 assert.equal(added.seat_count,count+1);assert.equal(added.depth,s.depth);
 assert(Math.abs(added.width-s.width-s.width/count)<1e-9);
 assert(Math.abs(added.x-added.width/2-(s.x-s.width/2))<1e-9);
 const removed=library.transform(added,sheet,'w',[0,0],[pitch,0]);
 assert.equal(removed.seat_count,count);assert(Math.abs(removed.width-s.width)<1e-9);
 assert.equal(library.transform(s,sheet,'s',[0,0],[0,70]).depth,s.depth);
 assert.equal((symbol(added).match(/data-sofa-seat/g)||[]).length,count+1);
 const enlarged=library.scale(added,1.2);assert.equal(enlarged.seat_count,count+1);
 assert(Math.abs(enlarged.sofa_modules.pitch_width-added.sofa_modules.pitch_width*1.2)<1e-9);
}
for(const angle of [0,90,230])for(const side of ['left','right']){
 const s=library.consistentSofa({...zeroAngle,kind:'sofa',shape:'l',seat_count:4,angle,return_side:side},sheet),a=angle*Math.PI/180,pitch=s.sofa_modules.pitch_width*sheet.width;
 const addWidth=library.transform(s,sheet,'e',[0,0],[pitch*Math.cos(a),pitch*Math.sin(a)]);
 assert.equal(addWidth.seat_count,5);assert.equal(addWidth.sofa_modules.main_seats,4);
 const addDepth=library.transform(addWidth,sheet,'s',[0,0],[-pitch*Math.sin(a),pitch*Math.cos(a)]);
 assert.equal(addDepth.seat_count,6);assert.equal(addDepth.sofa_modules.return_seats,2);
 assert.equal(addDepth.sofa_modules.leg_width,addWidth.sofa_modules.leg_width);
 assert.equal(addDepth.sofa_modules.leg_depth,addWidth.sofa_modules.leg_depth);
 assert.equal((symbol(addDepth).match(/data-sofa-seat/g)||[]).length,6);
 assert.equal(addDepth.return_side,side);
 const scale=library.transform(addDepth,sheet,'se',[0,0],[20,20]);
 assert.equal(scale.seat_count,6);
 assert(Math.abs(scale.sofa_modules.pitch_width/addDepth.sofa_modules.pitch_width-scale.width/addDepth.width)<1e-9);
}
const cap=library.transform({...zeroAngle,kind:'sofa',seat_count:12},sheet,'e',[0,0],[1000,0]);
assert.equal(cap.seat_count,12);
console.log('Sofa modules: single/straight/L, both legs, mirrored/rotated, fixed depth, whole seats, limits and uniform scale passed');

// Unequal source-page axes must still produce identical seats in both directions.
for(const dimensions of [{width:473,height:355},{width:500,height:1000}]){
 const old={...zeroAngle,kind:'sofa',shape:'l',seat_count:5,sofa_modules:{main_seats:3,return_seats:2,leg_width:.08,leg_depth:.04,pitch_width:.06,pitch_depth:.03}};
 const fixed=library.consistentSofa(old,dimensions),m=fixed.sofa_modules;
 const unit=m.leg_width*dimensions.width;
 for(const length of [m.leg_depth*dimensions.height,m.pitch_width*dimensions.width,m.pitch_depth*dimensions.height])assert(Math.abs(length-unit)<1e-9);
 assert.equal(fixed.seat_count,5);assert.equal(fixed.x,old.x);assert.equal(fixed.y,old.y);assert.equal(fixed.angle,old.angle);
 assert(fixed.width<=old.width+1e-9&&fixed.depth<=old.depth+1e-9);
 assert.strictEqual(library.consistentSofa(fixed,dimensions),fixed);
 const seatRects=[...symbol(fixed).matchAll(/data-sofa-seat="true" x="([^"]+)" y="([^"]+)" width="([^"]+)" height="([^"]+)" rx="([^"]+)" ry="([^"]+)"/g)];
 assert.equal(seatRects.length,5);
 for(const match of seatRects){
  const width=Number(match[3])*fixed.width*dimensions.width/100,depth=Number(match[4])*fixed.depth*dimensions.height/100;
  assert(Math.abs(width-depth)<1e-9);assert(Math.abs(width-unit*.8)<1e-9);
  assert(Math.abs(Number(match[5])*fixed.width*dimensions.width-Number(match[6])*fixed.depth*dimensions.height)<1e-9);
 }
 const larger=library.scale(fixed,1.2);assert.strictEqual(library.consistentSofa(larger,dimensions),larger);
}
console.log('L-sofa consistency: equal seat sizes and leg thickness on unequal page axes; idempotent correction, position/rotation/count preservation and scaling passed');
for(const angle of [0,90,180,270])for(const handle of ['e','w']){
 const s={...zeroAngle,kind:'sofa',shape:'box',seat_count:2,angle};
 const sign=handle==='e'?1:-1,a=angle*Math.PI/180,pitch=s.width*sheet.width/2;
 const delta=[sign*pitch*Math.cos(a),sign*pitch*Math.sin(a)];
 const three=library.transform(s,sheet,handle,[0,0],delta);
 assert.equal(three.seat_count,3);
 const two=library.transform(three,sheet,handle,[0,0],delta.map(n=>-n));
 assert.equal(two.seat_count,2);assert(Math.abs(two.width-s.width)<1e-9);
 assert(Math.abs(two.x-s.x)<1e-9);assert(Math.abs(two.y-s.y)<1e-9);
 const returned=library.transform(s,sheet,handle,[0,0],[0,0]);
 assert.equal(returned.seat_count,2);assert.equal(returned.width,s.width);
}
console.log('Two-seater: 2→3→2 from either side at all cardinal rotations, with return-to-start and no count drift passed');
for(const angle of [0,90,180,270]){
 const chair={...zeroAngle,kind:'chair',shape:'box',width:.05,depth:.1,angle},a=angle*Math.PI/180;
 const row=library.transform(chair,sheet,'e',[0,0],[57.5*Math.cos(a),57.5*Math.sin(a)]);
 assert.equal(row.chair_modules.columns,2);assert.equal(row.chair_modules.rows,1);
 const grid=library.transform(row,sheet,'s',[0,0],[-57.5*Math.sin(a),57.5*Math.cos(a)]);
 assert.equal(grid.chair_modules.rows,2);assert.equal(grid.chair_modules.columns,2);
 assert.equal(library.chairInstances(grid,sheet).length,4);
 for(const unit of library.chairInstances(grid,sheet)){assert.equal(unit.width,chair.width);assert.equal(unit.depth,chair.depth);assert.equal(unit.angle,angle)}
 assert.equal((symbol(grid).match(/data-chair-instance/g)||[]).length,4);
 const reduced=library.transform(row,sheet,'e',[0,0],[-57.5*Math.cos(a),-57.5*Math.sin(a)]);
 assert.equal(reduced.chair_modules.columns,1);assert(Math.abs(reduced.width-chair.width)<1e-9);assert(Math.abs(reduced.x-chair.x)<1e-9);assert(Math.abs(reduced.y-chair.y)<1e-9);
 const scaled=library.scale(grid,1.5);assert.equal(scaled.chair_modules.width,chair.width*1.5);assert.equal(scaled.chair_modules.columns,2);
}
console.log('Chair repetition: rows/columns, individual dimensions, rotated add/remove, gaps and proportional scaling passed');
let checked=0;
for(const preset of presets.filter(p=>!['sofa','chair','stair'].includes(p.kind))){
 const item=create(preset.id,[0,0,1,1],sheet,null,[.5,.5],'proportions');
 for(const angle of [0,37,90,180])for(const handle of ['n','e','s','w','ne','sw']){
  const rotated={...item,angle};
  const changed=library.transform(rotated,sheet,handle,[0,0],[10,-12]);
  assert(Math.abs(changed.width/changed.depth-item.width/item.depth)<1e-9,preset.id+' '+handle);
  assert.equal(changed.angle,angle);assert.equal(changed.preset_id,preset.id);
  if(preset.shape==='round')assert(Math.abs(changed.width*sheet.width-changed.depth*sheet.height)<1e-9);
  checked++;
 }
}
console.log(`Other furniture: ${checked} proportional-resize cases passed for beds, tables, storage, appliances, fixtures and pillars`);
for(const angle of [0,37,90,180]){
 const stair={...create('staircase',[0,0,1,1],sheet,null,[.5,.5],'stairs'),angle},a=angle*Math.PI/180;
 const wider=library.transform(stair,sheet,'e',[0,0],[10*Math.cos(a),10*Math.sin(a)]);
 assert(Math.abs(wider.depth-stair.depth)<1e-9);assert(wider.width>stair.width);assert.equal(wider.height_m,3);
 const longer=library.transform(stair,sheet,'s',[0,0],[-10*Math.sin(a),10*Math.cos(a)]);
 assert(Math.abs(longer.width-stair.width)<1e-9);assert(longer.depth>stair.depth);
 const restore=library.transform(wider,sheet,'e',[0,0],[-10*Math.cos(a),-10*Math.sin(a)]);
 for(const k of ['width','depth','x','y'])assert(Math.abs(restore[k]-stair[k])<1e-9);
 assert(symbol(stair).includes('stair-up'));
}
console.log('Staircase independent dimensions, fixed opposite edges, rotation and direction symbol passed');
