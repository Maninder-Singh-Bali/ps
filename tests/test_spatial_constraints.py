import tempfile,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from store import Store
from placement_map import spatial_instructions,room_dimensions,validate_layout,create_guide
from plan_area import box_polygon

class SpatialTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir=Path(__file__).parent);self.st=Store(self.tmp.name);self.p=self.st.create_project('Spatial QA')
        self.st.db['assets']['plan']={'id':'plan','project_id':self.p['id'],'width':1000,'height':500,'path':str(Path(self.tmp.name)/'plan.png')}
        self.p['floor_plans']=['plan'];self.room=self.st.add_room(self.p['id'],'Living','Lower','plan',[0,0,1,1]);self.room['references']=['sofa','table','chair']
        self.refs=[{'id':x,'category':x} for x in self.room['references']]
        self.room['furniture_layout']={'plan_id':'plan','bbox':[0,0,1,1],'items':[{'asset_id':'sofa','x':.18,'y':.5,'angle':90},{'asset_id':'table','x':.47,'y':.51,'angle':0},{'asset_id':'chair','x':.47,'y':.17,'angle':180}],'camera_heading':0}
    def tearDown(self):self.tmp.cleanup()
    def test_saved_visual_positions_become_relational_instructions(self):
        s=spatial_instructions(self.st,self.room,self.refs)
        self.assertIn('overrides the old furniture arrangement',s)
        self.assertIn('Product image 4 (chair) must face toward the camera',s)
        self.assertIn('Product image 3 (table) is closer to the camera, in front of product image 4 (chair)',s)
        self.assertIn('Product image 2 (sofa) is to the left',s)
        self.assertNotIn('room bounding spans',s)
    def test_camera_rotation_changes_interpretation(self):
        self.room['furniture_layout']['camera_heading']=180
        s=spatial_instructions(self.st,self.room,self.refs)
        self.assertIn('Product image 4 (chair) must face away from the camera',s)
        self.assertIn('Product image 2 (sofa) is to the right',s)
    def test_dimensions_are_computed_without_manual_prompt_editing(self):
        self.p['measurements']=[{'plan_id':'plan','floor':'Lower','outline':box_polygon([0,0,1,1]),'scale':{'mode':'dimensions','unit':'m','width':8,'height':6}}]
        d=room_dimensions(self.st,self.room);self.assertEqual(d['width_m'],8)
        s=spatial_instructions(self.st,self.room,self.refs);self.assertIn('8.00 m across plan',s);self.assertIn('1.44 m from',s)
        # Clean map does not require the original raster (or inherit old furniture symbols).
        guide=create_guide(self.st,self.room,self.refs,Path(self.tmp.name));self.assertTrue(guide[0].exists())
    def test_item_sizes_survive_validation_and_old_layouts_keep_working(self):
        d={'revision':self.room['revision'],'items':self.room['furniture_layout']['items']}
        d['items'][0]['size']={'width':2.4,'depth':1.0,'unit':'m'}
        result=validate_layout(self.room,d);self.assertEqual(result['camera_heading'],0);self.assertEqual(result['items'][0]['size']['width'],2.4)
        d['camera_heading']=45
        with self.assertRaises(ValueError):validate_layout(self.room,d)
if __name__=='__main__':unittest.main()
