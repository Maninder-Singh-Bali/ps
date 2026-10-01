import unittest
from native_review import rectangle,annotate,classified
from drawing_scene import resolve
from drawing_editor import clean_changes,export_svg

class NativeReview(unittest.TestCase):
 def element(self):
  e={'id':'base2','kind':'detail','native_source_id':'pdfpage1path0','svg':'<path class="detail" d="M10 20 L80 20 L80 25 L10 25 Z"/>'}
  annotate(e,{'plan_source':{'native_paths':[{'fill':[.7,.7,.7],'fill_opacity':1}]}})
  return e
 def test_fill_never_classifies_without_review(self):
  e=self.element();self.assertIn('native_fill_group',e)
  self.assertEqual(resolve({'elements':[e]})[0],[])
  c=classified(e,{'kind':'wall'});rows,unknown=resolve({'elements':[c]})
  self.assertFalse(unknown);self.assertEqual(len(rows),1)
  self.assertEqual(rows[0]['points'],[[10.,22.5],[80.,22.5]])
  self.assertEqual(rows[0]['thickness'],5)
 def test_boxes_cannot_replace_nonrectangular_paths(self):
  for path in ['M0 0 L8 0 L8 8 L4 2 Z','M0 0 L8 0 L8 8','M0 0 Q8 8 0 8 Z','M0 0 L8 0 L8 8 L0 8 L0 0 L8 0']:
   self.assertIsNone(rectangle('<path d="'+path+'"/>'))
  with self.assertRaises(ValueError):classified({'kind':'detail'},{'kind':'wall'})
 def test_review_survives_clean_and_export_and_rejects_invalid_kind(self):
  e=self.element();doc={'elements':[e],'width':100,'height':100}
  edits,features=clean_changes(doc,{'edits':{'base2':{'kind':'wall'}}})
  self.assertEqual(edits['base2']['kind'],'wall')
  self.assertIn('<rect class="wall"',export_svg(doc,edits,features))
  with self.assertRaises(ValueError):clean_changes(doc,{'edits':{'base2':{'kind':'door'}}})
 def test_background_and_transparent_fills_are_not_review_groups(self):
  for source in ({'fill':[1,1,1]},{'fill':[.7,.7,.7],'fill_opacity':.2},{'fill':None}):
   e=self.element();e.pop('native_fill_group');e.pop('native_rectangle')
   annotate(e,{'plan_source':{'native_paths':[source]}})
   self.assertNotIn('native_rectangle',e)
 def test_unclassifying_a_loaded_wall_restores_native_path_and_removes_extrusion(self):
  original=self.element();wall=classified(original,{'kind':'wall'})
  restored=classified(wall,{'kind':'detail'})
  self.assertEqual(restored['svg'],original['svg'])
  self.assertEqual(resolve({'elements':[restored]})[0],[])
  exported=export_svg({'elements':[wall],'width':100,'height':100},{'base2':{'kind':'detail'}},[])
  self.assertNotIn('class="wall"',exported)
