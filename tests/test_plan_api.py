import sys,io,json,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import test_studio as harness
import ezdxf,pymupdf
from project_storage import relocate
from plan_area import summarize

class PlanAPITests(unittest.TestCase):
 setUp=harness.StudioTests.setUp
 tearDown=harness.StudioTests.tearDown
 call=harness.StudioTests.call
 def upload(self,path):
  res=self.client.post(self.url+f'/api/projects/{self.pid}/upload?kind=plan',data=path.read_bytes(),headers={'Content-Type':'application/octet-stream','X-Filename':path.name})
  self.assertEqual(res.status_code,200,res.text);return res.json()['assets']
 def test_dxf_upload_scale_original_and_study_gate(self):
  doc=ezdxf.new();doc.units=6;doc.layers.new('A-DOOR');doc.modelspace().add_lwpolyline([(0,0),(12,0),(12,8),(0,8)],close=True);doc.modelspace().add_arc((3,3),1,0,90,dxfattribs={'layer':'A-DOOR'})
  source=self.root/'house.dxf';doc.saveas(source);aid=self.upload(source)[0]['id'];a=self.st.asset(aid)
  self.assertEqual(a['plan_source']['units'],'m');self.assertIn(a['native_vector_id'],self.st.db['assets']);self.assertEqual(Path(self.st.asset(a['original_document_id'])['path']).read_bytes(),source.read_bytes())
  self.call(f'/api/projects/{self.pid}/confirm-map',{},status=400)
  doc=self.call(f'/api/projects/{self.pid}/plans/{aid}/study',{'revision':0})
  self.assertTrue(any(f['kind']=='door' for f in doc['features']));self.assertFalse(doc['reviewed'])
  # Actual native coordinates, including page margins, produce 96 square metres.
  w,h=a['width'],a['height'];outline=[[35/w,35/h],[(w-35)/w,35/h],[(w-35)/w,(h-35)/h],[35/w,(h-35)/h]]
  result=summarize(outline,[outline],{'mode':'line','unit':'m','points':[[.1,.5],[.9,.5]],'value':.8*w*a['plan_source']['metres_per_pixel']},w,h)
  self.assertAlmostEqual(result['area_m2']['total'],96,places=3)
 def test_pdf_multi_page_preserves_source_once(self):
  pdf=pymupdf.open()
  for i in range(2):pdf.new_page().draw_rect((20,30,400,600))
  source=self.root/'two.pdf';pdf.save(source);pdf.close();rows=self.upload(source);self.assertEqual(len(rows),2)
  a,b=[self.st.asset(r['id']) for r in rows];self.assertEqual(a['original_document_id'],b['original_document_id']);self.assertNotIn('metres_per_pixel',a['plan_source'])
  
  for job in list(self.st.db['jobs'].values()):
   if job['kind']=='plan_setup':self.call('/api/jobs/'+job['id']+'/cancel',{})
  dest=self.root/'Relocated';dest.mkdir();relocate(self.st,self.pid,str(dest))
  self.assertTrue(Path(self.st.asset(a['original_document_id'])['path']).is_relative_to(dest))
 def test_reviewed_space_becomes_section_without_duplicate(self):
  from PIL import Image
  source=self.root/'raster.png';Image.new('RGB',(100,100),'white').save(source);aid=self.upload(source)[0]['id'];base=f'/api/projects/{self.pid}/plans/{aid}'
  doc=self.call(base+'/reading',{},'GET');doc['features']=[{'id':'space1','kind':'space','review_status':'confirmed','label':'Dining','bbox':[.1,.1,.4,.4],'floor':'Ground','source':'manual'}]
  doc=self.call(base+'/reading',doc);d={'feature_id':'space1','revision':doc['revision'],'map_revision':doc['map_revision']};first=self.call(base+'/study-section',d)
  self.assertEqual(self.st.room(self.pid,first['room_id'])['name'],'Dining');self.assertFalse(self.st.project(self.pid)['map_confirmed'])
  second=self.call(base+'/study-section',{**d,'revision':first['reading']['revision'],'map_revision':first['reading']['map_revision']})
  self.assertEqual(first['room_id'],second['room_id']);self.assertEqual(len(self.st.project(self.pid)['rooms']),2)

if __name__=='__main__':unittest.main()
