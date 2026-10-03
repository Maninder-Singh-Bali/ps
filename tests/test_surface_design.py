import unittest,copy,sys,tempfile,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import surface_design as sd
import plan_drafts
from shapely import Polygon,Point
class SurfaceDesignTests(unittest.TestCase):
 def setUp(self):
  self.s={'id':'s','kind':'wall','wall_id':'w','side':-1,'label':'Room face'}
  self.o={'id':'p','surface_id':'s','kind':'painting','x':1.,'y':1.5,'width':.6,'height':.8,'depth':.03,'rotation':0,'reference':{'dimension_status':'assumed'}}
  self.d={'features':[{'id':'w','kind':'wall','points':[[100,100],[500,100]],'thickness':20,'height_m':3}], 'calibration':{'metres_per_pixel':.01},'wall_height_m':3,'surface_design':{'version':1,'surfaces':[self.s],'items':[self.o]}}
 def test_face_and_host_motion(self):
  faces=sd.mesh(self.d,[0,0]);self.assertTrue(faces);self.assertAlmostEqual(min(p[1] for f in faces for p in f['points']),.866)
  self.d['features'][0]['points']=[[200,200],[600,200]];moved=sd.mesh(self.d,[0,0]);self.assertAlmostEqual(moved[0]['points'][0][0]-faces[0]['points'][0][0],1);self.assertEqual(self.o['x'],1)
 def test_missing_host_retained(self):
  self.d['features']=[];self.assertEqual(sd.mesh(self.d,[0,0]),[]);self.assertEqual(sd.validate(self.d['surface_design'])['items'][0],self.o)
 def test_opening_clips_finish_one_face(self):
  self.s['finish']={'kind':'paint','color':'#ffffff'};self.d['features'].append({'id':'door','kind':'door','host_wall_id':'w','offset':150,'width':80,'head_m':2.2});region,world=sd.context(self.d,self.s);self.assertFalse(region.contains(Point(1.7,1)));self.assertTrue(region.contains(Point(1.7,2.8)));self.assertLess(world(1,1)[1],1)
 def test_ceiling_voids_and_orientation(self):
  s={'id':'ceil','kind':'ceiling','boundary':[[100,100],[500,100],[500,500],[100,500]],'holes':[[[250,250],[350,250],[350,350],[250,350]]],'elevation_m':3};self.d['surface_design']={'version':1,'surfaces':[s],'items':[]};faces=sd.mesh(self.d,[0,0]);self.assertTrue(faces)
  for f in faces:
   self.assertTrue(f['ceiling']);p=Polygon([p[:2] for p in f['points']]);self.assertLess(p.intersection(Polygon([(2.5,2.5),(3.5,2.5),(3.5,3.5),(2.5,3.5)])).area,1e-8)
  self.assertEqual(sd.context(self.d,s)[1](.5,1,.3),[1.5,2,2.7])
 def test_invalid_and_roundtrip(self):
  raw=copy.deepcopy(self.d['surface_design']);self.assertEqual(sd.validate(raw),raw);raw['items'][0]['width']=0
  with self.assertRaises(ValueError):sd.validate(raw)
  raw=copy.deepcopy(self.d['surface_design']);raw['items'][0]['reference']['image']='https://remote/image'
  with self.assertRaises(ValueError):sd.validate(raw)
 def test_tiles_clip_and_scale(self):
  self.s={'id':'f','kind':'floor','boundary':[[0,0],[200,0],[200,100],[0,100]],'holes':[],'finish':{'kind':'tile','tile_width':1,'tile_length':.5,'grout':0,'color':'#ffffff','grout_color':'#000000'}};self.d['surface_design']={'version':1,'surfaces':[self.s],'items':[]};faces=sd.mesh(self.d,[0,0]);white=[f for f in faces if f['color']==[255,255,255]];self.assertEqual(len(white),8);self.assertAlmostEqual(sum(Polygon([p[:2] for p in f['points']]).area for f in white),2)
if __name__=='__main__':unittest.main()
