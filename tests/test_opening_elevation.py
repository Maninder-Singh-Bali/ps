import copy,json,math,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from shapely import Point
import wall_junctions as J
import plan_drafts as D
class OpeningElevationTests(unittest.TestCase):
 def test_legacy_window_and_door_bands_without_inferred_hosts(self):
  for kind,base in [('window',.8),('door',0)]:
   f={'id':'o','kind':kind,'points':[[100,0],[200,0]],'thickness':10,'head_m':2,'sill_m':base};before=copy.deepcopy(f)
   self.assertFalse(J.at_height([f],1)[0].covers(Point(150,0)))
   self.assertTrue(J.at_height([f],2.3)[0].covers(Point(150,0)))
   self.assertEqual(kind=='window',J.at_height([f],.4)[0].covers(Point(150,0)))
   self.assertEqual(before,f)
 def test_full_height_glazing_no_solid_bands(self):
  f={'id':'o','kind':'window','points':[[100,0],[200,0]],'thickness':10,'head_m':2.5,'sill_m':0}
  self.assertEqual([],J.mesh([f],.01,[0,0]))
 def test_host_bands_and_glass_frame_follow_same_dimensions(self):
  d={'id':'synthetic','name':'Synthetic opening regression','width':1000,'height':800,'features':[],'background':{},'wall_height_m':3};d['features']=[{'id':'w','kind':'wall','points':[[100,100],[400,500]],'thickness':15,'height_m':3},{'id':'o','kind':'window','points':[[0,0],[1,0]],'thickness':15,'host_wall_id':'w','offset':100,'width':100,'sill_m':.7,'head_m':1.9}];d['calibration']={'points':[[0,0],[100,0]],'metres':1}
  scene=D.preview(d);glass=[f for f in scene['surfaces'] if f['kind']=='window'];frame=[f for f in scene['surfaces'] if f['kind']=='window_frame'];self.assertTrue(glass and frame)
  for fs in [glass,frame]:self.assertEqual({.7,1.9},{round(min(p[2] for f in fs for p in f['points']),5),round(max(p[2] for f in fs for p in f['points']),5)})
  p=Point(190,220)
  for z,solid in [(.4,True),(1,False),(2.4,True)]:self.assertEqual(solid,J.at_height(d['features'],z,3)[0].covers(p))
 def test_raised_door_base_and_lintel(self):
  f={'id':'d','kind':'door','points':[[0,0],[100,0]],'thickness':10,'base_m':.2,'head_m':2.2};p=Point(50,0)
  self.assertTrue(J.at_height([f],.1)[0].covers(p));self.assertFalse(J.at_height([f],1)[0].covers(p));self.assertTrue(J.at_height([f],2.3)[0].covers(p))
if __name__=='__main__':unittest.main()
