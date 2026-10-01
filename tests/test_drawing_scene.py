import sys,copy,unittest,tempfile,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from drawing_scene import resolve,cut_walls
import shared_floor,furniture_blocks
from store import Store
from engine import register_asset
from PIL import Image

def element(key,kind,svg,**kw):return dict(id=key,kind=kind,svg=svg,**kw)

class DrawingScene(unittest.TestCase):
 def test_saved_source_and_typed_geometry_share_transforms_and_visibility(self):
  doc={'elements':[element('wall','wall','<rect x="0" y="0" width="100" height="4"/>'),element('hidden','wall','<path d="M0 10 H100"/>'),element('paired','wall','<path d="M0 4 H100"/>',absorbed_by='wall')],
   'edits':{'wall':{'dx':10,'dy':20,'sx':2,'sy':3,'rotation':90},'hidden':{'hidden':True}},'features':[{'id':'typed','kind':'wall','points':[[50,50],[60,50]],'thickness':2}]}
  before=copy.deepcopy(doc);rows,unknown=resolve(doc)
  self.assertEqual(unknown,[]);self.assertEqual(len(rows),2);self.assertEqual(doc,before)
  self.assertAlmostEqual(rows[0]['points'][0][0],4);self.assertAlmostEqual(rows[0]['points'][0][1],20)
  self.assertAlmostEqual(rows[0]['points'][1][1],220);self.assertAlmostEqual(rows[0]['thickness'],12)
 def test_window_rect_and_centerline_are_one_opening_and_cut_host_wall(self):
  doc={'elements':[element('w','wall','<rect x="0" y="0" width="100" height="2"/>'),element('win','window','<rect x="40" y="-.5" width="20" height="3"/>'),element('center','window','<path d="M40 1 H60"/>')],'edits':{}}
  rows,_=resolve(doc);self.assertEqual(len(rows),2);out=cut_walls(rows)
  self.assertEqual([r['points'] for r in out if r['kind']=='wall'],[[[0,1],[40,1]],[[60,1],[100,1]]])
  self.assertEqual(len([r for r in out if r['kind']=='window']),1)
 def test_door_symbol_preserves_hinge_closed_span_and_leaf_under_transform(self):
  doc={'elements':[element('d','opening','<g transform="translate(30 40) rotate(90)"><path d="M0 0 V-10"/><path d="M-10 0 A10 10 0 0 1 0 -10"/></g>')],'edits':{'d':{'dx':5}}}
  rows,unknown=resolve(doc);self.assertEqual(unknown,[]);d=rows[0];self.assertEqual(d['kind'],'door')
  for actual,expected in zip(d['points'],[[35,40],[35,30]]):
   for a,b in zip(actual,expected):self.assertAlmostEqual(a,b)
  self.assertEqual(d['leaf_points'][1],[45,40])
 def test_unrecognized_geometry_is_reported_without_becoming_a_box(self):
  rows,unknown=resolve({'elements':[element('curved','wall','<path d="M0 0 Q30 40 50 0"/>'),element('label','detail','<rect width="100" height="100"/>'),element('sofa','furniture','<rect width="10" height="10"/>')]})
  self.assertGreater(len(rows),2);self.assertEqual(unknown,[]);self.assertTrue(all(r['source_id']=='curved' for r in rows))
 def test_openings_do_not_remove_parallel_distant_or_crossing_walls(self):
  wall={'id':'w','kind':'wall','points':[[0,0],[100,0]],'thickness':2}
  for pts in ([[40,10],[60,10]],[[50,-10],[50,10]],[[101,0],[110,0]]):
   out=cut_walls([wall,{'kind':'window','points':pts,'thickness':2}]);self.assertEqual(out[0]['points'],wall['points'])

class SceneIntegration(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(dir=ROOT/'tests');self.root=Path(self.tmp.name);self.st=Store(self.root/'data');self.p=self.st.create_project('Source architecture QA');self.pid=self.p['id']
  png=self.root/'plan.png';Image.new('RGB',(200,100),'white').save(png);self.a=register_asset(self.st,self.pid,png,'plan');self.p['floor_plans']=[self.a['id']]
  self.room=self.st.add_room(self.pid,'Room','Lower',self.a['id'],[0,0,.5,1]);self.upper=self.st.add_room(self.pid,'Room','Upper',self.a['id'],[.6,0,.4,1])
  source=self.root/'base.svg';source.write_text('<svg xmlns="http://www.w3.org/2000/svg"><rect class="wall" x="0" y="0" width="100" height="2"/><rect class="window" x="40" y="-.5" width="20" height="3"/><rect class="wall" x="120" y="0" width="80" height="2"/><rect class="wall" x="98" y="0" width="2" height="100"/></svg>')
  base={'id':'vector','project_id':self.pid,'path':str(source)};self.st.db['assets']['vector']=base;self.a['drawing']={'base_asset_id':base['id'],'features':[],'edits':{},'revision':0}
 def tearDown(self):self.tmp.cleanup()
 def test_base_architecture_enters_shared_scene_and_camera_without_mutation(self):
  before=copy.deepcopy(self.st.db);scene=shared_floor.build(self.st,self.room)
  self.assertEqual(scene['architecture_counts'],{'wall':3,'window':1,'door':0,'sliding_door':0})
  self.assertEqual({f['source_id'] for f in scene['lines']},{'base0','base1','base3'})
  wallpoints=[p for f in scene['surfaces'] if f['kind']=='wall' for p in f['points']]
  mpp=scene['model_scale']['metres_per_pixel']
  self.assertFalse(any(40*mpp<p[0]<60*mpp and p[1]<3*mpp and .9<p[2]<2.4 for p in wallpoints),'Window must not be filled with wall')
  preview=shared_floor.preview_camera(self.st,self.pid,self.a['id'],{'room_id':self.room['id'],'revision':self.room['revision'],'position':[.25,.8],'target':[.25,.05],'height':1.5})
  self.assertEqual(preview['typed_segments'],4);self.assertTrue(preview['image'].startswith('data:image/png'))
  self.assertEqual(self.st.db,before)
  self.assertEqual(len(shared_floor.build(self.st,self.upper)['lines']),1)
 def test_hidden_and_moved_base_walls_update_model_hash_and_placement(self):
  original=shared_floor.build(self.st,self.room);self.a['drawing']['edits']['base3']={'dx':-50}
  moved=shared_floor.build(self.st,self.room);self.assertNotEqual(original['geometry_hash'],moved['geometry_hash'])
  block={'id':'b','label':'Chair','kind':'chair','x':.25,'y':.5,'width':.1,'depth':.1,'angle':0}
  self.assertTrue(any('mapped wall' in i['message'] for i in furniture_blocks.checks(self.st,self.room,[block])))
  self.a['drawing']['edits']['base3']={'hidden':True}
  self.assertFalse(any('mapped wall' in i['message'] for i in furniture_blocks.checks(self.st,self.room,[block])))
  self.assertNotIn('base3',{f['source_id'] for f in shared_floor.build(self.st,self.room)['lines']})

if __name__=='__main__':unittest.main()
