import sys,tempfile,unittest
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from perspective_layout import render_faces
from shared_floor import save_projection

class ProjectionControls(unittest.TestCase):
 def test_wider_lens_shows_smaller_projected_object(self):
  with tempfile.TemporaryDirectory(dir=ROOT/'tests') as d:
   plane=np.array([[-1,4,0],[1,4,0],[1,4,2],[-1,4,2]])
   counts=[]
   for fov in (40,90):
    _,ids,_=render_faces([(plane,(100,100,100))],[0,0,1],[0,4,1],Path(d)/'guide.png',owners=[1],return_buffers=True,horizontal_fov=fov)
    counts.append(int((ids==1).sum()))
   self.assertGreater(counts[0],counts[1]*3)
 def test_occluded_object_is_absent_from_visible_target(self):
  with tempfile.TemporaryDirectory(dir=ROOT/'tests') as d:
   back=np.array([[-1,4,0],[1,4,0],[1,4,2],[-1,4,2]])
   front=np.array([[-2,2,0],[2,2,0],[2,2,2],[-2,2,2]])
   _,ids,depth=render_faces([(back,(100,100,100)),(front,(200,200,200))],[0,0,1],[0,4,1],Path(d)/'guide.png',owners=[1,0],return_buffers=True)
   self.assertEqual(int((ids==1).sum()),0)
   rows=save_projection([{'object_key':'room:sofa','label':'Sofa'}],ids,depth,d)
   self.assertIsNone(rows[0]['guide_bbox_xyxy']);self.assertIsNone(rows[0]['output_bbox_xyxy'])
 def test_masks_follow_depth_and_final_crop(self):
  with tempfile.TemporaryDirectory(dir=ROOT/'tests') as d:
   plane=np.array([[-1,4,0],[1,4,0],[1,4,2],[-1,4,2]])
   _,ids,depth=render_faces([(plane,(100,100,100))],[0,0,1],[0,4,1],Path(d)/'guide.png',owners=[1],return_buffers=True)
   row=save_projection([{'object_key':'room:sofa','label':'Sofa'}],ids,depth,d)[0]
   self.assertGreater(row['visible_pixels'],10000);self.assertAlmostEqual(row['median_camera_depth'],4)
   b=row['guide_bbox_xyxy'];self.assertEqual(row['output_bbox_xyxy'],[b[0],b[1]-4,b[2],b[3]-4])
   self.assertTrue((Path(d)/row['mask_file']).exists())

if __name__=='__main__':unittest.main()
