import copy, tempfile, unittest
from pathlib import Path
from PIL import Image
from store import Store
from engine import register_asset
from revision_comparison import review,crop_bounds

class ComparisonTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.st=Store(self.root/'db');self.p=self.st.create_project('Comparison');self.r=self.st.add_room(self.p['id'])
  def asset(name,kind,size):
   path=self.root/(name+'.png');Image.new('RGB',size,'white').save(path);return register_asset(self.st,self.p['id'],path,kind,self.r['id'])
  self.ref=asset('historical','reference',(300,400));self.parent=asset('parent','image',(1920,1080));self.result=asset('result','image',(1920,1080));self.r['images']=[self.parent['id'],self.result['id']]
  self.result.update(source_image_id=self.parent['id'],status='review',review_decision='kept',job_id='job')
  self.control={'mode':'region','source_id':self.parent['id'],'reference_id':self.ref['id'],'region':[.4,.1,.1,.2],'reference_crop':[.1,.1,.5,.5]}
  self.manifest={'master_image':{'id':self.parent['id'],'sha256':self.parent['sha256']},'preservation':self.control,'content':{'products':[{'id':self.ref['id'],'sha256':self.ref['sha256'],'category':'Historical title'}]}}
  self.st.db['jobs']['job']={'project_id':self.p['id'],'scene_manifest':self.manifest};self.st.save()
 def tearDown(self):self.tmp.cleanup()
 def test_historical_reference_parent_crop_and_review_state(self):
  before=copy.deepcopy(self.st.db);d=review(self.st,self.result['id'])
  self.assertEqual(d['parent']['id'],self.parent['id']);self.assertEqual(d['parent']['version'],1);self.assertEqual(d['result']['version'],2)
  self.assertEqual(d['reference']['id'],self.ref['id']);self.assertEqual(d['reference']['crop'],[30,40,150,200]);self.assertEqual(d['reference']['crop'][2]/d['reference']['crop'][3],.75)
  self.assertEqual(d['review_decision'],'kept');self.assertEqual(d['status'],'review');self.assertIsNotNone(d['crop']);self.assertEqual(before,self.st.db)
 def test_changed_missing_reference_is_not_replaced_with_current(self):
  Image.new('RGB',(300,400),'black').save(self.ref['path']);self.r['references']=['some-current-reference']
  d=review(self.st,self.result['id']);self.assertIsNone(d['reference']);self.assertIn('unavailable',d['reference_note'])
 def test_manifest_parent_recovery_is_explicit_and_missing_mask_falls_back(self):
  self.result.pop('source_image_id');self.control.pop('region')
  d=review(self.st,self.result['id']);self.assertEqual(d['parent_note'],'recorded manifest evidence');self.assertIsNone(d['crop']);self.assertIn('No saved mask',d['fallback_reason'])
 def test_conflicting_parent_links_are_not_guessed(self):
  self.st.db['jobs']['job']['source_image_id']='different';d=review(self.st,self.result['id']);self.assertIsNone(d['parent']);self.assertIsNone(d['crop']);self.assertIn('Conflicting',d['parent_note'])
 def test_polygon_crop_shared_margin_clamps_to_image(self):
  box,poly=crop_bounds({'mask_polygon':[[0,.1],[.1,.1],[.1,.2],[0,.2]]},1920,1080)
  self.assertEqual(box[0],0);self.assertGreater(box[2],192);self.assertLess(box[1],108);self.assertEqual(poly[1],[192,108])
  self.assertEqual(crop_bounds({},1920,1080),(None,None))
if __name__=='__main__':unittest.main()
