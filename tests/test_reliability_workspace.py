import copy,hashlib,io,json,tempfile,unittest
from pathlib import Path
from PIL import Image
import plan_drafts as D,manual_project as M,surface_inputs,portable_project,draft_workspace
from store import Store
class WorkspaceTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name);self.ctx=D.use_root(self.root/'drafts');self.ctx.__enter__();self.addCleanup(self.ctx.__exit__,None,None,None)
  b=io.BytesIO();Image.new('RGB',(1200,800),'#b57a49').save(b,format='PNG');self.raw=b.getvalue();imp=D.upload(self.raw,'plan.png');self.d=D.create(imp['id'],1);self.key=self.d['id'];self.d['features']=[{'id':'a','kind':'wall','points':[[100,100],[700,100]],'thickness':20},{'id':'b','kind':'wall','points':[[700,100],[700,600]],'thickness':20}];self.d['calibration']={'points':[[100,100],[700,100]],'metres':6};self.d=D.save(self.key,self.d);self.st=Store(self.root/'project')
 def reference(self):
  r=D.upload_reference(self.key,self.raw,'photo.png');self.d['surface_design']={'version':1,'surfaces':[{'id':'face','kind':'wall','wall_id':'a','side':1,'label':'Wall'}],'items':[{'id':'art','surface_id':'face','kind':'painting','x':2,'y':1.5,'width':.6,'height':.8,'depth':.03,'rotation':0,'reference':r}]};self.d=D.save(self.key,self.d);return r
 def test_independent_and_explicit_copy(self):
  with D.use_root(self.root/'other'):self.assertEqual(D.listing(),[])
  self.assertEqual(len(D.listing()),1);r=draft_workspace.migrate(self.root/'drafts',self.root/'copy');self.assertTrue(r['files']);self.assertEqual(D.get(self.key),self.d)
  with D.use_root(self.root/'copy'):self.assertEqual(D.get(self.key),self.d)
  with self.assertRaises(ValueError):draft_workspace.migrate(self.root/'drafts',self.root/'copy')
 def test_original_reference_preparation(self):
  r=self.reference();self.assertGreater(r['asset']['width'],r['thumbnail']['width']);plan={'drawing':{'surface_design':self.d['surface_design'],'surface_design_floor':'Floor'},'surface_reference_files':D.reference_files(self.d)}
  info,refs=surface_inputs.prepare(plan,{'floor':'Floor'},self.root/'inputs');self.assertEqual(Path(refs[0]['path']).read_bytes(),self.raw);self.assertFalse(refs[0]['preview_only']);self.assertIsNone(refs[0]['conditioning_derivative'])
  Path(plan['surface_reference_files'][r['asset']['sha256']]).write_bytes(b'changed')
  with self.assertRaisesRegex(ValueError,'hash/size'):surface_inputs.prepare(plan,{'floor':'Floor'},self.root/'bad')
 def test_link_atomic_and_guarded(self):
  old=self.st.create_project('Preserved');before=copy.deepcopy(self.st.db['projects'][old['id']]);result=M.activate(self.st,self.key,{'revision':self.d['revision'],'reviewed':True});p=self.st.project(result['project_id']);self.assertEqual(self.st.project(old['id']),before);self.assertFalse(p['map_confirmed']);self.assertEqual(p['generation_phase']['status'],'paused');self.assertEqual(M.get(self.st,self.key),result['document']);self.assertEqual(len(p['rooms']),1)
  with self.assertRaisesRegex(ValueError,'already linked'):M.activate(self.st,self.key,{'revision':self.d['revision'],'reviewed':True})
 def test_link_failure_and_stale_review(self):
  before=copy.deepcopy(self.st.db)
  for data in ({'revision':0,'reviewed':True},{'revision':self.d['revision']}):
   with self.assertRaises(ValueError):M.activate(self.st,self.key,data)
  self.assertEqual(before,self.st.db)
  from unittest.mock import patch
  with patch.object(self.st,'save',side_effect=OSError('disk full')):
   with self.assertRaises(OSError):M.activate(self.st,self.key,{'revision':self.d['revision'],'reviewed':True})
  self.assertEqual(before,self.st.db);self.assertEqual(json.loads(self.st.path.read_text()),before)
 def test_linked_architecture_cannot_be_overwritten_by_legacy_editor(self):
  self.reference();r=M.activate(self.st,self.key,{'revision':self.d['revision'],'reviewed':True});import drawing_editor
  doc=drawing_editor.get_document(self.st,r['project_id'],r['plan_id']);before=copy.deepcopy(self.st.db)
  drawing_editor.save_document(self.st,r['project_id'],r['plan_id'],doc);self.assertEqual(before,self.st.db)
  changed=copy.deepcopy(doc);changed['features'][0]['thickness']+=1
  with self.assertRaisesRegex(ValueError,'linked floor plan'):drawing_editor.save_document(self.st,r['project_id'],r['plan_id'],changed)
  self.assertEqual(before,self.st.db)
 def test_existing_project_retained(self):
  p=self.st.create_project('Existing');p['generation_phase']={'status':'paused','history':['unchanged']};old=copy.deepcopy(p);r=M.activate(self.st,self.key,{'revision':self.d['revision'],'reviewed':True,'project_id':p['id']});self.assertEqual(old['generation_phase'],p['generation_phase']);self.assertEqual(r['project_id'],p['id'])
 def test_portable_original_and_source(self):
  self.reference();r=M.activate(self.st,self.key,{'revision':self.d['revision'],'reviewed':True});archive=self.root/'copy.zip';portable_project.export_project(self.st.path,r['project_id'],archive);portable_project.import_project(archive,self.root/'imported');st=Store(self.root/'imported');d=M.get(st,self.key);plan=st.asset(r['plan_id']);self.assertTrue(Path(M.source_file(st,self.key,Path(d['source_url']).name)).exists())
  with D.use_root(self.root/'empty'):
   result=M.save(st,self.key,d);info,refs=surface_inputs.prepare(st.asset(r['plan_id']),st.project(r['project_id'])['rooms'][0],self.root/'portable-input');self.assertEqual(Path(refs[0]['path']).read_bytes(),self.raw)
if __name__=='__main__':unittest.main()
