import unittest, sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tests import test_furniture_blocks as fixtures
from scene_scale import clean_model, estimate
from drawing_editor import get_document
from unittest.mock import patch
import shared_floor

class MetricScale(unittest.TestCase):
 setUp=fixtures.FurnitureBlocks.setUp
 tearDown=fixtures.FurnitureBlocks.tearDown
 request=fixtures.FurnitureBlocks.request
 def test_automatic_open_does_not_convert_unclassified_strokes_to_furniture(self):
  import furniture_blocks
  self.a['plan_reading']['features']=[dict(kind='furniture',object_type='unknown',bbox=[.1,.1,.1,.1],floor='Lower')]
  with patch('block_scan.scan') as scan:
   result=self.request('propose',[],automatic=True)
  self.assertEqual(result['items'],[]);scan.assert_not_called()
 def test_multi_section_save_builds_each_floor_once(self):
  drafts=[dict(room_id=self.r['id'],revision=self.r['revision'],items=[self.item])]
  for i in range(5):
   r=self.st.add_room(self.pid,'Room '+str(i),'Upper' if i>2 else 'Lower',self.a['id'],[0,0,1,1])
   drafts.append(dict(room_id=r['id'],revision=r['revision'],items=[{**self.item,'id':'copy'+str(i),'asset_id':None}]))
  with patch('shared_floor.build',wraps=shared_floor.build) as build:
   result=self.request('save-plan',drafts=drafts)
  self.assertEqual(result['saved_sections'],6)
  self.assertEqual(build.call_count,2)
 def test_scale_matches_plan_height_and_library_units(self):
  chair={**self.item,'id':'chair','preset_id':'chair','kind':'chair','width':.055,'depth':.11,'height_m':.85,'asset_id':None}
  self.r['block_layout']={'items':[chair]}
  mpp,source=estimate(self.st,self.a)
  self.assertAlmostEqual(mpp,.025)
  self.a['drawing']['site']={'model':{'metres_per_pixel':.05,'wall_heights':{'Lower':3.4}}}
  scene=shared_floor.build(self.st,self.r)
  self.assertEqual((scene['width'],scene['depth'],scene['height']),(20,10,3.4))
  self.assertAlmostEqual(scene['model_scale']['eye_height_m'],1.5664)
  self.assertFalse(scene['calibrated'])
 def test_reviewed_size_overrides_generic_estimate_and_conflicts_ignored(self):
  self.item.update(physical_size={'width':3.,'depth':1.,'unit':'m'})
  self.item['depth']=.2
  # 3/120 differs from 1/40 by zero.
  self.r['block_layout']={'items':[self.item]}
  self.assertAlmostEqual(estimate(self.st,self.a)[0],.025)
  del self.item['physical_size']
  self.st.asset(self.item['asset_id'])['source_product']={'dimensions_m':{'length':{'metres':3},'width':{'metres':1}},'dimension_notes':['Variant discrepancy']}
  self.assertEqual(estimate(self.st,self.a)[1],'Uncalibrated estimate')
 def test_scale_save_reload_and_preview_preserve_sun(self):
  self.a['drawing']['site']={'north_angle':27,'name':'Original site'}
  doc=get_document(self.st,self.pid,self.a['id'])
  doc['site']['model']={'metres_per_pixel':.06,'wall_heights':{'Lower':3.2},'human_height_m':1.6764,'vertical_fov':70}
  checked=self.request('check',drawing=doc)
  self.assertEqual(checked['preview_scene']['height'],3.2)
  self.assertNotIn('model',self.a['drawing']['site'])
  with patch('drawing_editor.rasterize', side_effect=lambda src,dst:__import__('PIL').Image.new('RGB',(400,200)).save(dst)):
   result=self.request('save-plan',drafts=[{'room_id':self.r['id'],'revision':self.r['revision'],'items':[self.item]}],drawing=doc)
  saved=self.st.asset(self.a['id'])['drawing']['site']
  self.assertEqual(saved['model']['wall_heights']['Lower'],3.2)
  self.assertEqual(saved['north_angle'],27)
  self.assertEqual(result['preview_scene']['width'],24)
 def test_invalid_scale_rejected(self):
  for value in [{'wall_heights':{'Lower':float('nan')}},{'wall_heights':{'Lower':2}},{'metres_per_pixel':0},{'human_height_m':False},{'vertical_fov':120}]:
   with self.assertRaises(ValueError):clean_model(value)

if __name__=='__main__':unittest.main()


