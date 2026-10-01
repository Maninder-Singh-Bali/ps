import sys,unittest,tempfile,copy,json,hashlib
from pathlib import Path
from unittest.mock import patch
from PIL import Image
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from store import Store
from engine import register_asset,Engine
import plan_health,shared_floor,vision_study
from drawing_editor import get_document

class SharedFloorHealth(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(dir=ROOT/'tests');self.root=Path(self.tmp.name);self.st=Store(self.root/'data');self.p=self.st.create_project('Shared QA');self.pid=self.p['id']
  path=self.root/'plan.png';Image.new('RGB',(200,100),'white').save(path);self.a=register_asset(self.st,self.pid,path,'plan');self.aid=self.a['id'];self.p['floor_plans']=[self.aid]
  self.r=self.st.add_room(self.pid,'Living','Lower',self.aid,[0,0,.5,1]);self.other=self.st.add_room(self.pid,'Kitchen','Lower',self.aid,[.5,0,.5,1])
  self.a['drawing']={'revision':0,'features':[{'id':'newwall','kind':'wall','points':[[100,0],[100,100]]},{'id':'newoutside','kind':'wall','points':[[0,0],[200,0]]}],'edits':{}}
  self.f={'id':'passage','kind':'space','label':'Living to kitchen','bbox':[.49,.3,.02,.4],'floor':'Lower','room_id':self.r['id'],'connection_room_id':self.other['id'],'review_status':'confirmed','shape':'unspecified','notes':'No dividing wall'}
  self.a['plan_reading']={'revision':0,'reviewed':True,'features':[self.f],'checks':{},'warnings':[]};self.p['map_confirmed']=True;self.st.save()
  self.a['source_review']={'kind':'plan','reviewed':True,'revision':0,'source_sha256':self.a['sha256'],'panels':[{'id':'plan','bbox':[0,0,1,1]}]}
 def tearDown(self):self.tmp.cleanup()
 def fake_raster(self,source,dest):Image.new('RGB',(200,100),'white').save(dest)
 def test_explicit_courtyard_void_only_cuts_its_own_floor(self):
  from drawing_editor import clean_changes,feature_svg
  from drawing_scene import resolve
  self.other['floor']='Upper'
  feature={'id':'newcourtyard','kind':'floor_opening','points':[[120,20],[160,60]],'thickness':1}
  doc=get_document(self.st,self.pid,self.aid)
  _,features=clean_changes(doc,{'features':[feature]})
  self.assertEqual(feature_svg(features[0]),'')
  self.a['drawing']['features']+=features
  self.assertFalse(any(f['kind']=='floor_opening' for f in resolve(get_document(self.st,self.pid,self.aid))[0]))
  lower=shared_floor.build(self.st,self.r);upper=shared_floor.build(self.st,self.other)
  self.assertEqual(sum(f['kind'] in ('floor','floor_estimate') for f in lower['surfaces']),1)
  floors=[f['points'] for f in upper['surfaces'] if f['kind'] in ('floor','floor_estimate')]
  area=sum((p[1][0]-p[0][0])*(p[2][1]-p[1][1]) for p in floors)
  self.assertAlmostEqual(area,upper['width']*upper['depth']*.84)
  for p in floors:
   self.assertFalse(p[0][0]<upper['width']*.4<p[1][0] and p[0][1]<upper['depth']*.4<p[2][1])
  with self.assertRaises(ValueError):clean_changes(doc,{'features':[{**feature,'points':[[120,20],[160,20]]}]})
 def test_multiple_overlapping_slab_voids_are_not_double_subtracted(self):
  rectangles=shared_floor.floor_rectangles(10,10,[(2,2,6,6),(4,4,8,8)])
  self.assertEqual(sum((r-l)*(b-t) for l,t,r,b in rectangles),72)
 def test_architecture_surfaces_keep_selection_identity(self):
  self.a['drawing']['features'] += [{'id':'newwindow','kind':'window','points':[[20,30],[40,30]],'thickness':2}, {'id':'newdoor','kind':'door','points':[[50,30],[70,30]],'thickness':2}]
  scene=shared_floor.build(self.st,self.r)
  for face in scene['surfaces']:
   if face['kind'] not in ('floor','floor_estimate'):self.assertIn(face.get('source_id'),{'newwall','newoutside','newwindow','newdoor'})
 def test_editor_returns_all_floor_scenes_without_changing_generation_scene(self):
  import furniture_blocks
  self.other['floor']='Upper'
  result=furniture_blocks.request(self.st,self.pid,self.r['id'],{'action':'check','revision':self.r['revision'],'items':[]})
  self.assertEqual([v['scene']['floor'] for v in result['preview_floors']],['Lower','Upper'])
  self.assertEqual(result['preview_scene']['floor'],'Lower')
  self.assertEqual(result['preview_floors'][1]['room_id'],self.other['id'])
 def test_confirmed_passage_cuts_only_intersection_and_is_idempotent(self):
  out,repairs,_=plan_health.repair_plan(self.a)
  self.assertEqual(len(repairs),1);self.assertEqual(repairs[0]['after'][0]['points'],[[100,0],[100,30]])
  self.assertEqual(repairs[0]['after'][1]['points'],[[100,70],[100,100]])
  self.a['drawing']['features']=out;self.assertEqual(plan_health.repair_plan(self.a)[1],[])
 def test_drafts_and_broad_room_boxes_never_erase_walls(self):
  self.f['review_status']='pending';self.assertEqual(plan_health.repair_plan(self.a)[1],[])
  self.f.update(review_status='confirmed',bbox=[.1,.1,.8,.8]);self.assertEqual(plan_health.repair_plan(self.a)[1],[]);self.assertTrue(plan_health.repair_plan(self.a)[2])
 def test_parallel_outside_and_border_segments_not_removed(self):
  for pts in ([[0,0],[0,100]],[[98,0],[98,100]],[[100,0],[100,30]]):self.assertIsNone(plan_health.cut_interval(pts,[98,30,102,70]))
 def test_save_audit_undo_and_source_preservation(self):
  original=Path(self.a['path']).read_bytes()
  with patch('drawing_editor.rasterize',self.fake_raster):
   result=plan_health.apply(self.st,self.pid,self.aid,plan_health.fingerprint(self.a,self.p));self.assertTrue(result['changed']);self.assertFalse(self.p['map_confirmed'])
   self.assertEqual(len(self.a['repair_history']),1)
   plan_health.undo(self.st,self.pid,self.aid,plan_health.fingerprint(self.a,self.p))
  self.assertEqual(Path(self.a['path']).read_bytes(),original);self.assertTrue(self.a['repair_history'][0]['undone'])
  self.assertEqual(self.a['drawing']['features'][0]['points'],[[100,0],[100,100]])
 def test_stale_or_running_repair_is_rejected(self):
  with self.assertRaisesRegex(ValueError,'changed'):plan_health.apply(self.st,self.pid,self.aid,'old')
  self.st.new_job(self.pid,'image',self.r['id'])
  with self.assertRaisesRegex(ValueError,'current activity'):plan_health.apply(self.st,self.pid,self.aid,plan_health.fingerprint(self.a,self.p))
 def test_all_section_views_share_geometry_without_room_box_walls(self):
  self.a['drawing']['features']=[self.a['drawing']['features'][1]]
  left=shared_floor.build(self.st,self.r);right=shared_floor.build(self.st,self.other)
  self.assertEqual(left['geometry_hash'],right['geometry_hash']);self.assertEqual(len(left['lines']),1);self.assertFalse(left['calibrated'])
 def test_camera_scene_uses_library_mesh_and_keeps_object_identity(self):
  from furniture_meshes import mesh
  item={'id':'seat','kind':'sofa','label':'Two seater','seat_count':2,'x':.25,'y':.5,'width':.2,'depth':.2,'height_m':.85,'angle':30,'preset_id':'sofa-2'}
  self.r['block_layout']={'items':[item]};before=copy.deepcopy(self.st.db)
  scene=shared_floor.build(self.st,self.r);faces=[f for f in scene['surfaces'] if f['kind']=='block'];expected=mesh(item,self.a)
  self.assertEqual(len(faces),len(expected));self.assertGreater(len(faces),50)
  for actual,wanted in zip(faces,expected):
   self.assertEqual(actual['object_key'],self.r['id']+':seat');self.assertEqual(actual['color'],wanted['color'])
   for p,q in zip(actual['points'],wanted['points']):
    self.assertAlmostEqual(p[0],q[0]*scene['width']);self.assertAlmostEqual(p[1],q[1]*scene['depth']);self.assertEqual(p[2],q[2])
  self.assertEqual(self.st.db,before)
 def test_camera_validation_and_native_guide(self):
  request={'room_id':self.r['id'],'revision':self.r['revision'],'position':[.2,.8],'target':[.8,.2],'height':1.5}
  with self.assertRaisesRegex(ValueError,'inside'):shared_floor.save_camera(self.st,self.pid,self.aid,{**request,'position':[.8,.8]})
  shared_floor.save_camera(self.st,self.pid,self.aid,request)
  path,meta=shared_floor.create_guide(self.st,self.r,[],self.root)
  with Image.open(path) as im:self.assertEqual(im.size,(1920,1088))
  self.assertTrue(meta['shared_floor']);self.assertFalse(meta['labels_in_image'])
 def test_missing_camera_cannot_generate_geometry(self):
  with self.assertRaisesRegex(ValueError,'camera'):shared_floor.create_guide(self.st,self.r,[],self.root)
 def test_camera_preview_is_non_mutating_and_lens_is_used_in_guide(self):
  import base64,io
  request={'room_id':self.r['id'],'revision':self.r['revision'],'position':[.2,.8],'target':[.8,.2],'height':1.7,'target_height':1.2,'horizontal_fov':85}
  before=copy.deepcopy(self.st.db)
  preview=shared_floor.preview_camera(self.st,self.pid,self.aid,request)
  self.assertEqual(self.st.db,before)
  with Image.open(io.BytesIO(base64.b64decode(preview['image'].split(',')[1]))) as im:self.assertEqual(im.size,(960,540))
  shared_floor.save_camera(self.st,self.pid,self.aid,request)
  scene=shared_floor.build(self.st,self.r)
  self.assertEqual(scene['camera']['target'][2],1.2);self.assertEqual(scene['camera']['horizontal_fov'],85)
  path,meta=shared_floor.create_guide(self.st,self.r,[],self.root)
  self.assertEqual(meta['camera'],scene['camera'])
  with Image.open(path) as im:
   expected=im.crop((0,4,1920,1084));expected.thumbnail((960,540))
   with Image.open(io.BytesIO(base64.b64decode(preview['image'].split(',')[1]))) as actual:self.assertEqual(actual.tobytes(),expected.tobytes())
  for field,value in [('horizontal_fov',101),('horizontal_fov',float('nan')),('target_height',-1)]:
   with self.assertRaises(ValueError):shared_floor.save_camera(self.st,self.pid,self.aid,{**request,'revision':self.r['revision'],field:value})
 def test_camera_change_invalidates_approval_but_same_view_is_idempotent(self):
  request={'room_id':self.r['id'],'revision':self.r['revision'],'position':[.2,.8],'target':[.8,.2],'height':1.5}
  shared_floor.save_camera(self.st,self.pid,self.aid,request);request['revision']=self.r['revision']
  self.r['approved_image_id']='approved';self.r['approved_video_id']='video'
  shared_floor.save_camera(self.st,self.pid,self.aid,request)
  self.assertEqual(self.r['approved_image_id'],'approved')
  shared_floor.save_camera(self.st,self.pid,self.aid,{**request,'horizontal_fov':80})
  self.assertIsNone(self.r['approved_image_id']);self.assertIsNone(self.r['approved_video_id'])
 def test_preview_identifies_furniture_without_changing_geometry(self):
  self.r['block_layout']={'items':[
   {'id':'sofa','label':'Sofa','kind':'sofa','x':.15,'y':.4,'width':.15,'depth':.12,'angle':0},
   {'id':'table','label':'Table','kind':'table','x':.3,'y':.5,'width':.08,'depth':.08,'angle':0}]}
  request={'room_id':self.r['id'],'revision':self.r['revision'],'position':[.25,.9],'target':[.25,.4],'height':1.5,'target_height':.3,'horizontal_fov':90}
  before=copy.deepcopy(self.st.db)
  plain=shared_floor.preview_camera(self.st,self.pid,self.aid,request)
  identified=shared_floor.preview_camera(self.st,self.pid,self.aid,{**request,'identify_objects':True})
  self.assertEqual(plain['objects'],identified['objects']);self.assertNotEqual(plain['image'],identified['image'])
  self.assertEqual([o['label'] for o in identified['objects']],['Sofa','Table'])
  self.assertTrue(all(o['visible_pixels']>0 for o in identified['objects']))
  self.assertNotEqual(identified['objects'][0]['color'],identified['objects'][1]['color'])
  self.assertEqual(self.st.db,before)
 def test_architecture_uses_volumes_and_openings_not_section_boxes(self):
  self.a['drawing']['features']=[{'id':'wall','kind':'wall','points':[[0,0],[40,0]],'thickness':2},
    {'id':'door','kind':'door','points':[[40,0],[60,0]],'thickness':2},
    {'id':'window','kind':'window','points':[[60,0],[100,0]],'thickness':2}]
  scene=shared_floor.build(self.st,self.r)
  wall=[s for s in scene['surfaces'] if s['kind']=='wall'];self.assertEqual(len(wall),6)
  self.assertAlmostEqual(max(p[1] for s in wall for p in s['points'])-min(p[1] for s in wall for p in s['points']),.1)
  self.assertTrue(any(s['kind']=='door_leaf' for s in scene['surfaces']))
  self.assertTrue(any(s['kind']=='window' and s['color']==[182,212,218] for s in scene['surfaces']))
  self.assertEqual(len(scene['lines']),3)
 def test_vision_predictions_remain_pending_and_do_not_overwrite_verified_feature(self):
  row={**self.f,'seat_count':None,'object_type':''};fresh={**row,'id':'visionchair','kind':'furniture','label':'Sofa','bbox':[.1,.1,.1,.2],'seat_count':3}
  self.a['vision_report']={'input_map_revision':self.p['map_revision'],'features':[row,fresh],'source_scope':__import__('source_scope').capture(self.a)}
  result=vision_study.import_proposals(self.st,self.pid,self.aid,{'revision':0})
  self.assertEqual(result['added'],1);self.assertFalse(self.a['plan_reading']['reviewed']);self.assertEqual(self.a['plan_reading']['features'][0]['review_status'],'confirmed')
  self.assertEqual(self.a['plan_reading']['features'][1]['review_status'],'pending')
 def test_invalid_vision_geometry_and_counts_are_not_accepted(self):
  report=vision_study.clean_result({'features':[{'kind':'furniture','bbox':[.1,.1,.2,.2],'seat_count':-4},{'kind':'wall','bbox':[0,0,float('nan'),1]},{'kind':'door','bbox':[.9,.9,.2,.2]}]})
  self.assertEqual(len(report['features']),1);self.assertIsNone(report['features'][0]['seat_count']);self.assertEqual(report['features'][0]['review_status'],'pending')
 def test_product_board_uses_real_reference_indices_and_saved_camera(self):
  from flux_layout_prompt import compile_prompt
  refs=[{'id':'product'+str(n),'category':'Sofa'} for n in range(4)]
  self.r['furniture_layout']={'camera_heading':0,'items':[{'asset_id':r['id'],'x':.2,'y':.5,'angle':90} for r in refs]}
  self.a['floor_cameras']={self.r['id']:{'position':[.05,.5],'target':[.4,.5],'height':1.5}}
  prompt,_=compile_prompt(self.p,self.r,refs,self.a,packed=True);data=json.loads(prompt)
  self.assertEqual([r['image'] for r in data['reference_roles']],[1,2]);self.assertEqual({s['reference_image'] for s in data['subjects']},{2})
  self.assertEqual(data['subjects'][0]['facing'],'away from the camera')
 def test_object_identity_and_seat_counts_survive_review(self):
  import plan_reading
  f={**self.f,'id':'sofa','kind':'furniture','object_type':'sofa','seat_count':3,'connection_room_id':None}
  out=plan_reading.clean_features({'features':[f]},self.p,self.aid)[0]
  self.assertEqual(out['seat_count'],3);self.assertEqual(out['object_type'],'sofa')
  self.a['plan_reading']['features']=[out]
  self.assertIn('seats: 3',plan_reading.instruction(self.a,self.r))
 def test_room_sized_furniture_prediction_is_not_imported(self):
  report=vision_study.clean_result({'features':[{'kind':'furniture','bbox':self.r['bbox'],'label':'sofa','seat_count':3}]})
  report=vision_study.check_observations(report,[self.r]);report['input_map_revision']=self.p['map_revision'];self.a['vision_report']=report;report['source_scope']=__import__('source_scope').capture(self.a)
  self.assertTrue(report['features'][0]['location_unresolved']);self.assertFalse(report['accuracy_verified'])
  with self.assertRaisesRegex(ValueError,'No new usable'):vision_study.import_proposals(self.st,self.pid,self.aid,{'revision':0})
 def test_neighbour_product_changes_invalidate_shared_scene(self):
  from scene_control import scene_snapshot,assert_scene
  ref=register_asset(self.st,self.pid,self.a['path'],'reference',self.other['id'],category='Chair');self.other['references']=[ref['id']]
  scene=scene_snapshot(self.st,self.p,self.r);ref['enabled']=False
  with self.assertRaisesRegex(ValueError,'changed'):assert_scene(self.st,self.p,self.r,scene)

if __name__=='__main__':unittest.main()
