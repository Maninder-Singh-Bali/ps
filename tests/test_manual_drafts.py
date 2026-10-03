import copy,io,json,tempfile,unittest
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import plan_drafts as drafts
from drawing_scene import hosted_features,resolve,cut_walls
from PIL import Image

class ManualDraftTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.old=drafts.ROOT;drafts.ROOT=Path(self.tmp.name)
  b=io.BytesIO();Image.new('RGB',(1000,800),'white').save(b,'PNG');m=drafts.upload(b.getvalue(),'floor.png');self.d=drafts.create(m['id'],1)
 def tearDown(self):drafts.ROOT=self.old;self.tmp.cleanup()
 def features(self):
  return [{'id':'w','kind':'wall','points':[[100,100],[500,100]],'thickness':15},{'id':'o','kind':'window','points':[[200,100],[300,100]],'thickness':15,'host_wall_id':'w','offset':100,'width':100,'head_m':2,'sill_m':.8}]
 def test_upload_unscaled_original_preserved(self):
  self.assertIsNone(self.d['calibration']);self.assertEqual([],self.d['features']);self.assertTrue((drafts.folder(self.d['id'])/'original.png').exists())
 def test_pdf_pages_rotation(self):
  import fitz
  p=fitz.open();p.new_page(width=600,height=400);p.new_page(width=300,height=400).set_rotation(90)
  m=drafts.upload(p.tobytes(),'two.pdf');self.assertEqual(2,len(m['pages']));d=drafts.create(m['id'],2);self.assertGreater(d['width'],d['height']);self.assertEqual(90,d['source_page']['rotation'])
 def test_persistence_and_conflict(self):
  d=self.d;d['features']=self.features();d['calibration']={'points':[[100,100],[500,100]],'metres':4};d['notes']='Keep gap';d['background']['rotation']=12
  result=drafts.save(d['id'],d);self.assertEqual(.01,result['calibration']['metres_per_pixel']);self.assertEqual('Keep gap',drafts.get(d['id'])['notes']);self.assertEqual(12,result['background']['rotation'])
  with self.assertRaises(ValueError):drafts.save(d['id'],d)
 def test_inches_persists_without_geometry_conversion(self):
  d=self.d;d['features']=self.features();d['calibration']={'points':[[100,100],[500,100]],'metres':4};d['units']='in'
  drafts.save(d['id'],d);saved=drafts.get(d['id'])
  self.assertEqual('in',saved['units']);self.assertEqual(d['features'],saved['features']);self.assertEqual(.01,saved['calibration']['metres_per_pixel'])
 def test_host_moves_and_shared_cut(self):
  fs=self.features();fs[0]['points'][1]=[100,500];rows=hosted_features(fs);self.assertEqual([[100,200],[100,300]],rows[1]['points']);walls=[f for f in cut_walls(rows) if f['kind']=='wall'];self.assertEqual(2,len(walls));self.assertEqual([100,200],walls[0]['points'][1])
 def test_host_does_not_cut_other_wall(self):
  fs=self.features();fs.append({**fs[0],'id':'other'});rows=cut_walls(hosted_features(fs));self.assertEqual(1,len([f for f in rows if f['id']=='other']))
 def test_same_shared_3d_opening_heights(self):
  d=self.d;d['features']=self.features();d['calibration']={'points':[[100,100],[500,100]],'metres':4};scene=drafts.preview(d);self.assertEqual(2,scene['architecture_counts']['wall']);zs={round(p[2],3) for f in scene['surfaces'] if f['kind']=='window' for p in f['points']};self.assertEqual({.8,2},zs);self.assertTrue(any(f['kind']=='joined_wall' for f in scene['surfaces']))
 def test_unscaled_3d_and_invalid_host_rejected(self):
  with self.assertRaises(ValueError):drafts.preview(self.d)
  self.d['features']=self.features();self.d['features'][1]['host_wall_id']='missing'
  with self.assertRaises(ValueError):drafts.save(self.d['id'],self.d)
 def test_attachment_acknowledgement_survives_save_and_undo_payload(self):
  d=self.d;original=self.features();d['features']=original;d['opening_attachment_revision']=1
  result=drafts.save(d['id'],d);self.assertEqual(1,drafts.get(d['id'])['opening_attachment_revision'])
  # Undo restores original geometry while retaining migration acknowledgement.
  result['features']=[];drafts.save(d['id'],result);reopened=drafts.get(d['id'])
  self.assertEqual([],reopened['features']);self.assertEqual(1,reopened['opening_attachment_revision'])
 def test_no_active_store_or_jobs_in_draft_files(self):
  result=drafts.save(self.d['id'],self.d);self.assertNotIn('jobs',result);self.assertNotIn('generation_phase',result);self.assertTrue(result['draft_only'])
if __name__=='__main__':unittest.main()
