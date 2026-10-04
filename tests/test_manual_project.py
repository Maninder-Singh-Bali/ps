import copy,tempfile,unittest
from pathlib import Path
from store import Store
import manual_project,plan_drafts

class LinkedManualProject(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.st=Store(self.tmp.name);p=self.st.create_project('New apartment');self.pid=p['id']
  self.d={'id':'linked','name':'New apartment','revision':0,'width':400,'height':300,'features':[{'id':'w','kind':'wall','points':[[10,10],[200,10]],'thickness':10,'height_m':2.8}],'calibration':{'points':[[10,10],[110,10]],'metres':2},'wall_height_m':2.8,'surface_design':{'version':1,'surfaces':[],'items':[]},'active_project_id':self.pid}
  self.d=plan_drafts.validate(self.d,self.d)
  self.st.db['assets']['plan']={'id':'plan','project_id':self.pid,'path':str(Path(self.tmp.name)/'plan.png'),'manual_draft_id':'linked','manual_document':self.d,'manual_floor':'Apartment','drawing':{'features':copy.deepcopy(self.d['features']),'surface_design':copy.deepcopy(self.d['surface_design']),'site':{'model':{'metres_per_pixel':.02,'wall_heights':{'Apartment':2.8}}}}}
  p['floor_plans']=['plan'];self.r=self.st.add_room(self.pid,plan_id='plan',bbox=[0,0,1,1]);self.r['approved_image_id']='prior';self.st.save()
 def test_preview_stays_on_requested_floor(self):
  from unittest.mock import patch
  second=copy.deepcopy(self.st.asset('plan'));second.update(id='upper-plan',manual_draft_id='upper',manual_floor='Upper')
  second['manual_document']['id']='upper';self.st.db['assets']['upper-plan']=second
  upper=self.st.add_room(self.pid,plan_id='upper-plan',bbox=[0,0,1,1]);self.st.project(self.pid)['manual_preview_room_id']=self.r['id']
  before=copy.deepcopy(self.st.db)
  with patch('shared_floor.build',side_effect=lambda store,room:room['plan_id']):
   self.assertEqual(manual_project.preview(self.st,second['manual_document']),'upper-plan')
   self.assertEqual(manual_project.preview(self.st,self.d),'plan')
  self.assertEqual(before,self.st.db)
 def test_atomic_authority_and_reopen_invalidation(self):
  data=copy.deepcopy(self.d);data['features'][0]['height_m']=3
  result=manual_project.save(self.st,'linked',data)
  re=Store(self.tmp.name);self.assertEqual(manual_project.get(re,'linked'),result);self.assertEqual(re.asset('plan')['drawing']['features'][0]['height_m'],3);self.assertEqual(re.room(self.pid,self.r['id'])['revision'],2);self.assertIsNone(re.room(self.pid,self.r['id'])['approved_image_id'])
  with self.assertRaisesRegex(ValueError,'another window'):manual_project.save(re,'linked',data)
 def test_units_only_do_not_invalidate(self):
  data=copy.deepcopy(self.d);data['units']='in';manual_project.save(self.st,'linked',data);self.assertEqual(self.r['revision'],1);self.assertEqual(self.r['approved_image_id'],'prior')
 def test_job_lock_keeps_scene_unchanged(self):
  self.st.db['jobs']['j']={'project_id':self.pid,'kind':'image','status':'running'};before=copy.deepcopy(self.st.db)
  with self.assertRaisesRegex(ValueError,'current job'):manual_project.save(self.st,'linked',self.d)
  self.assertEqual(before,self.st.db)
 def test_invalid_geometry_does_not_mutate(self):
  before=copy.deepcopy(self.st.db);data=copy.deepcopy(self.d);data['features'][0]['points']=[[1,1],[1,1]]
  with self.assertRaises(ValueError):manual_project.save(self.st,'linked',data)
  self.assertEqual(before,self.st.db)
if __name__=='__main__':unittest.main()
