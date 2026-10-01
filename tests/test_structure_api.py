import sys,unittest,io
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import test_studio as harness
from PIL import Image

class StructureAPI(unittest.TestCase):
 setUp=harness.StudioTests.setUp
 tearDown=harness.StudioTests.tearDown
 call=harness.StudioTests.call
 def prepare(self):
  buf=io.BytesIO();Image.new('RGB',(200,100),'white').save(buf,format='PNG')
  res=self.client.post(self.url+f'/api/projects/{self.pid}/upload?kind=plan',data=buf.getvalue(),headers={'Content-Type':'application/octet-stream','X-Filename':'plan.png'})
  self.assertEqual(res.status_code,200);aid=res.json()['assets'][0]['id']
  self.call(self.route,{'plan_id':aid,'bbox':[0,0,.5,1]},'PATCH')
  other=self.call(f'/api/projects/{self.pid}/rooms',{'name':'Kitchen','floor':'Ground floor','plan_id':aid,'bbox':[.5,0,.5,1]})
  return aid,other,f'/api/projects/{self.pid}/plans/{aid}'
 def test_structure_and_scene_endpoints_do_not_change_plan(self):
  aid,other,base=self.prepare();before=self.st.snapshot()
  report=self.call(base+'/structure',{},'GET');scene=self.call(base+'/shared-scene?room_id='+self.rid,{},'GET')
  self.assertEqual(len(report['sections']),2);self.assertFalse(report['can_generate']);self.assertEqual(scene['lines'],[]);self.assertTrue(scene['issues'])
  self.assertEqual(before,self.st.snapshot())
 def test_visual_job_deduplicates_and_invalid_sections_are_rejected(self):
  aid,other,base=self.prepare();one=self.call(base+'/read-visual',{'section_ids':[self.rid]});two=self.call(base+'/read-visual',{'section_ids':[self.rid]})
  self.assertEqual(one['id'],two['id']);self.assertEqual(one['kind'],'vision_study')
  self.call(base+'/read-visual',{'section_ids':['missing']},status=400)
  self.call(base+'/import-visual',{'revision':0},status=400)
 def test_plan_errors_block_image_and_video_without_queueing(self):
  aid,other,base=self.prepare();self.call(self.route+'/generate-image',{},status=400);self.call(self.route+'/generate-video',{},status=400)
  self.assertFalse(any(j['kind'] in ('image','video','reference') for j in self.st.db['jobs'].values()))
 def test_block_scan_and_save_through_api(self):
  aid,other,base=self.prepare();route=self.route+'/blocks';before=self.st.snapshot()
  scan=self.call(route,{'action':'propose','revision':self.st.room(self.pid,self.rid)['revision'],'items':[]})
  self.assertEqual(scan['items'],[]);self.assertEqual(before,self.st.snapshot())
  item={'id':'testblock','kind':'table','label':'Table','x':.2,'y':.5,'width':.1,'depth':.15,'angle':0,'seat_count':None}
  result=self.call(route,{'action':'save','revision':self.st.room(self.pid,self.rid)['revision'],'items':[item]})
  room=self.st.room(self.pid,self.rid);self.assertEqual(room['block_layout']['items'][0]['label'],'Table');self.assertFalse(room['block_layout']['reviewed'])
  self.call(route,{'action':'save','revision':-1,'items':[item]},status=400)
  self.assertFalse(any(j['kind'] in ('image','video','reference') for j in self.st.db['jobs'].values()))

if __name__=='__main__':unittest.main()
