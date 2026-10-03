import copy,json,math,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from shapely import Point,Polygon,LineString,unary_union
import wall_junctions as J
import plan_drafts

def wall(i,a,b,t=20):return {'id':i,'kind':'wall','points':[a,b],'thickness':t}
def polygon_result(r):return unary_union([Polygon(p['outer'],p['holes']) for p in r['rings']])
class JunctionTests(unittest.TestCase):
 def test_l_inside_and_outside_faces(self):
  fs=[wall('a',[0,0],[100,0]),wall('b',[0,0],[0,100])];g=polygon_result(J.resolve(fs))
  self.assertTrue(g.covers(Point(-9,-9)));self.assertTrue(g.covers(Point(9,9)));self.assertFalse(g.covers(Point(11,11)));self.assertEqual(4000,g.area);self.assertEqual('Polygon',g.geom_type)
 def test_unequal_l(self):
  fs=[wall('a',[0,0],[100,0],20),wall('b',[0,0],[0,100],40)];g=polygon_result(J.resolve(fs));self.assertTrue(g.covers(Point(-19,-9)));self.assertFalse(g.covers(Point(21,11)));self.assertTrue(g.is_valid)
 def test_t_midpoint_and_crossing(self):
  fs=[wall('a',[-100,0],[100,0],20),wall('b',[0,0],[0,100],40)]
  self.assertAlmostEqual(7600,polygon_result(J.resolve(fs)).area)
  fs[1]['points']=[[0,-100],[0,100]];self.assertAlmostEqual(11200,polygon_result(J.resolve(fs)).area)
 def test_acute_bevel_bound(self):
  fs=[wall('a',[0,0],[200,0]),wall('b',[0,0],[200,10])];r=J.resolve(fs);g=polygon_result(r)
  self.assertTrue(any(j['kind']=='bevel' for j in r['joins']));self.assertGreaterEqual(g.bounds[0],-30);self.assertTrue(g.is_valid)
 def test_intentional_small_gap(self):
  fs=[wall('a',[0,0],[100,0]),wall('b',[101,0],[200,0])];g=polygon_result(J.resolve(fs));self.assertEqual(2,len(J.polygons(g)));self.assertFalse(g.covers(Point(100.5,0)))
 def test_split_delete_move_and_thickness_recompute(self):
  fs=[wall('a',[0,0],[100,0]),wall('b',[0,0],[0,100])];original=polygon_result(J.resolve(fs))
  split=[wall('a',[0,0],[50,0]),wall('c',[50,0],[100,0]),fs[1]];self.assertTrue(original.equals(polygon_result(J.resolve(split))))
  del split[2];self.assertFalse(polygon_result(J.resolve(split)).covers(Point(-5,-5)))
  moved=copy.deepcopy(fs);moved[0]['points'][0]=[10,10];moved[1]['points'][0]=[10,10];self.assertFalse(original.equals(polygon_result(J.resolve(moved))))
  moved[0]['thickness']=40;self.assertNotEqual(J.resolve(fs)['hash'],J.resolve(moved)['hash'])
 def test_attached_opening_and_window_bands(self):
  fs=[wall('a',[0,0],[400,0]),wall('b',[0,0],[0,100]),{'id':'door','kind':'door','host_wall_id':'a','offset':120,'width':90,'points':[[120,0],[210,0]],'thickness':20}, {'id':'window','kind':'window','host_wall_id':'a','offset':270,'width':70,'points':[[270,0],[340,0]],'thickness':20,'sill_m':.9,'head_m':2.1}]
  g=polygon_result(J.resolve(fs));self.assertFalse(g.covers(Point(150,0)));self.assertFalse(g.covers(Point(300,0)))
  lo,_=J.at_height(fs,.5);middle,_=J.at_height(fs,1.5);hi,_=J.at_height(fs,2.3)
  self.assertTrue(lo.covers(Point(300,0)));self.assertFalse(middle.covers(Point(300,0)));self.assertTrue(hi.covers(Point(150,0)))
  original=copy.deepcopy(fs);J.mesh(fs,.01,[0,0]);self.assertEqual(original,fs)
 def test_no_internal_caps_or_top_triangle_lines(self):
  fs=[wall('a',[0,0],[100,0]),wall('b',[0,0],[0,100])];g=polygon_result(J.resolve(fs));faces=J.mesh(fs,1,[0,0]);self.assertTrue(any(not all(f['edge_mask']) for f in faces))
  for f in faces:
   zs={p[2] for p in f['points']}
   if len(zs)==2:
    a,b=f['points'][:2];self.assertLess(g.boundary.distance(Point((a[0]+b[0])/2,(a[1]+b[1])/2)),1e-8)
if __name__=='__main__':unittest.main()
