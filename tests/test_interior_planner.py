import unittest,copy
from unittest.mock import patch
import test_structure_api as structure_harness
import test_studio as harness
import scene_control
from interior_style import view_context,surface_references
from placement_map import active_references

class InteriorPlanner(unittest.TestCase):
 setUp=harness.StudioTests.setUp
 tearDown=harness.StudioTests.tearDown
 call=harness.StudioTests.call
 asset=harness.StudioTests.asset
 def prepare(self):
  result=structure_harness.StructureAPI.prepare(self);self.p=self.st.project(self.pid);self.st.db['jobs'].clear();return result
 def camera(self,base,name,**extra):
  return self.call(base+'/floor-camera',{'room_id':self.rid,'revision':self.st.room(self.pid,self.rid)['revision'],'view_name':name,'position':[.2,.5],'target':[.4,.5],'height':1.55,**extra})
 def test_named_views_preserve_other_view_and_reject_changed_scene(self):
  aid,_,base=self.prepare();r=self.st.room(self.pid,self.rid)
  one=self.camera(base,'Seating')['view'];two=self.camera(base,'Reverse',position=[.4,.5],target=[.2,.5])['view']
  tickets={v['id']:scene_control.scene_snapshot(self.st,self.p,view_context(r,v['id'])) for v in [one,two]}
  self.camera(base,'Seating',view_id=one['id'],view_revision=one['revision'],target=[.3,.6])
  with self.assertRaises(ValueError):scene_control.assert_scene(self.st,self.p,r,tickets[one['id']])
  scene_control.assert_scene(self.st,self.p,r,tickets[two['id']])
  from store import Store
  reopened=Store(self.root);self.assertEqual(reopened.room(self.pid,self.rid)['camera_views'],r['camera_views'])
 def test_surface_persistence_scope_and_approval_invalidation(self):
  self.prepare();r=self.st.room(self.pid,self.rid);a=self.asset('reference');r['references'].append(a['id']);r['images']=['prior-image'];r['view_approvals']={'a':{'approved_image_id':'prior-image'}}
  self.call(self.route+'/surfaces',{'revision':r['revision'],'surfaces':{'floor':{'name':'Synthetic tile','variant':'Matt','dimensions':'600 mm','dimension_status':'reviewed','image_ids':[a['id']],'asset_id':a['id']}}})
  self.assertEqual(r['images'],['prior-image']);self.assertEqual(r['view_approvals'],{});self.assertEqual(active_references(self.st,r),[])
  self.assertEqual(surface_references(self.st,r)[0]['surface_target'],'floor')
  self.call(self.route+'/surfaces',{'revision':r['revision'],'surfaces':{'floor':{'image_ids':['foreign']}}},status=400)
  self.assertEqual(r['surfaces']['floor']['variant'],'Matt')
 def test_surface_prompt_is_not_a_furniture_placeholder(self):
  from flux_layout_prompt import compile_prompt
  import json
  prompt,_=compile_prompt({'style':''},{'id':'r','name':'Room','notes':'','surfaces':{},'block_layout':{}},[{'id':'tile','surface_target':'floor'}],{})
  p=json.loads(prompt);self.assertEqual(p['subjects'],[]);self.assertIn('floor',p['reference_roles'][1]['role'])
 def test_dimension_provenance_and_variant_roundtrip(self):
  from furniture_blocks import clean
  row={'id':'a','kind':'sofa','x':.2,'y':.2,'width':.2,'depth':.1,'angle':0,'variant':'Synthetic beige','dimension_status':'reviewed','physical_size':{'width':1.9,'depth':.9}}
  result=clean([row])[0];self.assertEqual(result['variant'],row['variant']);self.assertEqual(result['dimension_status'],'reviewed')
 def test_imageobject_content_url_is_extracted(self):
  import products,json
  html='<script type="application/ld+json">'+json.dumps({'@type':'Product','name':'Synthetic chair','image':[{'@type':'ImageObject','contentUrl':'https://example.com/chair.png'}]})+'</script>'
  value=products.parse_listing(html,'https://example.com/chair')
  self.assertEqual(value['images'],['https://example.com/chair.png']);self.assertEqual(value['image'],value['images'][0])
 def test_selected_review_preserves_outside_proposals_and_expires(self):
  from interior_style import selected_map_ready
  aid,other,base=self.prepare();a=self.st.asset(aid);r=self.st.room(self.pid,self.rid)
  a['construction_selection']={'confirmed':True,'source_sha256':a['sha256'],'floor':r['floor'],'regions':[[[0,0],[.5,0],[.5,1],[0,1]]],'exclusions':[],'revision':1}
  other['floor']='Needs floor assignment';other['bbox']=[.4,.2,.3,.3]
  a['plan_reading']={'reviewed':False,'features':[{'id':'outside','kind':'unknown','bbox':[.7,.2,.1,.1],'review_status':'pending','floor':''}]}
  before=copy.deepcopy(a['plan_reading'])
  preview=self.call(self.route+'/blocks',{'action':'check','revision':r['revision'],'items':[]})
  self.assertEqual([v['scene']['floor'] for v in preview['preview_floors']],[r['floor']])
  self.call(f'/api/projects/{self.pid}/confirm-map',{'plan_id':aid})
  self.assertTrue(selected_map_ready(self.st,self.p,r));self.assertFalse(selected_map_ready(self.st,self.p,other))
  self.assertEqual(before,a['plan_reading']);self.assertEqual(other['floor'],'Needs floor assignment')
  a['plan_reading']['features'].append({'id':'inside','kind':'unknown','bbox':[.1,.2,.1,.1],'review_status':'pending','floor':''})
  self.assertFalse(selected_map_ready(self.st,self.p,r))
  self.call(f'/api/projects/{self.pid}/confirm-map',{'plan_id':aid},status=400)
  a['plan_reading']['features'].pop()
  a['construction_selection']['revision']=2
  self.assertFalse(selected_map_ready(self.st,self.p,r))

 def test_jobs_for_different_views_are_not_deduplicated(self):
  a=self.st.new_job(self.pid,'image',self.rid,view_id='a');b=self.st.new_job(self.pid,'image',self.rid,view_id='b')
  self.assertNotEqual(a['id'],b['id']);self.assertEqual(a['id'],self.st.new_job(self.pid,'image',self.rid,view_id='a')['id'])
 def test_camera_review_checks_visible_neighbours_without_approving_hidden_rooms(self):
  from shared_floor import visible_block_issues
  rooms=[{'id':'active','name':'Active'},{'id':'next','name':'Adjacent'}]
  with patch('shared_floor.sections',return_value=rooms),patch('furniture_blocks.readiness',side_effect=lambda st,r:['Review required'] if r['id']=='next' else []):
   self.assertEqual(visible_block_issues(None,rooms[0],[{'room_id':'next','visible_pixels':0}]),[])
   self.assertEqual(visible_block_issues(None,rooms[0],[{'room_id':'next','visible_pixels':1}]),['Adjacent: Review required'])

if __name__=='__main__':unittest.main()
