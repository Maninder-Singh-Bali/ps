import copy,unittest
from drawing_scene import hosted_features,resolve
class LegacyIdentity(unittest.TestCase):
 def test_fallbacks_are_stable_and_non_mutating(self):
  rows=[{'kind':'wall','points':[[0,0],[100,0]],'thickness':10},{'kind':'wall','source_id':'source-wall','points':[[0,0],[0,100]],'thickness':10}];before=copy.deepcopy(rows)
  a=hosted_features(rows);self.assertEqual(a,hosted_features(rows));self.assertEqual([f['id'] for f in a],['typed:0','source-wall']);self.assertEqual(rows,before);self.assertEqual(len(resolve({'features':rows})[0]),2)
 def test_valid_attachments_and_fallback_reference(self):
  rows=[{'kind':'wall','source_id':'host','points':[[0,0],[100,0]],'thickness':10},{'id':'window','kind':'window','host_wall_id':'host','offset':20,'width':30,'points':[[1,1],[2,2]]}]
  result=hosted_features(rows);self.assertEqual(result[1]['id'],'window');self.assertEqual(result[1]['host_wall_id'],'host');self.assertEqual(result[1]['points'],[[20,0],[50,0]])
 def test_existing_ids_never_collide_with_fallback(self):
  rows=[{'kind':'wall','points':[[0,0],[100,0]]},{'id':'typed:0','kind':'wall','points':[[0,0],[0,100]]}];a=hosted_features(rows);self.assertEqual(a[1]['id'],'typed:0');self.assertNotEqual(a[0]['id'],'typed:0')
 def test_unsupported_duplicate_identity_explains(self):
  with self.assertRaisesRegex(ValueError,'unique ID'):hosted_features([{'id':'a','kind':'wall'},{'id':'a','kind':'wall'}])
