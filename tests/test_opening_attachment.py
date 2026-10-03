"""Draft-only frame pose preservation across JS-compatible hosted coordinates."""
import copy,math,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from drawing_scene import hosted_features
import wall_junctions as J
from shapely import Point
class AttachmentTests(unittest.TestCase):
 def test_preserved_normal_offset_depth_and_hinge(self):
  for end in ([200,0],[0,200],[120,160]):
   for reverse in (True,False):
    w={'id':'w','kind':'wall','points':[[0,0],end],'thickness':20,'height_m':3}
    o={'id':'o','kind':'window','points':[[0,0],[1,0]],'host_wall_id':'w','offset':50,'width':30,'normal_offset':-5,'frame_thickness':10,'thickness':10,'sill_m':.7,'head_m':2.1,'hinge_end':reverse}
    before=copy.deepcopy([w,o]);q=hosted_features(before)[1];u=[v/200 for v in end];n=[-u[1],u[0]];expected=[[u[i]*t-5*n[i] for i in range(2)] for t in (50,80)]
    if reverse:expected.reverse()
    self.assertEqual(q['points'],expected);self.assertEqual(q['thickness'],10);self.assertEqual(before,[w,o])
    self.assertEqual(q,hosted_features([w,q])[1])
 def test_full_host_bands_cut_beside_offset_frame(self):
  fs=[{'id':'w','kind':'wall','points':[[0,0],[200,0]],'thickness':20},{'id':'o','kind':'window','points':[[50,-5],[100,-5]],'host_wall_id':'w','offset':50,'width':50,'normal_offset':-5,'frame_thickness':10,'thickness':10,'sill_m':.9,'head_m':2.4}]
  for z,solid in ((.4,True),(1.5,False),(2.45,True)):
   for y in (-8,8):self.assertEqual(J.at_height(fs,z,2.5)[0].covers(Point(75,y)),solid)
  full=copy.deepcopy(fs);full[1].update(sill_m=0,head_m=2.5)
  for z in (.01,1.5,2.49):self.assertFalse(J.at_height(full,z,2.5)[0].covers(Point(75,0)))
if __name__=='__main__':unittest.main()
