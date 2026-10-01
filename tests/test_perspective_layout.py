import sys,tempfile,unittest,json
from pathlib import Path
from unittest.mock import patch
import numpy as np
from PIL import Image
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from store import Store
from engine import register_asset,Engine
from perspective_layout import create,eligible
from scene_control import scene_snapshot

class PerspectiveTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory(dir=ROOT/'tests');self.root=Path(self.temp.name)
  self.st=Store(self.root/'data');self.p=self.st.create_project('Relative layout QA')
  path=self.root/'plan.png';Image.new('RGB',(66,73),'white').save(path)
  self.plan=register_asset(self.st,self.p['id'],path,'plan');self.p['floor_plans'].append(self.plan['id'])
  self.plan['drawing']={'features':[{'id':'newleft','kind':'wall','points':[[3,1],[3,69]]},{'id':'newright','kind':'wall','points':[[61,1],[61,69]]}],'edits':{}}
  self.r=self.st.add_room(self.p['id'],'Living',bbox=[0,0,1,1],plan_id=self.plan['id']);self.p['map_confirmed']=True
  self.refs=[]
  for category in ('Sofa','Coffee table','Chair'):
   ref=register_asset(self.st,self.p['id'],path,'reference',self.r['id'],category=category);self.refs.append(ref);self.r['references'].append(ref['id'])
  self.r['furniture_layout']={'plan_id':self.plan['id'],'bbox':self.r['bbox'],'camera_heading':0,'items':[{'asset_id':a['id'],'x':x,'y':y,'angle':angle} for a,x,y,angle in zip(self.refs,[.18,.48,.48],[.5,.52,.19],[90,0,180])]}
 def tearDown(self):self.temp.cleanup()
 def test_render_has_correct_handedness_and_no_claimed_dimensions(self):
  path,meta=create(self.st,self.r,self.refs,self.root);im=np.asarray(Image.open(path))
  self.assertEqual(im.shape,(1088,1920,3));self.assertIsNone(meta['dimensions']);self.assertFalse(meta['labels_in_image'])
  # Cream sofa is visibly on the left; green chair stays behind the centre table.
  # Sample the distinct cream upholstery, excluding similarly coloured floor/rug.
  sofa=(im[:,:,0]>190)&(im[:,:,0]<226)&((im[:,:,0].astype(int)-im[:,:,1])>=6)&((im[:,:,0].astype(int)-im[:,:,1])<=8)&((im[:,:,1].astype(int)-im[:,:,2])>=19)
  chair=(im[:,:,1]>im[:,:,0])&(im[:,:,0]>100)&(im[:,:,0]<160)
  self.assertGreater(int(chair.sum()),1000);self.assertLess(np.nonzero(sofa)[1].mean(),960);self.assertLess(abs(np.nonzero(chair)[1].mean()-960),150)
 def test_surviving_source_lines_are_not_silently_discarded(self):
  with patch('drawing_editor.get_document',return_value={'elements':[{'id':'base-wall'}]}):self.assertFalse(eligible(self.st,self.r,self.refs))
 def test_unplaced_product_disables_perspective_guess(self):
  self.r['furniture_layout']['items'].pop();self.assertIsNone(create(self.st,self.r,self.refs,self.root))
 def test_empty_architecture_section_does_not_require_furniture_map(self):
  self.r.pop('furniture_layout');self.r['references']=[]
  result=create(self.st,self.r,[],self.root);self.assertIsNotNone(result);self.assertEqual(result[1]['objects'],[])
 def test_wide_room_cutaway_does_not_hide_entire_scene_behind_rear_wall(self):
  self.r.pop('furniture_layout');self.r['references']=[];self.plan.update(width=100,height=50)
  self.plan['drawing']['features']=[{'id':'newback','kind':'wall','points':[[0,50],[100,50]]},{'id':'newfront','kind':'wall','points':[[0,0],[30,0]]},{'id':'newwindow','kind':'window','points':[[30,0],[65,0]]}]
  path,_=create(self.st,self.r,[],self.root);im=np.asarray(Image.open(path));glass=(im[:,:,1]>im[:,:,0])&(im[:,:,0]>190)
  self.assertGreater(int(glass.sum()),1000,'Rear cutaway must expose the front window in wide rooms.')
 def test_workflow_uses_native_guide_and_records_limits(self):
  engine=Engine(self.st,ROOT);engine.upload=lambda path:Path(path).name
  job=self.st.new_job(self.p['id'],'image',self.r['id'],input_revision=self.r['revision'],scene_ticket=scene_snapshot(self.st,self.p,self.r))
  graph,_=engine.build_image(job,self.root)
  self.assertEqual(graph['20']['inputs']['width'],1920);self.assertEqual(graph['20']['inputs']['height'],1088)
  self.assertEqual(graph['4']['inputs']['image'],'perspective_layout_reference.png');self.assertNotIn('200',graph)
  self.assertEqual(job['placement_control']['conditioning_image_count'],4);self.assertIsNotNone(job.get('layout_guide_id'));self.assertTrue(job['perspective_layout']['assumptions'])
  prompt=json.loads(graph['6']['inputs']['text']);self.assertEqual(len(prompt['reference_roles']),4);self.assertEqual([x['count'] for x in prompt['subjects']],[1,1,1]);self.assertEqual(prompt['subjects'][2]['position'],'centre rear, at the matching placeholder in image 1');self.assertEqual(prompt['subjects'][2]['facing'],'toward the camera')
 def test_prompt_facing_rotates_with_the_saved_camera(self):
  from flux_layout_prompt import compile_prompt
  self.r['furniture_layout']['camera_heading']=90
  prompt,_=compile_prompt(self.p,self.r,self.refs,self.plan);subjects=json.loads(prompt)['subjects']
  self.assertEqual(subjects[0]['facing'],'away from the camera');self.assertEqual(subjects[2]['facing'],'toward the image right');self.assertTrue(subjects[2]['position'].startswith('left '))
 def test_surface_cleanup_excludes_unrelated_product_and_map_images(self):
  path=self.root/'master.png';Image.new('RGB',(1920,1080),'white').save(path)
  a=register_asset(self.st,self.p['id'],path,'image',self.r['id']);self.r['images'].append(a['id'])
  self.r['scene_control']={'mode':'region','source_id':a['id'],'region':[.2,.2,.1,.1],'denoise':1.,'instruction':'Remove the faint lettering from this plaster wall.'}
  engine=Engine(self.st,ROOT);engine.upload=lambda path:Path(path).name
  job=self.st.new_job(self.p['id'],'image',self.r['id'],input_revision=self.r['revision'],scene_ticket=scene_snapshot(self.st,self.p,self.r))
  graph,_=engine.build_image(job,self.root)
  self.assertNotIn('100',graph);self.assertNotIn('200',graph);self.assertEqual(job['surface_cleanup']['reference_count'],1)
  self.assertIn('Remove the faint lettering',graph['6']['inputs']['text']);self.assertEqual(graph['23']['inputs']['image'],['330',0])
  self.assertFalse(graph['330']['inputs']['resize_source']);self.assertEqual(graph['20']['inputs']['width'],512);self.assertFalse(job['surface_cleanup']['resized'])
if __name__=='__main__':unittest.main()
