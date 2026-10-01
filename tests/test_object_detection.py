import sys
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import object_detection as detection
import object_knowledge as knowledge
import plan_upscale


class DetectionTests(unittest.TestCase):
    def test_crop_coordinates_are_original_coordinates(self):
        b=detection.map_box([.2,.1,.4,.5],[.45,.45,.55,.55])
        for actual,expected in zip(b,[.56,.505,.22,.275]):self.assertAlmostEqual(actual,expected)

    def test_grounding_corners_convert_and_invalid_boxes_rejected(self):
        rows=detection.parse_objects({'rooms':[{'name':'Bedroom','bbox_2d':[100,200,400,700]},
            {'name':'Invalid','bbox_2d':[900,100,400,700]}, {'name':'Invalid','bbox_2d':[0,0,1100,500]}]},'sections')['features']
        self.assertEqual(len(rows),1);self.assertEqual(rows[0]['bbox'],[.1,.2,.3,.5])
        self.assertEqual(rows[0]['floor'],'');self.assertEqual(rows[0]['review_status'],'pending')

    def test_ambiguous_patterns_and_object_labels_cannot_be_imported_as_rooms(self):
        result={'features':[{'kind':'stair','label':'Stair','evidence':'Repeated parallel lines','confidence':'high'},
            {'kind':'space','label':'Curved screen television','evidence':'Printed label','confidence':'high'}], 'warnings':[]}
        knowledge.quality_flags(result)
        self.assertTrue(all(f['location_unresolved'] for f in result['features']))
        self.assertTrue(all(f['kind']=='unknown' and f['confidence']=='low' for f in result['features']))

    def test_fixture_kind_normalization_preserves_unknown_names(self):
        self.assertEqual(knowledge.normalize_kind('fixture','bathtub'),'furniture')
        self.assertEqual(knowledge.normalize_kind('spaceship','mysterious shape'),'unknown')

    def test_overlap_dedup_preserves_adjacent_objects(self):
        def chair(box):return {'kind':'furniture','object_type':'chair','label':'Chair','bbox':box}
        rows=[chair([.1,.1,.1,.1]),chair([.105,.1,.1,.1]),chair([.22,.1,.1,.1])]
        self.assertEqual(len(detection.merge_features(rows)),2)

    def test_unknowns_and_generic_sofas_do_not_get_guessed_assets(self):
        self.assertIsNone(knowledge.match_asset('sofa'))
        self.assertIsNone(knowledge.match_asset('curved sofa'))
        self.assertIsNone(knowledge.match_asset('industrial centrifuge'))
        self.assertEqual(knowledge.match_asset('coffee_table'),'coffee-table')
        self.assertEqual(knowledge.match_asset('Washbasin'),'basin')
        self.assertGreater(len(knowledge.catalog()),45)

    def test_high_res_plan_keeps_native_pixels_without_runtime(self):
        import tempfile
        from PIL import Image
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder:
            path=Path(folder)/'plan.png';Image.new('RGB',(1800,700)).save(path)
            out,info=plan_upscale.enhance(path,folder,folder)
            self.assertEqual(out,path);self.assertEqual(info['scale'],1)

    def test_corrupt_model_rejected_before_execution(self):
        import tempfile
        from PIL import Image
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder:
            root=Path(folder);path=root/'plan.png';Image.new('RGB',(200,300)).save(path)
            weights=root/'models'/'upscale';weights.mkdir(parents=True)
            (weights/(plan_upscale.MODEL+'.pth')).write_bytes(b'wrong')
            with patch('plan_upscale.subprocess.run') as run:
                with self.assertRaisesRegex(ValueError,'integrity'):plan_upscale.enhance(path,root,root)
                run.assert_not_called()

    def test_empty_or_partial_detection_is_not_verified(self):
        import vision_study
        result=vision_study.check_observations(vision_study.clean_result({'features':[],'uncertainties':[]}),[])
        self.assertFalse(result['accuracy_verified'])

    def test_visual_job_runs_with_renderer_offline_and_preserves_source(self):
        import tempfile
        import copy
        import requests
        from PIL import Image
        from store import Store
        from engine import Engine,register_asset
        import vision_study
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder:
            root=Path(folder).resolve();st=Store(root/'data');p=st.create_project('Detection test')
            source=root/'plan.png';Image.new('RGB',(100,100)).save(source)
            a=register_asset(st,p['id'],source,'plan');p['floor_plans'].append(a['id'])
            a['source_review']={'kind':'plan','reviewed':True,'revision':0,'source_sha256':a['sha256'],'panels':[{'id':'plan','bbox':[0,0,1,1]}]}
            a['plan_reading']={'revision':3,'features':[{'id':'manual-correction'}]}
            before=copy.deepcopy(a['plan_reading']);original=source.read_bytes()
            job=st.new_job(p['id'],'vision_study',plan_id=a['id'],section_ids=[],input_revision=p['map_revision'],study_revision=3)
            engine=Engine(st,root)
            report={'features':[{'id':'chair','kind':'furniture','object_type':'chair','label':'Chair','bbox':[.1,.1,.1,.1]}],'warnings':[]}
            with patch.object(engine,'get',side_effect=requests.ConnectionError),patch('vision_study.ensure_service',return_value={'models':[{'name':vision_study.MODEL}]}),patch('plan_upscale.enhance',side_effect=ValueError('Unavailable')),patch('object_detection.read',return_value=report):
                vision_study.run(engine,job)
            self.assertEqual(source.read_bytes(),original)
            self.assertEqual(a['plan_reading'],before)
            self.assertEqual(job['status'],'completed')
            self.assertTrue(any('Enhancement unavailable' in w for w in a['vision_report']['warnings']))
            self.assertEqual(a['vision_report']['source_scope']['panels'][0]['bbox'],[0,0,1,1])
            engine.session.close()

    def test_jobs_dedupe_per_page_not_per_project(self):
        import tempfile
        from store import Store
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder:
            st=Store(folder);p=st.create_project('Pages')
            one=st.new_job(p['id'],'vision_study',plan_id='page-one')
            two=st.new_job(p['id'],'vision_study',plan_id='page-two')
            again=st.new_job(p['id'],'vision_study',plan_id='page-one')
            self.assertEqual(one['id'],again['id']);self.assertNotEqual(one['id'],two['id'])

if __name__=='__main__':unittest.main()
