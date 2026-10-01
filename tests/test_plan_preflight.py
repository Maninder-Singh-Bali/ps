import sys,unittest,copy
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from plan_preflight import report,assert_ready

class Checks(unittest.TestCase):
 def setUp(self):
  self.p={'id':'p','map_confirmed':True,'map_revision':1,'floor_plans':['a'],'measurements':[]}
  self.r={'id':'r','name':'Test room','floor':'Ground','plan_id':'a','bbox':[0,0,1,1],'references':[]}
  self.r['furniture_layout']={'plan_id':'a','bbox':[0,0,1,1],'camera_heading':0,'items':[]}
  self.a={'id':'a','project_id':'p','width':100,'height':100,'plan_reading':{'reviewed':True,'features':[]},'drawing':{'features':[{'id':'north','kind':'wall','points':[[0,0],[100,0]]}],'edits':{}}}
  self.assets={'a':self.a};self.asset=lambda key:self.assets[key];self.project=lambda key:self.p
 def codes(self):return {c['id'] for c in report(self,self.p,self.r)['checks'] if c['level']=='blocked'}
 def furniture(self,x,y,size=None):
  self.assets['f']={'id':'f','category':'Sofa','enabled':True};self.r['references']=['f'];self.r['furniture_layout']['items']=[{'asset_id':'f','x':x,'y':y,'angle':0,**({'size':size} if size else {})}]
 def test_reviewed_closed_view_can_generate_but_scale_is_unknown(self):
  out=assert_ready(self,self.p,self.r);self.assertTrue(out['can_generate']);self.assertIn('scale',{r['id'] for r in out['checks']});self.assertIn('saved inputs',out['scope'])
 def test_unreviewed_plan_does_not_silently_generate(self):
  self.a['plan_reading']['reviewed']=False
  with self.assertRaisesRegex(ValueError,'architectural plan study'):assert_ready(self,self.p,self.r)
 def test_open_camera_edge_requires_adjoining_geometry(self):
  self.r['furniture_layout']['camera_heading']=180;self.assertIn('open-view',self.codes())
 def test_wall_cannot_cover_an_opening_but_endpoint_contact_is_valid(self):
  self.a['drawing']['features'].append({'id':'door','kind':'door','points':[[20,0],[40,0]]});self.assertIn('blocked-opening',self.codes())
  self.a['drawing']['features'][0]['points']=[[0,0],[20,0]];self.assertNotIn('blocked-opening',self.codes())
 def test_l_shaped_room_checks_polygon_not_only_bbox(self):
  self.r['area_polygon']=[[0,0],[1,0],[1,.4],[.4,.4],[.4,1],[0,1]];self.furniture(.8,.8);self.assertIn('outside-f',self.codes())
 def test_measured_furniture_footprint_extending_outside_is_blocked(self):
  self.p['measurements']=[{'plan_id':'a','floor':'Ground','outline':[[0,0],[1,0],[1,1],[0,1]],'scale':{'mode':'dimensions','unit':'m','width':4,'height':4}}]
  self.furniture(.1,.5,{'width':2,'depth':1,'unit':'m'});self.assertIn('footprint-f',self.codes())
 def test_unplaced_reference_requires_marker(self):
  self.furniture(.4,.4);self.r['furniture_layout']['items']=[];self.assertIn('placements',self.codes())
 def test_curved_geometry_cannot_be_replaced_by_straight_placeholder(self):
  self.a['plan_reading']['features']=[{'kind':'curved_wall','bbox':[0,0,1,1],'floor':'Ground','room_id':'r','review_status':'confirmed'}]
  self.a['drawing']['features']=[];self.assertIn('curves',self.codes())
 def test_unresolved_stair_connection_blocks_invention(self):
  self.a['plan_reading']['features']=[{'kind':'stair','bbox':[0,0,.2,.2],'floor':'Ground','room_id':'r','review_status':'confirmed'}];self.assertIn('landing',self.codes())
 def test_saved_photo_edit_does_not_claim_plan_verification(self):
  self.r['anchor_id']='photo';self.a['plan_reading']['reviewed']=False
  out=report(self,self.p,self.r);self.assertTrue(out['can_generate']);self.assertIn('master',{v['id'] for v in out['checks']})
 def shared(self,kind='sliding_door'):
  self.r['bbox']=[0,0,.5,1]
  other={'id':'other','name':'Courtyard','floor':'Ground','plan_id':'a','bbox':[.5,0,.5,1]}
  self.p['rooms']=[self.r,other]
  feature={'id':'shared','label':'Courtyard glazing','kind':kind,'bbox':[.49,.2,.02,.6],'floor':'Ground','room_id':'r','connection_room_id':'other','review_status':'confirmed'}
  self.a['plan_reading']['features']=[feature]
  return feature,other
 def test_shared_feature_checked_from_both_sections(self):
  f,other=self.shared()
  for room in (self.r,other):
   check=next(c for c in report(self,self.p,room)['checks'] if c['id']=='connection-shared')
   self.assertEqual(check['level'],'pass');self.assertIn('Courtyard',check['message'])
 def test_shared_opening_cannot_be_solid_wall_in_drawing(self):
  self.shared();self.a['drawing']['features'].append({'kind':'wall','points':[[50,0],[50,100]]})
  self.assertIn('meaning-shared',self.codes())
 def test_shared_feature_must_touch_both_sections(self):
  f,_=self.shared();f['bbox']=[.1,.2,.02,.6];self.assertIn('connection-shared',self.codes())
 def test_independent_crops_cannot_claim_matching_coordinates(self):
  f,other=self.shared();other['plan_id']='crop';self.assertIn('connection-shared',self.codes())
 def test_unresolved_shared_feature_blocks_both_views(self):
  f,other=self.shared();f['review_status']='pending'
  for room in (self.r,other):
   self.assertTrue(any(c['id']=='unresolved' and c['level']=='blocked' for c in report(self,self.p,room)['checks']))
 def test_wall_ending_at_opening_does_not_cross_it(self):
  self.shared();self.a['drawing']['features']=[{'kind':'wall','points':[[50,0],[50,20]]}]
  self.assertNotIn('meaning-shared',self.codes())
if __name__=='__main__':unittest.main()
