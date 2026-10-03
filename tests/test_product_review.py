import json, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
from product_review import projector, plane_inverse, confirmed_dimensions

class ProductReviewTests(unittest.TestCase):
    def test_projection_matches_renderer_and_four_row_crop(self):
        p=projector({'position':[0,0,1],'target':[0,4,1],'horizontal_fov':90})
        self.assertEqual(p([0,4,1]),[960,540])
        self.assertAlmostEqual(p([1,4,1])[0],720)
        self.assertAlmostEqual(p([0,4,2])[1],300)
        with self.assertRaises(ValueError):p([0,-1,1])
    def test_oblique_artwork_recovers_physical_aspect_not_screen_ratio(self):
        p=projector({'position':[0,0,1.5],'target':[0,4,1.2],'horizontal_fov':80})
        axis=np.array([.6,.8,0]);c=np.array([1,4,1.2]);w,h=.3,.4
        corners=[p(c+axis*x+[0,0,z]) for x,z in [(-w/2,h),(w/2,h),(w/2,0),(-w/2,0)]]
        inv=np.array(plane_inverse(corners,[[0,0],[w,0],[w,h],[0,h]]))
        recovered=[]
        for q in corners:
            v=inv@[*q,1];recovered.append(v[:2]/v[2])
        np.testing.assert_allclose(recovered,[[0,0],[w,0],[w,h],[0,h]],atol=1e-10)
        self.assertGreater(abs(np.linalg.norm(np.array(corners[1])-corners[0])/np.linalg.norm(np.array(corners[3])-corners[0])-.75),.1)
    def test_horizontal_rim_plane_recovers_known_diameter_only(self):
        p=projector({'position':[0,0,1.5],'target':[0,4,1.2],'horizontal_fov':90});r=.18
        metric=[[-r,-r],[r,-r],[r,r],[-r,r]]
        inv=np.array(plane_inverse([p([x,y+4,2.15]) for x,y in metric],metric))
        pts=[]
        for x in (-r,r):
            v=inv@[*p([x,4,2.15]),1];pts.append(v[:2]/v[2])
        self.assertAlmostEqual(np.linalg.norm(pts[1]-pts[0]),.36)
    def test_degenerate_plane_rejected(self):
        with self.assertRaises(ValueError):plane_inverse([[0,0],[1,0],[2,0],[3,0]],[[0,0],[1,0],[1,1],[0,1]])
    def test_only_explicit_hash_bound_fields_are_confirmed(self):
        with tempfile.TemporaryDirectory() as folder:
            class Snapshot:root=Path(folder)
            item={'asset_id':'ref','physical_size':{'width':.36},'height_m':.25,'dimension_status':'estimated'}
            self.assertEqual(confirmed_dimensions(Snapshot(),item)[0],{})
            path=Path(folder)/'product-review-facts.json'
            path.write_text(json.dumps({'references':{'ref':{'sha256':'known','dimensions':{'diameter_m':.36},'source':'User supplied'}}}))
            with patch('scene_control.file_identity',return_value={'sha256':'known'}):
                self.assertEqual(confirmed_dimensions(Snapshot(),item)[0],{'diameter_m':.36})
            with patch('scene_control.file_identity',return_value={'sha256':'changed'}):
                with self.assertRaises(ValueError):confirmed_dimensions(Snapshot(),item)
if __name__=='__main__':unittest.main()
