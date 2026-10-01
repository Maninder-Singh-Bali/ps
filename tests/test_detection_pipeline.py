import sys,unittest,tempfile,json,copy
from pathlib import Path
from unittest.mock import patch
from PIL import Image
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from detection_review import reconcile,compare_sources
import object_detection,detection_pipeline

def obj(label,kind='furniture',box=None):return {'id':label,'label':label,'object_type':label,'kind':kind,'bbox':box or [.1,.1,.1,.1],'evidence':'visible symbol','confidence':'low'}
class Response:
    def __init__(self,rows):self.rows=rows
    def raise_for_status(self):pass
    def json(self):return {'message':{'content':json.dumps({'rooms':[],'objects':self.rows})}}
class FakeSession:
    trust_env=False
    def __init__(self,rows=None):self.rows=rows or [];self.calls=0
    def post(self,url,**kw):
        if url.endswith('/chat'):self.calls+=1
        return Response(self.rows)
    def close(self):pass

class PipelineTests(unittest.TestCase):
    def test_truncated_output_keeps_complete_rows_only(self):
        text='{"objects":[{"name":"chair","bbox_2d":[0,0,100,100]},{"name":"unfinished'
        self.assertEqual(detection_pipeline.recover_finished_rows(text,'objects'),[{'name':'chair','bbox_2d':[0,0,100,100]}])
        self.assertEqual(detection_pipeline.recover_finished_rows('not JSON','objects'),[])
    def test_cross_category_conflict_is_one_issue_and_input_unchanged(self):
        source={'features':[obj('toilet'),obj('door','door')],'warnings':[]};before=copy.deepcopy(source)
        result=reconcile(source)
        self.assertEqual(source,before);self.assertEqual(len(result['review_issues']),1)
        self.assertTrue(all(f['location_unresolved'] for f in result['features']))
        self.assertEqual(result,reconcile(result))
    def test_equivalent_labels_dedupe_but_nearby_chairs_do_not(self):
        rows=[obj('washbasin'),obj('wash basin'),obj('chair',box=[.3,.3,.1,.1]),obj('chair',box=[.405,.3,.1,.1])]
        self.assertEqual(len(object_detection.merge_features(rows)),3)
    def test_hierarchical_overlaps_are_not_conflicts(self):
        self.assertFalse(reconcile({'features':[obj('bed'),obj('pillow')],'warnings':[]})['review_issues'])
    def test_source_disagreement_remains_unresolved(self):
        rows=compare_sources([obj('sofa')],[obj('stair','stair')]);result=reconcile({'features':rows})
        self.assertTrue(result['features'][0]['location_unresolved'])
        self.assertEqual(result['review_issues'][0]['type'],'source_disagreement')
    def test_parser_no_silent_24_or_120_limit(self):
        raw={'objects':[{'name':'chair','kind':'furniture','bbox_2d':[i,0,i+1,1]} for i in range(150)]}
        self.assertEqual(len(object_detection.parse_objects(raw,'objects')['features']),150)
    def run_reader(self,root,session,sections=None,settings=None,cancelled=None):
        path=root/'plan.png'
        if not path.exists():Image.new('RGB',(400,400)).save(path)
        with patch('detection_pipeline.requests.Session',return_value=session):
            return object_detection.read(path,path,settings or {},sections or [],lambda *a:None,root/'cache',cancelled)
    def test_every_selected_section_is_processed(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as temp:
            sections=[{'id':str(i),'name':str(i),'bbox':[i*.1,0,.1,.1]} for i in range(5)]
            result=self.run_reader(Path(temp),FakeSession(),sections)
            self.assertEqual(result['coverage']['processed_sections'],['0','1','2','3','4'])
            self.assertTrue(result['coverage_complete']);self.assertFalse(result['geometry_validated'])
    def test_dense_pass_is_subdivided_and_budget_is_explicit(self):
        rows=[{'name':'chair','kind':'furniture','bbox_2d':[i*20,10,i*20+10,20]} for i in range(20)]
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as temp:
            result=self.run_reader(Path(temp),FakeSession(rows),settings={'detection_max_passes':3})
            self.assertFalse(result['coverage_complete']);self.assertGreater(result['coverage']['pending_regions'],0)
            self.assertTrue(any(p['depth']==1 for p in result['passes']))
    def test_resume_reuses_completed_regions_and_cache_invalidates(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as temp:
            root=Path(temp);first=FakeSession();r=self.run_reader(root,first,settings={'detection_max_passes':1})
            self.assertFalse(r['coverage_complete']);second=FakeSession();r=self.run_reader(root,second)
            self.assertTrue(r['coverage_complete']);self.assertEqual(second.calls,1)
            before=detection_pipeline.signature(root/'plan.png',root/'plan.png','m',[])
            with patch('detection_pipeline.VERSION',999):self.assertNotEqual(before,detection_pipeline.signature(root/'plan.png',root/'plan.png','m',[]))
    def test_exhausted_dense_regions_are_not_resumable(self):
        rows=[{'name':'chair','kind':'furniture','bbox_2d':[i*20,10,i*20+10,20]} for i in range(20)]
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as temp:
            result=self.run_reader(Path(temp),FakeSession(rows),settings={'detection_max_passes':128})
            self.assertFalse(result['coverage_complete']);self.assertEqual(result['coverage']['pending_regions'],0)
            self.assertGreater(result['coverage']['saturated_regions'],0);self.assertFalse(result['coverage']['resumable'])
    def test_scope_revision_is_part_of_cache_identity(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as temp:
            path=Path(temp)/'plan.png';Image.new('RGB',(8,8)).save(path)
            self.assertNotEqual(detection_pipeline.signature(path,path,'m',[],{'revision':1}),detection_pipeline.signature(path,path,'m',[],{'revision':2}))
    def test_cancel_retains_completed_passes(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as temp:
            session=FakeSession();r=self.run_reader(Path(temp),session,cancelled=lambda:session.calls>=1)
            self.assertTrue(r['cancelled']);self.assertFalse(r['coverage_complete']);self.assertTrue(list((Path(temp)/'cache').glob('*.json')))
    def test_remote_reader_is_rejected_before_network(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as temp:
            session=FakeSession()
            with self.assertRaises(ValueError):self.run_reader(Path(temp),session,settings={'vision_url':'https://example.com'})
            self.assertEqual(session.calls,0)
if __name__=='__main__':unittest.main()
