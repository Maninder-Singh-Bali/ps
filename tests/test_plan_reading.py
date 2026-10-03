import sys, tempfile, unittest, json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import numpy as np
from PIL import Image,ImageDraw
from store import Store
from engine import register_asset
from plan_reading import detect,repeated_strokes,study,save_reading,get_reading,assert_reviewed,instruction
from plan_area import calibration
import plan_import

class PlanReadingTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(dir=ROOT/'tests');self.root=Path(self.tmp.name);self.st=Store(self.root/'data');self.p=self.st.create_project('Test')
  self.path=self.root/'plan.png';Image.new('RGB',(400,400),'white').save(self.path);self.a=register_asset(self.st,self.p['id'],self.path,'plan');self.p['floor_plans']=[self.a['id']]
  self.a['source_review']={'kind':'plan','reviewed':True,'revision':0,'source_sha256':self.a['sha256'],'panels':[{'id':'plan','bbox':[0,0,1,1]}]}
 def tearDown(self):self.tmp.cleanup()
 def test_stair_runs_both_axes_not_solid_wall(self):
  im=Image.new('L',(400,400),255);d=ImageDraw.Draw(im)
  for y in range(70,200,12):d.line((70,y,120,y),fill=0,width=1)
  self.assertTrue(repeated_strokes(np.array(im)));self.assertTrue(repeated_strokes(np.array(im).T))
  im=Image.new('L',(400,400),255);ImageDraw.Draw(im).rectangle((70,70,120,200),fill=0)
  self.assertEqual(repeated_strokes(np.array(im)),[])
 def test_curved_seats_not_automatically_called_stairs(self):
  im=Image.new('L',(400,400),255);d=ImageDraw.Draw(im);d.arc((50,50,350,350),180,360,fill=0,width=2)
  for x in range(80,320,40):d.ellipse((x,110,x+20,120),outline=0)
  for f in repeated_strokes(np.array(im)):self.assertEqual(f['kind'],'unknown')
 def feature(self):return {'id':'stair1','kind':'stair','review_status':'confirmed','label':'West stair','bbox':[.1,.1,.2,.3],'floor':'Lower','shape':'L-shaped','notes':'User marked stair','source':'manual','room_id':None}
 def test_correction_survives_rescan_and_blocks_unreviewed_map(self):
  d=get_reading(self.st,self.p['id'],self.a['id']);d['features']=[self.feature()]
  saved=save_reading(self.st,self.p['id'],self.a['id'],d)
  scanned=study(self.st,self.p['id'],self.a['id'],{'revision':saved['revision']})
  self.assertEqual(scanned['features'][0]['id'],'stair1');self.assertEqual(scanned['features'][0]['review_status'],'confirmed')
  with self.assertRaises(ValueError):assert_reviewed(self.st,self.p)
  self.assertEqual(len(list((Path(self.p['storage_path'])/'Supporting_Files/Plan_Studies').glob('*.json'))),2)
 def test_stale_and_pending_cannot_approve(self):
  d=get_reading(self.st,self.p['id'],self.a['id']);saved=save_reading(self.st,self.p['id'],self.a['id'],d)
  with self.assertRaises(ValueError):save_reading(self.st,self.p['id'],self.a['id'],d)
  saved['reviewed']=True
  with self.assertRaises(ValueError):save_reading(self.st,self.p['id'],self.a['id'],saved)
  saved['checks']={k:True for k in ('walls','openings','rooms','stairs')}
  save_reading(self.st,self.p['id'],self.a['id'],saved);assert_reviewed(self.st,self.p)
 def test_pending_correction_survives_rescan(self):
  self.a['plan_reading']={'revision':1,'features':[dict(self.feature(),kind='unknown',review_status='pending',source='local_inference')]}
  d=get_reading(self.st,self.p['id'],self.a['id']);d['features'][0]=dict(d['features'][0],kind='furniture',label='Wardrobe candidate')
  saved=save_reading(self.st,self.p['id'],self.a['id'],d)
  self.assertEqual(saved['features'][0]['source'],'manual')
  scanned=study(self.st,self.p['id'],self.a['id'],{'revision':saved['revision']})
  self.assertEqual(scanned['features'][0]['label'],'Wardrobe candidate')
  self.assertEqual(scanned['features'][0]['review_status'],'pending')
 def test_scoped_constraints_preserve_unknown_landing(self):
  self.a['plan_reading']={'features':[dict(self.feature(),connection_room_id=None)]}
  r={'id':'r','floor':'Lower','bbox':[0,0,.8,.8]}
  self.assertIn('do not invent a landing',instruction(self.a,r));self.assertEqual(instruction(self.a,{**r,'floor':'Upper'}),'')
 def test_dxf_units_curves_and_import_transform(self):
  import ezdxf
  doc=ezdxf.new();doc.units=4;m=doc.modelspace();doc.layers.new('A-WALL');m.add_lwpolyline([(0,0),(12000,0),(12000,8000),(0,8000)],close=True,dxfattribs={'layer':'A-WALL'})
  m.add_arc((5000,4000),1000,0,90);path=self.root/'floor.dxf';doc.saveas(path)
  row=plan_import.dxf(path,self.root)[0];meta=row['metadata'];self.assertEqual(meta['units'],'mm');self.assertIn('C',row['vector_path'].read_text())
  with Image.open(row['path']) as im:w,h=im.size
  spanx,spany=meta['drawing_extents'][2:];self.assertAlmostEqual(spanx,12000);self.assertAlmostEqual(spany,8000)
  mpp=meta['metres_per_pixel'];poly=[[35/w,35/h],[(w-35)/w,35/h],[(w-35)/w,(h-35)/h],[35/w,(h-35)/h]]
  _,mult=calibration({'mode':'line','unit':'m','points':[[.1,.5],[.9,.5]],'value':w*.8*mpp},poly,w,h)
  from plan_area import area
  self.assertAlmostEqual(area(poly)*mult,96,places=3)
 def test_unknown_dxf_units_no_automatic_scale(self):
  import ezdxf
  doc=ezdxf.new();doc.units=0;doc.modelspace().add_circle((0,0),12);path=self.root/'unitless.dxf';doc.saveas(path)
  row=plan_import.dxf(path,self.root)[0];self.assertIsNone(row['metadata']['metres_per_pixel'])
 def test_vector_and_scanned_pdf_are_distinguished(self):
  import pymupdf
  doc=pymupdf.open();p=doc.new_page(width=300,height=400);p.draw_rect((20,30,220,300));p.insert_text((50,60),'Living');p.set_rotation(90)
  p=doc.new_page(width=300,height=400);p.insert_image(p.rect,filename=str(self.path));source=self.root/'mixed.pdf';doc.save(source);doc.close()
  rows=plan_import.pdf(source,self.root);self.assertEqual(len(rows),2)
  self.assertTrue(rows[0]['metadata']['vector']);self.assertFalse(rows[1]['metadata']['vector']);self.assertIsNone(rows[1]['vector_path'])
  self.assertNotIn('metres_per_pixel',rows[0]['metadata'])
  with Image.open(rows[0]['path']) as im:self.assertGreater(im.width,im.height)
 def test_dwg_explains_conversion(self):
  with self.assertRaisesRegex(ValueError,'DXF or vector PDF'):plan_import.import_file(self.root/'plan.dwg',self.root)

 def test_shared_opening_instructions_reach_both_sections(self):
  plan={'plan_reading':{'features':[{'id':'opening1','kind':'sliding_door','label':'Courtyard glazing','bbox':[.49,.1,.02,.8],'room_id':'living','connection_room_id':'court','floor':'Lower','review_status':'confirmed','shape':'straight','notes':'One shared boundary'}]}}
  for key in ('living','court'):
   text=instruction(plan,{'id':key,'floor':'Lower','bbox':[0,0,1,1]})
   self.assertIn('opening1',text);self.assertIn('living and court',text)
  self.assertEqual(instruction(plan,{'id':'unrelated','floor':'Lower','bbox':[0,0,1,1]}),'')
 def test_shared_openings_reject_self_and_unregistered_other_plan(self):
  from plan_reading import clean_features
  p={'rooms':[{'id':'a','plan_id':'plan','floor':'Lower'},{'id':'b','plan_id':'crop','floor':'Lower'}]}
  f={**self.feature(),'kind':'sliding_door','room_id':'a','connection_room_id':'a'}
  with self.assertRaisesRegex(ValueError,'different'):clean_features({'features':[f]},p,'plan')
  f['connection_room_id']='b'
  with self.assertRaisesRegex(ValueError,'full plan'):clean_features({'features':[f]},p,'plan')
if __name__=='__main__':unittest.main()
