'use strict';
const assert=require('node:assert/strict'),G=require('../static/surface-design-geometry.js');
const surface={id:'ceiling',kind:'ceiling',boundary:[[0,0],[10,0],[10,8],[0,8]],elevation_m:3};
const cove={id:'cove',kind:'profile',surface_id:'ceiling',x:5,y:4,width:8,height:.04,depth:.04,rotation:0,run:[[-4,-3],[4,-3],[4,3],[-4,3],[-4,-3]]};
const pendant={id:'lamp',kind:'pendant',surface_id:'ceiling',x:5,y:4,width:.23,height:.21,depth:.41,drop:.45,rotation:0};
const doc={calibration:{metres_per_pixel:1},features:[],surface_design:{items:[cove,pendant]}};
assert.deepEqual(G.conflicts(doc,surface,pendant),[],'a pendant inside a cove is not touching it');
assert.deepEqual(G.conflicts(doc,surface,cove),[],'collision is symmetric');
assert(G.conflicts(doc,surface,{...pendant,y:1}).includes('Overlaps profile'),'actual strip collision stays blocked');
assert(G.conflicts(doc,surface,{...cove,x:0}).includes('Outside surface or over a void'));
// Empty centre of a closed run can surround an opening/void without covering it.
assert.deepEqual(G.conflicts({...doc,surface_design:{items:[cove]}},{...surface,holes:[[[4,3],[6,3],[6,5],[4,5]]]},cove),[]);
assert(G.conflicts(doc,{...surface,holes:[[[4,.9],[6,.9],[6,1.1],[4,1.1]]]},cove).some(x=>/void/.test(x)));
// Check a mitred corner outside both butt-ended strips, then rotate both objects.
const elbow={...cove,x:3,y:3,height:.2,run:[[-1,0],[0,0],[0,1]]};
const tiny={...pendant,x:3.075,y:2.925,width:.02,height:.02};
assert(G.conflicts({...doc,surface_design:{items:[elbow]}},surface,tiny).includes('Overlaps profile'));
const rotated={...elbow,rotation:90},turned={...tiny,x:3.075,y:3.075};
assert(G.conflicts({...doc,surface_design:{items:[rotated]}},surface,turned).includes('Overlaps profile'));
const acute={...elbow,run:[[-1,0],[0,0],[-1,.01]]};
assert(G.conflicts({...doc,surface_design:{items:[acute]}},surface,{...tiny,x:3.4,y:3}).includes('Overlaps profile'),'bounded acute mitre remains occupied');
assert(!G.conflicts({...doc,surface_design:{items:[acute]}},surface,{...tiny,x:3.6,y:3}).includes('Overlaps profile'),'mitre does not grow without limit');
console.log('Profile conflicts: hollow runs, real collisions, voids, mitre joints and rotation passed.');
