import sys,unittest,tempfile,copy
from unittest.mock import patch
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from PIL import Image
from store import Store
from engine import register_asset
import furniture_blocks as blocks
import shared_floor
from furniture_meshes import mesh

class FurnitureBlocks(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(dir=ROOT/'tests');self.root=Path(self.tmp.name);self.st=Store(self.root/'data');self.p=self.st.create_project('Blocks QA');self.pid=self.p['id']
  path=self.root/'plan.png';Image.new('RGB',(400,200),'white').save(path);self.a=register_asset(self.st,self.pid,path,'plan');self.p['floor_plans']=[self.a['id']]
  self.r=self.st.add_room(self.pid,'Living','Lower',self.a['id'],[0,0,1,1]);self.a['drawing']={'features':[],'revision':0};self.a['plan_reading']={'features':[],'revision':0}
  self.item={'id':'three','kind':'sofa','label':'Three-seat sofa','seat_count':3,'x':.3,'y':.5,'width':.3,'depth':.2,'angle':0}
  ref=register_asset(self.st,self.pid,path,'reference',self.r['id'],category='Sofa');self.r['references']=[ref['id']];self.item['asset_id']=ref['id']
 def tearDown(self):self.tmp.cleanup()
 def test_mirrors_survive_save_reload_and_reflect_l_footprint(self):
  item={**self.item,'shape':'l','flip_x':True,'flip_y':True}
  self.request('save',[item])
  loaded=Store(self.st.root).room(self.pid,self.r['id'])['block_layout']['items'][0]
  self.assertTrue(loaded['flip_x']);self.assertTrue(loaded['flip_y'])
  original=blocks.parts({**item,'flip_x':False,'flip_y':False},self.a)
  mirrored=blocks.parts(loaded,self.a)
  for ps,qs in zip(original,mirrored):
   for p,q in zip(ps,qs):
    self.assertAlmostEqual(p[0]+q[0],2*item['x']);self.assertAlmostEqual(p[1]+q[1],2*item['y'])
  self.assertRaises(ValueError,blocks.clean,[{**item,'flip_x':'true'}])
 def request(self,action,items=None,**kw):return blocks.request(self.st,self.pid,self.r['id'],{'revision':self.r['revision'],'action':action,'items':items if items is not None else [self.item],**kw})
 def test_staircase_dimensions_height_direction_roundtrip(self):
  item={**self.item,'id':'stairs','kind':'stair','preset_id':'staircase','label':'Staircase','seat_count':None,'height_m':3.4,'angle':270}
  saved=self.request('save',[item])['items'][0]
  loaded=Store(self.st.root).room(self.pid,self.r['id'])['block_layout']['items'][0]
  for key in ('kind','preset_id','width','depth','height_m','angle'):self.assertEqual(loaded[key],item[key])
  from furniture_meshes import components
  parts=components(saved);self.assertTrue(all(p['role']=='step' for p in parts));self.assertGreater(len(parts),10)
  self.assertEqual(parts[0]['bounds'][5],1);self.assertLess(parts[-1]['bounds'][5],.1)
 def test_ceiling_placement_persists_and_ignores_furniture_below(self):
  light={**self.item,'id':'lamp','kind':'light','preset_id':'pendant-light','label':'Pendant','asset_id':None,'seat_count':None,'elevation_m':2.15,'height_m':.85}
  self.assertFalse(any('overlaps' in v['message'] for v in blocks.checks(self.st,self.r,[self.item,light])))
  saved=self.request('save',[self.item,light]);loaded=Store(self.st.root).room(self.pid,self.r['id'])['block_layout']['items'][1]
  self.assertEqual(loaded['elevation_m'],2.15)
  light['elevation_m']=.5
  self.assertTrue(any('overlaps' in v['message'] for v in blocks.checks(self.st,self.r,[self.item,light])))
 def test_rotated_footprint_uses_pixel_aspect(self):
  row={**self.item,'angle':90};pts=blocks.corners(row,self.a)
  self.assertAlmostEqual(max(p[0] for p in pts)-min(p[0] for p in pts),.1)
  self.assertAlmostEqual(max(p[1] for p in pts)-min(p[1] for p in pts),.6)
 def test_product_url_survives_checks_and_saved_plan_without_fetch(self):
  link='https://shop.example/product/synthetic-sectional-121'
  item={**self.item,'product_url':link}
  self.assertEqual(self.request('check',[item])['items'][0]['product_url'],link)
  drafts=[dict(room_id=self.r['id'],revision=self.r['revision'],items=[item])]
  self.assertEqual(self.request('save-plan',drafts=drafts)['items'][0]['product_url'],link)
  loaded=Store(self.st.root).room(self.pid,self.r['id'])['block_layout']['items'][0]
  self.assertEqual(loaded['product_url'],link)
  self.assertEqual(self.request('save',[{**loaded,'product_url':''}])['items'][0]['product_url'],'')
  for value in ['javascript:alert(1)','file:///C:/plan','https://','https://name:secret@shop.com/product',42]:
   with self.assertRaisesRegex(ValueError,'product URL'):blocks.clean([{**item,'product_url':value}])
 def test_multi_section_save_is_validated_before_any_changes(self):
  other=self.st.add_room(self.pid,'Bedroom','Lower',self.a['id'],[0,0,1,1])
  second={**self.item,'id':'bedroom-chair','kind':'chair','seat_count':None,'asset_id':None}
  drafts=[dict(room_id=self.r['id'],revision=self.r['revision'],items=[self.item]),dict(room_id=other['id'],revision=other['revision'],items=[second])]
  stale=copy.deepcopy(drafts);stale[1]['revision']=-1
  with self.assertRaisesRegex(ValueError,'changed'):self.request('save-plan',drafts=stale)
  self.assertNotIn('block_layout',self.r);self.assertNotIn('block_layout',other)
  invalid=copy.deepcopy(drafts);invalid[1]['items'][0]['asset_id']=self.item['asset_id']
  with self.assertRaisesRegex(ValueError,'reference'):self.request('save-plan',drafts=invalid)
  self.assertNotIn('block_layout',self.r)
  revs=[self.r['revision'],other['revision']]
  result=self.request('save-plan',drafts=drafts)
  self.assertEqual(result['saved_sections'],2)
  self.assertEqual(self.r['block_layout']['items'][0]['id'],self.item['id'])
  self.assertEqual(other['block_layout']['items'][0]['id'],second['id'])
  self.assertEqual([self.r['revision'],other['revision']],[n+1 for n in revs])
 def wall_draft(self):
  import drawing_editor
  doc=drawing_editor.get_document(self.st,self.pid,self.a['id'])
  doc['features']=[{'id':'newwall','kind':'wall','points':[[20,20],[20,180]],'thickness':2,'flip':False}]
  return doc
 def test_combined_wall_and_furniture_save_persists_together(self):
  drawing=self.wall_draft();drafts=[dict(room_id=self.r['id'],revision=self.r['revision'],items=[self.item])]
  result=self.request('save-plan',drafts=drafts,drawing=drawing)
  room=self.st.room(self.pid,self.r['id']);plan=self.st.asset(self.a['id'])
  self.assertEqual(room['block_layout']['items'][0]['id'],self.item['id'])
  self.assertEqual(plan['drawing']['features'][0]['id'],'newwall')
  self.assertEqual(result['drawing']['revision'],1)
  self.assertEqual(result['drawing']['map_revision'],self.p['map_revision']+1)
  disk=Store(self.st.root)
  self.assertEqual(disk.asset(self.a['id'])['drawing']['features'],result['drawing']['features'])
  self.assertEqual(disk.room(self.pid,self.r['id'])['block_layout'],room['block_layout'])
 def test_combined_save_failure_does_not_commit_either_half(self):
  self.st.save();before=copy.deepcopy(self.st.db);drafts=[dict(room_id=self.r['id'],revision=self.r['revision'],items=[self.item])]
  with patch('drawing_editor.rasterize',side_effect=ValueError('Export failed')):
   with self.assertRaisesRegex(ValueError,'Export failed'):self.request('save-plan',drafts=drafts,drawing=self.wall_draft())
  self.assertEqual(self.st.db,before);self.assertEqual(Store(self.st.root).db,before)
  drawing=self.wall_draft();drawing['revision']=-1
  with self.assertRaisesRegex(ValueError,'drawing changed'):self.request('save-plan',drafts=drafts,drawing=drawing)
  self.assertEqual(self.st.db,before)
 def test_unsaved_wall_preview_uses_draft_without_persistence(self):
  before=copy.deepcopy(self.st.db)
  result=self.request('check',drawing=self.wall_draft())
  self.assertGreater(result['architecture']['typed_wall_count'],0)
  self.assertEqual(self.st.db,before)
 def test_chair_group_persists_and_has_separate_volumes(self):
  m=dict(columns=2,rows=2,width=.08,depth=.1)
  item={**self.item,'kind':'chair','seat_count':None,'width':.172,'depth':.215,'chair_modules':m,'asset_id':None}
  for angle in (0,90,180,270):
   item['angle']=angle
   saved=self.request('save',[item])['items'][0]
   self.assertEqual(saved['chair_modules'],m)
   parts=blocks.parts(saved,self.a);self.assertEqual(len(parts),4)
   for p in parts:
    w=max(q[0] for q in p)-min(q[0] for q in p);d=max(q[1] for q in p)-min(q[1] for q in p)
    self.assertAlmostEqual(w,.08 if angle%180==0 else .05);self.assertAlmostEqual(d,.1 if angle%180==0 else .16)
   scene=shared_floor.build(self.st,self.r)
   self.assertEqual(len([f for f in scene['surfaces'] if f['kind']=='block']),len(mesh(saved,self.a)))
  for bad in ({**m,'rows':0},{**m,'columns':100},{**m,'width':float('nan')},{**m,'depth':.2}):
   with self.assertRaises(ValueError):blocks.clean([{**item,'chair_modules':bad}])
 def test_sofa_modules_persist_and_drive_shared_geometry(self):
  module={'main_seats':4,'return_seats':2,'leg_width':.08,'leg_depth':.04,'pitch_width':.06,'pitch_depth':.06}
  item={**self.item,'shape':'l','width':.26,'depth':.16,'seat_count':6,'sofa_modules':module}
  for action in ('check','save'):
   saved=self.request(action,[item])['items'][0]
   self.assertEqual(saved['sofa_modules'],module);self.assertEqual(saved['seat_count'],6)
  self.assertEqual(self.r['block_layout']['items'][0]['sofa_modules'],module)
  pieces=blocks.parts(saved,self.a)
  self.assertAlmostEqual(max(p[1] for p in pieces[0])-min(p[1] for p in pieces[0]),.04)
  self.assertAlmostEqual(max(p[0] for p in pieces[1])-min(p[0] for p in pieces[1]),.08)
  scene=shared_floor.build(self.st,self.r)
  self.assertTrue(any(f['kind']=='block' for f in scene['surfaces']))
  for bad in ({**module,'pitch_width':float('nan')},{**module,'return_seats':20},{**module,'leg_width':.09}):
   with self.assertRaises(ValueError):blocks.clean([{**item,'sofa_modules':bad}])
  straight={**self.item,'width':.2,'depth':.1,'seat_count':2,'sofa_modules':dict(main_seats=2,return_seats=0,leg_width=.1,leg_depth=.1,pitch_width=.1,pitch_depth=.1)}
  self.assertEqual(self.request('save',[straight])['items'][0]['sofa_modules'],straight['sofa_modules'])
 def test_library_types_height_and_round_pillar_survive_save(self):
  for kind in ('refrigerator','comforter','pillar','fixture','appliance','desk','plant','rug'):
   item={**self.item,'kind':kind,'preset_id':'pillar-round' if kind=='pillar' else kind,'shape':'round' if kind=='pillar' else 'box','height_m':3 if kind=='pillar' else .7,'asset_id':None}
   result=self.request('save',[item]);saved=result['items'][0]
   self.assertEqual(saved['kind'],kind);self.assertEqual(saved['preset_id'],item['preset_id']);self.assertEqual(saved['height_m'],item['height_m'])
   scene=shared_floor.build(self.st,self.r);surfaces=[f for f in scene['surfaces'] if f['kind']=='block']
   self.assertEqual(max(p[2] for f in surfaces for p in f['points']),item['height_m'])
   if kind=='pillar':self.assertEqual(len(blocks.parts(saved,self.a)[0]),32)
  for bad in (float('nan'),-1,10):
   with self.assertRaises(ValueError):blocks.clean([{**self.item,'height_m':bad}])
 def test_rug_under_furniture_is_allowed_but_solid_objects_still_conflict(self):
  rug={**self.item,'id':'rug','kind':'rug','asset_id':None}
  self.assertFalse(any('overlaps' in p['message'] for p in blocks.checks(self.st,self.r,[self.item,rug])))
  pillar={**rug,'id':'pillar','kind':'pillar','shape':'round'}
  self.assertTrue(any('overlaps' in p['message'] for p in blocks.checks(self.st,self.r,[self.item,pillar,rug])))
 def test_two_distinct_sofas_and_table_remain_distinct(self):
  ref2=register_asset(self.st,self.pid,self.a['path'],'reference',self.r['id'],category='Sofa');ref3=register_asset(self.st,self.pid,self.a['path'],'reference',self.r['id'],category='Table');self.r['references'] += [ref2['id'],ref3['id']]
  two={**self.item,'id':'two','asset_id':ref2['id'],'label':'Two-seat sofa','seat_count':2,'x':.75,'width':.2}
  table={**self.item,'id':'table','asset_id':ref3['id'],'kind':'table','label':'Side table','seat_count':None,'x':.55,'width':.08,'depth':.1}
  out=self.request('save',[self.item,two,table],reviewed=True)
  self.assertEqual(out['issues'],[]);self.assertEqual([v['seat_count'] for v in out['items']],[3,2,None]);self.assertEqual(blocks.readiness(self.st,self.r),[])
 def test_overlap_outside_and_wall_crossing_flagged(self):
  self.a['drawing']['features']=[{'kind':'wall','points':[[120,0],[120,200]]}]
  self.assertTrue(any('mapped wall' in v['message'] for v in self.request('check')['issues']))
  self.assertTrue(any('overlaps' in v['message'] for v in self.request('check',[self.item,{**self.item,'id':'two','asset_id':None}])['issues']))
  self.assertTrue(any('outside' in v['message'] for v in self.request('check',[{**self.item,'x':.02}])['issues']))
  with self.assertRaisesRegex(ValueError,'conflicts'):self.request('save',reviewed=True)
 def test_suggestion_avoids_known_obstacles_without_saving(self):
  self.a['drawing']['features']=[{'kind':'wall','points':[[120,0],[120,200]]}]
  out=self.request('suggest',selected='three');self.assertFalse(out['issues']);self.assertNotEqual(out['items'][0]['x'],.3);self.assertNotIn('block_layout',self.r)
 def test_plan_source_unchanged_and_approval_invalidated(self):
  original=Path(self.a['path']).read_bytes();self.r['approved_image_id']='old';self.r['approved_video_id']='old'
  self.request('save');self.assertIsNone(self.r['approved_image_id']);self.assertIsNone(self.r['approved_video_id']);self.assertEqual(Path(self.a['path']).read_bytes(),original)
  self.assertTrue(blocks.readiness(self.st,self.r));self.request('save',reviewed=True);self.assertFalse(blocks.readiness(self.st,self.r))
  self.a['drawing']['revision']=1;self.assertTrue(blocks.readiness(self.st,self.r))
 def test_bad_and_duplicate_inputs_rejected(self):
  for rows in ([self.item,self.item],[{**self.item,'width':float('nan')}],[{**self.item,'seat_count':2.5}]):
   with self.assertRaises(ValueError):self.request('check',rows)
 def test_no_objects_invented_from_unusable_detection(self):
  self.a['vision_report']={'features':[{'kind':'furniture','label':'Sofa','bbox':[0,0,1,1],'location_unresolved':True}]}
  self.assertEqual(self.request('propose')['items'],[])
 def test_shared_scene_contains_furniture_mesh_and_snapshot_tracks_it(self):
  from scene_control import scene_snapshot
  before=scene_snapshot(self.st,self.p,self.r)['fingerprint'];self.request('save',reviewed=True)
  scene=shared_floor.build(self.st,self.r)
  self.assertEqual(sum(f['kind']=='block' for f in scene['surfaces']),len(mesh(self.item,self.a)));self.assertEqual(len(scene['products']),1)
  self.assertNotEqual(before,scene_snapshot(self.st,self.p,self.r)['fingerprint'])
 def test_open_transition_clearance_and_stale_request(self):
  self.a['plan_reading']['features']=[{'kind':'space','label':'Open passage','review_status':'confirmed','floor':'Lower','bbox':[.2,.4,.2,.2],'connection_room_id':'other'}]
  self.assertTrue(any('Open passage' in v['message'] for v in self.request('check')['issues']))
  with self.assertRaisesRegex(ValueError,'changed'):blocks.request(self.st,self.pid,self.r['id'],{'revision':-1,'action':'save','items':[]})
 def test_active_generation_prevents_save(self):
  self.st.new_job(self.pid,'image',self.r['id'])
  with self.assertRaisesRegex(ValueError,'current activity'):self.request('save')
 def test_reference_pairing_survives_prompt_and_layout_without_duplicate_volumes(self):
  from placement_map import current_layout
  from flux_layout_prompt import compile_prompt
  import json
  self.item['prompt']='Keep the walnut arms and cream upholstery.';self.request('save',reviewed=True)
  layout=current_layout(self.r);self.assertEqual(layout['items'][0]['block_id'],'three');self.assertEqual(layout['items'][0]['asset_id'],self.item['asset_id'])
  prompt,_=compile_prompt(self.p,self.r,[self.st.asset(self.item['asset_id'])],self.a)
  subject=json.loads(prompt)['subjects'][0];self.assertEqual(subject['reference_image'],2);self.assertEqual(subject['block_id'],'three');self.assertIn('walnut',subject['change_instruction'])
  scene=shared_floor.build(self.st,self.r);self.assertEqual(len(scene['products']),1)
 def test_scan_proposes_separate_blocks_without_editing_source(self):
  from PIL import ImageDraw
  image=Image.new('RGB',(400,200),'#eeeeee');d=ImageDraw.Draw(image)
  for box in [(40,40,120,80),(180,30,225,110),(280,100,330,150)]:d.rectangle(box,outline='#888888',width=2)
  image.save(self.a['path']);original=Path(self.a['path']).read_bytes()
  out=self.request('propose');self.assertEqual(len(out['items']),3);self.assertTrue(all(v['kind']=='unknown' for v in out['items']))
  self.assertEqual(Path(self.a['path']).read_bytes(),original);self.assertNotIn('block_layout',self.r)
 def test_foreign_and_duplicate_product_links_blocked(self):
  with self.assertRaisesRegex(ValueError,'reference'):self.request('save',[{**self.item,'asset_id':'foreign'}])
  with self.assertRaisesRegex(ValueError,'already assigned'):self.request('save',[self.item,{**self.item,'id':'copy'}])
 def test_sectional_is_one_product_with_empty_inner_corner(self):
  self.item.update(shape='l',x=.5,y=.5,width=.7,depth=.7)
  # This small table is in the L's empty inner corner, not a collision.
  table={**self.item,'id':'inside','kind':'table','shape':'box','asset_id':None,'x':.65,'y':.3,'width':.1,'depth':.1}
  self.assertEqual(blocks.checks(self.st,self.r,[self.item,table]),[])
  self.request('save',reviewed=True);scene=shared_floor.build(self.st,self.r)
  self.assertEqual(sum(f['kind']=='block' for f in scene['surfaces']),len(mesh(self.item,self.a)));self.assertEqual(len(scene['products']),1)
 def test_projected_product_bounds_override_approximate_prompt_position(self):
  import json
  from flux_layout_prompt import compile_prompt
  self.request('save',reviewed=True)
  projection=[{'room_id':self.r['id'],'block_id':self.item['id'],'asset_id':self.item['asset_id'],'visible_pixels':100,'guide_bbox_xyxy':[192,108,960,544]}]
  prompt,_=compile_prompt(self.p,self.r,[self.st.asset(self.item['asset_id'])],self.a,projection=projection)
  obj=json.loads(prompt)['subjects'][0];self.assertEqual(obj['image_1_bounds_percent'],[10,9.93,50,50])
  projection[0]['asset_id']='wrong-product'
  with self.assertRaisesRegex(ValueError,'projection'):compile_prompt(self.p,self.r,[self.st.asset(self.item['asset_id'])],self.a,projection=projection)
 def test_old_anchor_does_not_bypass_architecture_in_block_mode(self):
  from plan_preflight import report
  self.request('save',reviewed=True);self.r['anchor_id']=self.item['asset_id'];self.p['map_confirmed']=True
  result=report(self.st,self.p,self.r)
  self.assertFalse(result['can_generate']);self.assertTrue(any(r['id']=='study' and r['level']=='blocked' for r in result['checks']))
 def test_architecture_status_does_not_call_unmapped_floor_clear(self):
  status=self.request('check')['architecture'];self.assertFalse(status['study_reviewed']);self.assertEqual(status['typed_wall_count'],0)
  self.assertTrue(any('endpoints' in t for t in status['notes']))

if __name__=='__main__':unittest.main()
