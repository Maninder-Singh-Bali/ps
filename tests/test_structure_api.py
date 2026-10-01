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
  a=self.st.asset(aid);a['source_review']={'kind':'plan','reviewed':True,'revision':0,'source_sha256':a['sha256'],'panels':[{'id':'plan','bbox':[0,0,1,1]}]}
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
 def test_exhausted_analysis_cannot_queue_a_misleading_resume(self):
  from source_scope import capture
  aid,other,base=self.prepare();a=self.st.asset(aid)
  for scope in (None,capture(a)):
   a['vision_report']={'source_scope':scope,'coverage_complete':False,'coverage':{'pending_regions':0,'failed_regions':0,'saturated_regions':4}}
   response=self.call(base+'/read-visual',{},status=400)
   self.assertIn('exhausted',response['error'])
  self.assertFalse(any(j['kind']=='vision_study' for j in self.st.db['jobs'].values()))
  a['vision_report']['coverage']['pending_regions']=1
  self.assertEqual(self.call(base+'/read-visual',{})['kind'],'vision_study')
 def test_plan_errors_block_image_and_video_without_queueing(self):
  aid,other,base=self.prepare();self.call(self.route+'/generate-image',{},status=400);self.call(self.route+'/generate-video',{},status=400)
  self.assertFalse(any(j['kind'] in ('image','video','reference') for j in self.st.db['jobs'].values()))
 def test_resume_preserves_original_scope_not_selected_preview_room(self):
  from source_scope import capture
  aid,other,base=self.prepare();a=self.st.asset(aid)
  for original in ([],[other['id']]):
   report={'pipeline_key':'key'+str(original),'source_scope':capture(a),'coverage_complete':False,'coverage':{'pending_regions':2}}
   previous=self.st.new_job(self.pid,'vision_study',plan_id=aid,section_ids=original)
   previous.update(status='completed',report=report);a['vision_report']=report
   resumed=self.call(base+'/read-visual',{'resume':True,'section_ids':[self.rid]})
   self.assertEqual(resumed['section_ids'],original)
   self.st.db['jobs'][resumed['id']]['status']='completed'
  a['vision_report']={**a['vision_report'],'pipeline_key':'missing'}
  self.call(base+'/read-visual',{'resume':True},status=400)
 def test_block_scan_and_save_through_api(self):
  aid,other,base=self.prepare();route=self.route+'/blocks';before=self.st.snapshot()
  scan=self.call(route,{'action':'propose','revision':self.st.room(self.pid,self.rid)['revision'],'items':[]})
  self.assertEqual(scan['items'],[]);self.assertEqual(before,self.st.snapshot())
  item={'id':'testblock','kind':'table','label':'Table','x':.2,'y':.5,'width':.1,'depth':.15,'angle':0,'seat_count':None}
  result=self.call(route,{'action':'save','revision':self.st.room(self.pid,self.rid)['revision'],'items':[item]})
  room=self.st.room(self.pid,self.rid);self.assertEqual(room['block_layout']['items'][0]['label'],'Table');self.assertFalse(room['block_layout']['reviewed'])
  self.call(route,{'action':'save','revision':-1,'items':[item]},status=400)
  self.assertFalse(any(j['kind'] in ('image','video','reference') for j in self.st.db['jobs'].values()))
 def test_raster_shared_scene_and_export_keep_furniture(self):
  import json,struct
  aid,other,base=self.prepare();a=self.st.asset(aid)
  a['raster_geometry']={'source_sha256':a['sha256'],'analysis_size':[200,100],'walls':[{'id':'wall','width_px':4,'geometry':{'type':'line','points':[[0,0],[200,0]]}}],'openings':[],'uncertain_spans':[]}
  self.st.room(self.pid,self.rid)['block_layout']={'items':[{'id':'chair','kind':'chair','preset_id':'chair','label':'Chair','x':.2,'y':.5,'width':.1,'depth':.1,'angle':0}]}
  shared=self.call(base+'/shared-scene?room_id='+self.rid,{},'GET')
  diagnostic=self.call(base+'/raster-draft',{},'GET')
  self.assertTrue(shared['partial']);self.assertTrue(shared['products']);self.assertEqual(diagnostic['products'],[])
  raw=self.client.get(self.url+base+'/model.glb?room_id='+self.rid).content
  length=struct.unpack('<I',raw[12:16])[0];export=json.loads(raw[20:20+length])
  self.assertTrue(any(n.get('extras',{}).get('stable_element_id','').endswith('chair') for n in export['nodes']))
  self.assertFalse(export['extras']['geometry_validated'])
  state=self.call(base+'/structure',{},'GET')['raster_validation']
  self.call(base+'/raster-validation',{'fingerprint':state['fingerprint'],'source_checked':True,'estimates_acknowledged':True},status=400)

if __name__=='__main__':unittest.main()
