import sys,tempfile,unittest,copy,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PIL import Image
from store import Store
from engine import Engine,register_asset
from scene_control import clean_control,scene_snapshot,assert_scene,check_protected_output
from render_progress import sampling_plan

ROOT=Path(__file__).resolve().parents[1]
class SceneControlTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(dir=ROOT/'tests');self.root=Path(self.tmp.name);self.st=Store(self.root/'db');self.p=self.st.create_project('Consistency QA');self.r=self.st.add_room(self.p['id'],'Living',bbox=[0,0,1,1]);self.p['map_confirmed']=True
  path=self.root/'master.png';Image.new('RGB',(1920,1080),(75,85,95)).save(path);self.a=register_asset(self.st,self.p['id'],path,'anchor',self.r['id']);self.r['anchor_id']=self.a['id'];self.engine=Engine(self.st,ROOT);self.engine.upload=lambda p:Path(p).name
 def tearDown(self):self.tmp.cleanup()
 def control(self,**extra):return clean_control(self.st,self.p,self.r,dict(mode='region',source_id=self.a['id'],region=[.5,.5,.3,.4],denoise=.75,instruction='Replace only the selected chair',**extra))
 def image(self):
  self.r['scene_control']=self.control();job=self.st.new_job(self.p['id'],'image',self.r['id'],input_revision=self.r['revision'],scene_ticket=scene_snapshot(self.st,self.p,self.r));return job,self.engine.build_image(job,self.root)[0]
 def test_native_mask_and_exact_composite_route(self):
  j,g=self.image();self.assertEqual(g['21']['inputs']['latent_image'],['307',0]);self.assertEqual(g['300']['inputs']['top'],4);self.assertEqual(g['300']['inputs']['bottom'],4);self.assertEqual(g['308']['inputs']['destination'],['300',0]);self.assertFalse(g['308']['inputs']['resize_source']);self.assertEqual(g['23']['inputs']['image'],['308',0]);self.assertEqual(sampling_plan(g)['21']['total'],3)
  self.assertEqual(j['scene_manifest']['content']['anchor']['id'],self.a['id']);self.assertTrue((self.root/'scene-manifest.json').exists())
 def test_changed_file_and_scene_rejected(self):
  original=scene_snapshot(self.st,self.p,self.r);self.r['notes']='Move the chair'
  with self.assertRaises(ValueError):assert_scene(self.st,self.p,self.r,original)
  self.r['notes']='';Image.new('RGB',(1920,1080),'red').save(self.a['path'])
  with self.assertRaises(ValueError):scene_snapshot(self.st,self.p,self.r)
 def test_dimensions_and_invalid_regions_rejected(self):
  for region in [[.9,.9,.5,.5],[0,0,0,.2],[float('nan'),0,.2,.2]]:
   with self.assertRaises(ValueError):clean_control(self.st,self.p,self.r,{'mode':'region','region':region,'instruction':'chair'})
  path=self.root/'small.png';Image.new('RGB',(960,540)).save(path);a=register_asset(self.st,self.p['id'],path,'anchor',self.r['id']);self.r['anchor_id']=a['id']
  with self.assertRaises(ValueError):clean_control(self.st,self.p,self.r,{'mode':'structure'})
 def test_exterior_check_does_not_pass_changed_background(self):
  c=self.control();result=self.root/'result.png';im=Image.open(self.a['path']).convert('RGB');im.putpixel((1000,600),(250,0,0));im.save(result);report=check_protected_output(self.a['path'],result,c);self.assertTrue(report['outside_exact_match']);self.assertGreater(report['inside_mean_channel_change'],0)
  im.putpixel((5,5),(0,0,0));im.save(result);self.assertEqual(check_protected_output(self.a['path'],result,c)['changed_outside_pixels'],1)
 def test_rejected_image_can_be_refined_without_unlocking_video(self):
  from store import approved_image
  path=self.root/'rejected.png';Image.open(self.a['path']).save(path)
  candidate=register_asset(self.st,self.p['id'],path,'image',self.r['id'],status='rejected')
  self.r['images'].append(candidate['id'])
  c=clean_control(self.st,self.p,self.r,dict(mode='region',source_id=candidate['id'],region=[.6,.3,.4,.7],instruction='Remove the extra chair'))
  self.assertEqual(c['source_id'],candidate['id'])
  with self.assertRaises(ValueError):approved_image(self.st,self.p,self.r)
 def test_ltx_gets_same_approved_scene_and_no_image_resize(self):
  plan=register_asset(self.st,self.p['id'],self.a['path'],'plan');self.r['plan_id']=plan['id'];self.p['floor_plans']=[plan['id']]
  camera={'position':[.2,.8],'target':[.5,.2],'height':1.5,'target_height':1.2,'horizontal_fov':75}
  plan['floor_cameras']={self.r['id']:camera}
  image_job,g=self.image();path=self.root/'approved.png';Image.open(self.a['path']).save(path);a=register_asset(self.st,self.p['id'],path,'image',self.r['id'],job_id=image_job['id'],approved_revision=self.r['revision'],status='approved');self.r['images'].append(a['id']);self.r['approved_image_id']=a['id']
  v=self.st.new_job(self.p['id'],'video',self.r['id'],input_revision=self.r['revision'],source_image_id=a['id'],duration=5,motion='still',scene_ticket=scene_snapshot(self.st,self.p,self.r));g,_=self.engine.build_video(v,self.root)
  self.assertEqual(g['9']['class_type'],'ImagePadForOutpaint');self.assertEqual(g['12']['inputs']['strength'],1);self.assertEqual(v['scene_manifest']['parent_image_scene']['fingerprint'],image_job['scene_manifest']['fingerprint']);self.assertEqual(v['scene_manifest']['approved_image']['id'],a['id'])
  self.assertEqual(v['camera_guidance']['camera'],camera);self.assertFalse(v['camera_guidance']['path_enforced'])
  self.assertIn('exact approved camera composition',g['5']['inputs']['text'])
  self.r['notes']='New furniture'
  with self.assertRaises(ValueError):self.engine.build_video(v,self.root)

if __name__=='__main__':unittest.main()
