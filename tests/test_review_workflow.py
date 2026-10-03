import sys,unittest,tempfile,json,copy,hashlib,threading
from pathlib import Path
from unittest.mock import patch
from PIL import Image
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from store import Store
from engine import register_asset
from detection_review import save_decision,reconcile
from raster_prepare import prepare

class ReviewWorkflow(unittest.TestCase):
    def test_original_bytes_and_rotation_transform_preserved(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as tmp:
            root=Path(tmp);p=root/'original.jpg';im=Image.new('RGB',(120,80));exif=Image.Exif();exif[274]=6;im.save(p,exif=exif)
            before=p.read_bytes();meta=prepare(p,root/'prepared.png')
            self.assertEqual(p.read_bytes(),before);self.assertEqual(meta['source_to_prepared'],[0,1,-1,0,80,0])
            self.assertEqual(meta['prepared_size'],[80,120]);self.assertEqual(meta['source_file_sha256'],hashlib.sha256(before).hexdigest())
    def test_conflict_resolution_is_persistent_and_revision_guarded(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as tmp:
            st=Store(Path(tmp)/'data');p=st.create_project('Review');source=Path(tmp)/'plan.png';Image.new('RGB',(30,30)).save(source)
            a=register_asset(st,p['id'],source,'plan');p['floor_plans']=[a['id']]
            rows=[{'id':str(i),'label':name,'kind':kind,'bbox':[.1,.1,.2,.2],'evidence':'symbol','review_status':'pending'} for i,(name,kind) in enumerate([('toilet','furniture'),('door','door')])]
            a['plan_reading']={'revision':3,'features':[{'id':'manual','notes':'preserve me'}]}
            a['vision_report']={'features':rows,'source_sha256':a['sha256'],'pipeline_key':'v1','stale':False}
            issue=reconcile(a['vision_report'])['review_issues'][0];before=copy.deepcopy(a['plan_reading'])
            data={'revision':0,'pipeline_key':'v1','source_sha256':a['sha256'],'issue_id':issue['id'],'action':'accept','element_id':'0'}
            result=save_decision(st,p['id'],a['id'],data)
            self.assertEqual(result['report']['features'][0]['review_resolution'],'accepted');self.assertEqual(a['plan_reading'],before)
            self.assertEqual(Store(st.root).asset(a['id'])['review_revision'],1)
            with self.assertRaisesRegex(ValueError,'changed'):save_decision(st,p['id'],a['id'],data)
            data['revision']=1;before_failure=copy.deepcopy(a)
            with patch.object(st,'save',side_effect=OSError('Disk full')):
                with self.assertRaises(OSError):save_decision(st,p['id'],a['id'],data)
            self.assertEqual(a,before_failure)
    def test_classification_choice_does_not_clear_source_disagreement(self):
        report={'features':[{'id':'a','label':'toilet','kind':'furniture','bbox':[0,0,1,1],'source_agreement':'disagrees'},
                            {'id':'b','label':'door','kind':'door','bbox':[0,0,1,1]}]}
        issue=reconcile(report)['review_issues'][0];report['review_decisions']={issue['id']:{'action':'accept','element_id':'a'}}
        self.assertTrue(reconcile(report)['features'][0]['location_unresolved'])
    def test_missing_ai_upscaler_has_cached_non_generative_fallback(self):
        from plan_upscale import enhance
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as tmp:
            root=Path(tmp);source=root/'tiny.png';Image.new('RGB',(400,300),'white').save(source);original=source.read_bytes()
            path,meta=enhance(source,root,root/'enlarged')
            self.assertEqual(meta['method'],'Lanczos interpolation');self.assertEqual(meta['output_size'],[800,600])
            self.assertFalse(meta['geometry_reconstructed']);self.assertEqual(source.read_bytes(),original)
            self.assertEqual(enhance(source,root,root/'enlarged')[0],path)
            self.assertTrue(enhance(source,root,root/'enlarged')[1]['cached'])
    def test_accept_label_does_not_validate_bad_geometry(self):
        report={'features':[{'id':'a','label':'toilet','kind':'furniture','bbox':[0,0,1,1],'location_unresolved':True},
                            {'id':'b','label':'door','kind':'door','bbox':[0,0,1,1]}]}
        issue=reconcile(report)['review_issues'][0];report['review_decisions']={issue['id']:{'action':'accept','element_id':'a'}}
        self.assertTrue(reconcile(report)['features'][0]['location_unresolved'])
    def test_synthetic_regression_conflicts_are_geometry_driven(self):
        report=json.loads((Path(__file__).resolve().parent/'fixtures/reconciliation-synthetic.json').read_text())
        result=reconcile(report);self.assertEqual(len(result['features']),12)
        self.assertEqual(len(result['review_issues']),6)
        self.assertEqual(sum('toilet' in i['message'] and 'door' in i['message'] for i in result['review_issues']),3)
        shifted=copy.deepcopy(report)
        for f in shifted['features']:f['bbox']=[f['bbox'][0]/2,f['bbox'][1]/2,f['bbox'][2]/2,f['bbox'][3]/2]
        self.assertEqual(len(reconcile(shifted)['review_issues']),6)
if __name__=='__main__':unittest.main()
