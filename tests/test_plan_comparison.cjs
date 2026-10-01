const assert=require('node:assert/strict');
const {planComparisonData}=require('../static/plan-comparison.js');
assert.equal(planComparisonData({}),null);
const job={scene_ticket:{content:{plan:{id:'original'},room:{bbox:[.1,.2,.3,.4],furniture_layout:{camera_heading:90,items:[{asset_id:'chair',x:.5,y:.2}]}},drawing:{features:[]},products:[{id:'chair',category:'Chair'}]}},layout_guide_id:'saved-guide'};
const review=planComparisonData(job);
assert.equal(review.planId,'original');assert.equal(review.guideId,'saved-guide');assert.equal(review.heading,90);assert.equal(review.items[0].y,.2);
assert.equal(review.dimensions,null);assert.equal(review.products[0].category,'Chair');
assert.equal(planComparisonData({scene_manifest:job.scene_ticket}).planId,'original');
console.log('Saved plan comparison: 9 checks passed');
