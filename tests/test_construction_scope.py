import copy,json,tempfile,unittest
from pathlib import Path
from PIL import Image
from store import Store
from engine import register_asset
import construction_scope as scope
import shared_floor
from raster_reconstruction import draft
from scene_control import scene_snapshot,assert_scene

class ConstructionScopeTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(dir=Path(__file__).parent);self.root=Path(self.tmp.name);self.st=Store(self.root/'data');self.p=self.st.create_project('Scope QA');self.pid=self.p['id']
  image=self.root/'sheet.png';Image.new('RGB',(1000,1000),'white').save(image);self.a=register_asset(self.st,self.pid,image,'plan');self.aid=self.a['id'];self.p['floor_plans']=[self.aid]
  self.r=self.st.add_room(self.pid,'Apartment A','Ground',self.aid,[.1,.1,.4,.7]);self.n=self.st.add_room(self.pid,'Apartment B','Ground',self.aid,[.5,.1,.4,.7])
  for r in (self.r,self.n):r.update(area_polygon=scope.box_polygon(r['bbox']),area_bbox=r['bbox'][:])
  self.a['plan_source']={'vector':True};self.a['drawing']={'revision':0,'edits':{},'features':[
   {'id':'party','kind':'wall','points':[[500,100],[500,800]],'thickness':20},
   {'id':'crossing','kind':'wall','points':[[100,100],[900,100]],'thickness':20},
   {'id':'neighbor','kind':'wall','points':[[900,100],[900,800]],'thickness':20},
   {'id':'door','kind':'door','points':[[100,100],[200,100]],'thickness':20},
   {'id':'neighbor-window','kind':'window','points':[[900,200],[900,300]],'thickness':20}]}
  self.a['plan_reading']={'features':[],'revision':0}
  self.data={'floor':'Ground','regions':[[[.1,.1],[.49,.1],[.49,.8],[.1,.8]]],'exclusions':[],'name':'Apartment A','kind':'apartment'}
 def tearDown(self):self.tmp.cleanup()
 def confirm(self,data=None):
  d=data or self.data;result=scope.inspect(self.st,self.pid,self.aid,d);return scope.save(self.st,self.pid,self.aid,{**d,'revision':result['revision'],'preview_key':result['preview_key'],'checked':True})
 def test_full_boundary_thickness_without_neighbor_or_selection_walls(self):
  self.confirm();scene=shared_floor.build(self.st,self.r)
  ids={r['source_id'] for r in scene['lines']}
  self.assertIn('party',ids);self.assertNotIn('neighbor',ids);self.assertNotIn('neighbor-window',ids)
  wall=next(r for r in scene['lines'] if r['source_id']=='party');self.assertEqual(wall['thickness'],20)
  self.assertTrue(all(i in {'party','crossing','door'} for i in ids))
  self.assertEqual(wall['points'],[[.5,.1],[.5,.8]])
  self.assertEqual(self.a['drawing']['features'][1]['points'][1],[900,100])
 def test_unconfirmed_new_plan_cannot_render_or_export_draft(self):
  self.a['construction_selection_required']=True
  self.assertEqual(shared_floor.build(self.st,self.r)['surfaces'],[])
  self.assertEqual(draft(self.st,self.pid,self.aid)['surfaces'],[])
 def test_void_subtracted_even_if_hole_crosses_selection(self):
  s={**self.data,'exclusions':[[[.2,.2],[.7,.2],[.7,.4],[.2,.4]]]}
  self.assertAlmostEqual(sum(scope.area(p) for p in scope.faces(s)),.39*.7-.29*.2)
  s['exclusions']=[];self.assertAlmostEqual(sum(scope.area(p) for p in scope.faces(s,holes=[[[.2,.2],[.7,.2],[.7,.4],[.2,.4]]])),.39*.7-.29*.2)
 def test_concave_polygon_does_not_include_its_bounding_box(self):
  s={**self.data,'regions':[[[.1,.1],[.6,.1],[.6,.3],[.3,.3],[.3,.8],[.1,.8]]]}
  self.assertFalse(scope.contains([.5,.6],s));self.assertEqual(scope.line_parts([.5,.5],[.5,.7],s),[])
  self.assertAlmostEqual(sum(scope.area(p) for p in scope.faces(s)),.2)
 def test_cuts_reported_and_atomic_openings_excluded(self):
  d={**self.data,'regions':[[[.15,.1],[.49,.1],[.49,.8],[.15,.8]]]}
  result=scope.inspect(self.st,self.pid,self.aid,d);self.assertTrue(any(i['kind']=='door' for i in result['issues']));self.assertTrue(any(i['kind']=='room' for i in result['issues']))
  self.confirm(d);self.assertFalse(any(r['source_id']=='door' for r in shared_floor.build(self.st,self.r)['lines']))
 def test_partial_rotated_furniture_and_neighbor_excluded(self):
  item={'id':'chair','kind':'chair','label':'Chair','x':.3,'y':.5,'width':.06,'depth':.06,'angle':45}
  self.r['block_layout']={'items':[item,{**item,'id':'cut','x':.49}]};self.n['block_layout']={'items':[{**item,'id':'neighbor','x':.7}]}
  result=scope.inspect(self.st,self.pid,self.aid,self.data);self.assertTrue(any(i['kind']=='furniture' for i in result['issues']))
  self.confirm();scene=shared_floor.build(self.st,self.r);self.assertEqual([p['block_id'] for p in scene['products']],['chair'])
 def test_saved_reopened_revision_and_undo_preserve_edits(self):
  original=copy.deepcopy(self.a['drawing']);self.confirm();first=copy.deepcopy(self.a['construction_selection']);self.confirm({**self.data,'name':'Smaller','regions':[[[.1,.1],[.4,.1],[.4,.8],[.1,.8]]]})
  scope.save(self.st,self.pid,self.aid,{'action':'undo','revision':2})
  loaded=Store(self.st.root).asset(self.aid);self.assertEqual(loaded['construction_selection']['regions'],first['regions']);self.assertEqual(loaded['construction_selection_revision'],3);self.assertEqual(loaded['drawing'],original)
 def test_stale_preview_and_old_source_rejected(self):
  result=scope.inspect(self.st,self.pid,self.aid,self.data);self.a['drawing']['revision']+=1
  with self.assertRaisesRegex(ValueError,'changed'):scope.save(self.st,self.pid,self.aid,{**self.data,'revision':0,'preview_key':result['preview_key'],'checked':True})
  self.confirm();self.a['sha256']='different';self.assertIsNone(scope.current(self.a));self.assertEqual(shared_floor.build(self.st,self.r)['surfaces'],[])
 def test_only_actual_reviewed_polygons_offered(self):
  self.n.pop('area_polygon');options=scope.inspect(self.st,self.pid,self.aid)['candidates'];self.assertEqual([r['id'] for r in options],[self.r['id']])
  self.confirm();self.assertTrue(any(c['kind']=='apartment' for c in scope.inspect(self.st,self.pid,self.aid)['candidates']))
 def test_scope_revision_invalidates_generation_ticket(self):
  before=scene_snapshot(self.st,self.p,self.r);self.confirm()
  with self.assertRaises(ValueError):assert_scene(self.st,self.p,self.r,before)
 def test_other_floor_empty_and_multiple_regions_keep_gap(self):
  self.confirm();r={**self.r,'floor':'Upper'};self.assertEqual(shared_floor.build(self.st,r)['surfaces'],[])
  s={**self.data,'regions':[scope.box_polygon([.1,.1,.1,.1]),scope.box_polygon([.6,.1,.1,.1])]}
  self.assertAlmostEqual(sum(scope.area(p) for p in scope.faces(s)),.02);self.assertFalse(scope.contains([.4,.15],s))
