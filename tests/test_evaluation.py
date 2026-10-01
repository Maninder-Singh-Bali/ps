import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from evaluation import evaluate

class Evaluation(unittest.TestCase):
    def test_known_false_positives_and_misses_are_counted(self):
        chair={'label':'chair','kind':'furniture','bbox':[0,0,.1,.1]}
        toilet={'label':'toilet','kind':'furniture','bbox':[.5,.5,.1,.1]}
        prediction={'source_sha256':'synthetic','features':[chair,{**chair,'bbox':[.2,0,.1,.1]}]}
        truth={'reviewed':True,'reviewer':'synthetic unit fixture','source_sha256':'synthetic','features':[chair,toilet]}
        result=evaluate(prediction,truth)
        self.assertEqual(result['per_category']['chair']['precision'],.5)
        self.assertEqual(result['per_category']['toilet']['recall'],0)
        self.assertIsNone(result['per_category']['toilet']['precision'])
        self.assertEqual(result['mean_matched_bbox_iou'],1)
        self.assertIsNone(result['wall_boundary_error'])
    def test_unreviewed_and_other_source_annotations_are_rejected(self):
        with self.assertRaises(ValueError):evaluate({}, {'reviewed':False})
        with self.assertRaises(ValueError):evaluate({'source_sha256':'a'}, {'source_sha256':'b','reviewed':True,'reviewer':'person'})

if __name__=='__main__':unittest.main()
