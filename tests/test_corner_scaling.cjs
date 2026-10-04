const assert=require('node:assert/strict'),D=require('../static/surface-design-geometry.js'),F=require('../static/furniture-library.js');
const near=(a,b)=>assert(Math.abs(a-b)<1e-8,`${a} != ${b}`);
for(const rotation of [0,35,90,170])for(let corner=0;corner<4;corner++)for(const fromCentre of [false,true]){
 const item={id:'p',x:4,y:3,width:1,height:1.5,rotation,reference:{aspect_locked:true,image_width:2,image_height:3}},before=JSON.stringify(item),fixed=D.corners(item)[(corner+2)%4],next=D.resize(item,[.1,-.06],corner,fromCentre);
 near(next.width/next.height,2/3);if(fromCentre){near(next.x,item.x);near(next.y,item.y)}else{D.corners(next)[(corner+2)%4].forEach((x,i)=>near(x,fixed[i]))}assert.equal(JSON.stringify(item),before);
}
const plan={width:1000,height:800};for(const angle of [0,37,90])for(const handle of ['nw','ne','se','sw']){
 const item={kind:'table',x:.5,y:.5,width:.1,depth:.15,angle},scaled=F.transform(item,plan,handle,[500,400],[515,405],true,true);near(scaled.x,.5);near(scaled.y,.5);near(scaled.width/scaled.depth,item.width/item.depth);
}
console.log('Four corners: opposite anchor or Alt centre anchor, rotated items, reference aspect and furniture centre scaling passed');

for(const reference of [undefined,{aspect_locked:true},{aspect_locked:true,crop:true,image_width:400,image_height:100}]){
 const item={x:3,y:3,width:1,height:2,rotation:0,reference},next=D.resize(item,[0,.5]);
 near(next.width/next.height,.5);assert(next.width>1,'vertical drag also scales locked item');
}
const free={x:3,y:3,width:1,height:2,rotation:0,reference:{aspect_locked:false}};
const resized=D.resize(free,[.5,0],2,true);near(resized.width,2);near(resized.height,2);near(resized.x,3);near(resized.y,3);
console.log('Proportion lock preserves current ratio with or without references/crop; unlock permits independent scaling');
