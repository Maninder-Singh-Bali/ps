import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from prompt_compiler import prepare_edit

class EditPreparationTests(unittest.TestCase):
 def test_simple_words_resolve_explicit_target_and_reference(self):
  r=prepare_edit('pls replace this chair with the refrence, dont change the backgroud','Living','region',['Ingrid cream chair'])
  self.assertIn('please replace this chair with the reference, do not change the background',r['prompt'])
  self.assertIn('selected rectangle',r['prompt']);self.assertIn('Ingrid cream chair',r['prompt'])
  self.assertTrue(r['original'].startswith('pls'));self.assertNotIn('1920',r['original'])
 def test_negations_and_materials_are_not_reinterpreted(self):
  text='Do not replace the chair. Only make the fabric dark blue; keep both wooden arms.'
  r=prepare_edit(text,'Bedroom','region',['Cream chair'])
  self.assertIn(text,r['prompt']);self.assertNotIn('Change the fabric to cream',r['prompt'])
 def test_does_not_guess_measurements_or_product_when_missing(self):
  r=prepare_edit('move the table left','Living','structure')
  self.assertNotIn('Available furniture references',r['prompt']);self.assertNotIn('centimetre',r['prompt']);self.assertIn('move the table left',r['prompt'])
 def test_limited_input(self):
  with self.assertRaises(ValueError):prepare_edit('x'*2501,'Living','region')

if __name__=='__main__':unittest.main()
