import sys,json,math,subprocess,copy,unittest,os,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from furniture_meshes import mesh,components,instances

class FurnitureMeshes(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  node=os.environ.get('PIXELOID_NODE') or (str(ROOT/'runtime/node/node.exe') if (ROOT/'runtime/node/node.exe').is_file() else shutil.which('node'))
  if not node:raise RuntimeError('Node.js is required; see SOURCE_SETUP.md.')
  cls.fixtures=json.loads(subprocess.check_output([node,str(ROOT/'tests/mesh_browser_fixtures.cjs')]))
 def test_all_presets_and_transforms_match_browser_and_do_not_mutate(self):
  for row in self.fixtures['models']:
   item=row['item'];before=copy.deepcopy(item);actual=mesh(item,self.fixtures['plan'])
   self.assertEqual(len(actual),len(row['mesh']),item['id'])
   for a,b in zip(actual,row['mesh']):
    self.assertEqual(a['part'],b['part']);self.assertEqual(a['color'],b['color'])
    for ap,bp in zip(a['points'],b['points']):
     for x,y in zip(ap,bp):self.assertAlmostEqual(x,y,places=10,msg=item['id'])
   self.assertEqual(item,before)
 def test_models_stay_inside_saved_footprint_and_height(self):
  plan=self.fixtures['plan']
  for row in self.fixtures['models']:
   v=row['item'];a=math.radians(-v['angle']);c,s=math.cos(a),math.sin(a)
   for face in mesh(v,plan):
    for x,y,z in face['points']:
     x=(x-v['x'])*plan['width'];y=(y-v['y'])*plan['height'];xx=x*c-y*s;yy=x*s+y*c
     self.assertLessEqual(abs(xx),v['width']*plan['width']/2+1e-8,v['id'])
     self.assertLessEqual(abs(yy),v['depth']*plan['height']/2+1e-8,v['id'])
     self.assertGreaterEqual(z,v.get('elevation_m',0)-1e-8);self.assertLessEqual(z,v['height_m']*(1.25 if v['preset_id']=='staircase-spiral' else 1)+v.get('elevation_m',0)+1e-8,v['id'])
 def test_sofa_seats_and_open_l_corner(self):
  for row in self.fixtures['models']:
   v=row['item']
   if v['kind']!='sofa':continue
   ps=components(v);self.assertEqual(sum(p['role']=='seat' for p in ps),v['seat_count'])
   self.assertTrue(any(p['role']=='back' for p in ps));self.assertTrue(any(p['role']=='arm' for p in ps))
   if v['shape']=='l':
    m=v.get('sofa_modules',{});lw=m.get('leg_width',v['width']*.4)/v['width'];ld=m.get('leg_depth',v['depth']*.4)/v['depth']
    for p in ps:
     x,y,z,w,d,h=p['bounds'];x=1-x-w if v['return_side']=='right' else x
     self.assertTrue(x+w<=lw+1e-8 or y>=1-ld-1e-8,p)
 def test_chair_group_and_bed_table_parts_are_recognizable(self):
  rows={r['item']['id']:r['item'] for r in self.fixtures['models']};plan=self.fixtures['plan']
  self.assertEqual(len(instances(rows['group'],plan)),6)
  self.assertEqual(sum(f['part']=='seat' for f in mesh(rows['group'],plan)),6*10)
  for key,roles in [('chair',{'leg','back','seat'}),('coffee-table',{'leg','top'}),('bed-double',{'headboard','mattress','pillow'}),('refrigerator',{'door','handle'}),('bookcase',{'shelf','back'})]:
   self.assertTrue(roles<={p['role'] for p in components(rows[key])},key)
 def test_lighting_art_and_spiral_save_with_mounting_and_winding(self):
  from furniture_blocks import clean
  rows={r['item']['id']:r['item'] for r in self.fixtures['models']}
  for key in ('floor-lamp','table-lamp','ceiling-light','wall-light','pendant-light','chandelier','painting-landscape','painting-portrait','painting-square','staircase-spiral'):
   v=rows[key];saved=clean([v])[0]
   self.assertEqual(saved['preset_id'],key)
   self.assertEqual(saved.get('elevation_m',0),v.get('elevation_m',0))
   self.assertEqual(mesh(saved,self.fixtures['plan']),mesh(v,self.fixtures['plan']))
  spiral=rows['staircase-spiral'];ps=components(spiral)
  self.assertEqual(sum(p['role']=='step' for p in ps),17)
  self.assertTrue(any(p['role']=='column' for p in ps))
  v={**rows['table-lamp'],'elevation_m':float('nan')}
  with self.assertRaises(ValueError):clean([v])
 def test_legacy_items_use_kind_and_round_fallback(self):
  v={'id':'old','kind':'sofa','x':.5,'y':.5,'width':.2,'depth':.1,'angle':40,'seat_count':2}
  self.assertEqual(sum(p['role']=='seat' for p in components(v)),2)
  v.update(kind='pillar',shape='round');self.assertEqual(components(v)[0]['type'],'cylinder')
  v.update(kind='unknown');self.assertEqual(len(mesh(v,self.fixtures['plan'])),6)

if __name__=='__main__':unittest.main()
