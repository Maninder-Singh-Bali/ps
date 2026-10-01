import copy,json,math,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from plan_area import polygon,box_polygon,proportions,summarize,save_measurement
from store import Store

SQUARE=box_polygon([0,0,1,1])
class GeometryTests(unittest.TestCase):
    def test_percent_only_never_invents_real_units(self):
        r=summarize(SQUARE,[box_polygon([0,0,.25,1])],{'mode':'percent'},1000,500)
        self.assertIsNone(r['area_m2']);self.assertAlmostEqual(r['percentages'][0],25);self.assertAlmostEqual(r['remaining_percent'],75)
    def test_dimensions_and_length_respect_original_aspect(self):
        parts=[box_polygon([0,0,.5,1])]
        dim=summarize(SQUARE,parts,{'mode':'dimensions','width':20,'height':10,'unit':'m'},1000,500)
        line=summarize(SQUARE,parts,{'mode':'line','points':[[0,0],[1,0]],'value':20,'unit':'m'},1000,500)
        self.assertAlmostEqual(dim['area_m2']['total'],200);self.assertAlmostEqual(line['area_m2']['total'],200);self.assertAlmostEqual(line['area_m2']['sections'][0],100)
        vertical=summarize(SQUARE,parts,{'mode':'line','points':[[0,0],[0,1]],'value':10},1000,500)
        self.assertAlmostEqual(vertical['area_m2']['total'],200)
    def test_known_area_and_feet(self):
        r=summarize(SQUARE,[box_polygon([0,0,.25,1])],{'mode':'area','value':1000,'unit':'ft'},473,355)
        self.assertAlmostEqual(r['area_m2']['total'],92.90304);self.assertAlmostEqual(r['area_m2']['sections'][0],23.22576)
    def test_irregular_footprint_is_not_its_bounding_rectangle(self):
        l=[[0,0],[1,0],[1,.5],[.5,.5],[.5,1],[0,1]]
        r=summarize(l,[],{'mode':'dimensions','width':20,'height':10},800,800)
        self.assertAlmostEqual(r['area_m2']['total'],150)
    def test_overlap_and_outside_are_not_double_counted(self):
        r=proportions(SQUARE,[box_polygon([0,0,.75,1]),box_polygon([.25,0,.75,1])])
        self.assertAlmostEqual(r['covered'],1);self.assertAlmostEqual(r['overlap'],.5);self.assertAlmostEqual(r['remaining'],0)
        r=proportions(box_polygon([0,0,.5,1]),[SQUARE]);self.assertAlmostEqual(r['outside'],.5)
    def test_crossing_diagonal_edges(self):
        r=proportions(SQUARE,[[[0,0],[1,0],[0,1]],[[0,0],[1,0],[1,1]]])
        self.assertAlmostEqual(r['covered'],.75);self.assertAlmostEqual(r['overlap'],.25);self.assertAlmostEqual(r['remaining'],.25)
    def test_courtyard_exclusion_and_overlapping_holes(self):
        r=summarize(SQUARE,[SQUARE],{'mode':'area','value':120},473,355,[box_polygon([.25,.25,.5,.5])]*2)
        self.assertAlmostEqual(r['total'],.75);self.assertAlmostEqual(r['area_m2']['total'],120);self.assertAlmostEqual(r['percentages'][0],100)
    def test_bad_polygons_and_measurements(self):
        for p in [[[0,0],[1,1],[1,0],[0,1]],[[0,0],[1,0],[float('nan'),1]],[[0,0],[1,0],[1,0],[0,1]]]:
            with self.assertRaises(ValueError):polygon(p)
        for s in [{'mode':'area','value':0},{'mode':'dimensions','width':2,'height':float('inf')},{'mode':'line','value':4,'points':[[0,0],[0,0]]}]:
            with self.assertRaises(ValueError):summarize(SQUARE,[],s,1000,500)

class PersistenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir=Path(__file__).parent);self.st=Store(self.tmp.name);self.p=self.st.create_project('Test floor');self.pid=self.p['id']
        self.p['floor_plans']=['plan'];self.st.db['assets']['plan']={'id':'plan','project_id':self.pid,'path':str(Path(self.tmp.name)/'plan.png'),'width':1000,'height':500}
        self.room=self.st.add_room(self.pid,'Kitchen','Lower floor','plan',[0,0,.5,1]);self.rid=self.room['id']
    def tearDown(self):self.tmp.cleanup()
    def request(self):return {'floor':'Lower floor','outline':SQUARE,'sections':[{'room_id':self.rid,'polygon':box_polygon([0,0,.5,1])}],'scale':{'mode':'percent'},'map_revision':self.p['map_revision'],'area_revision':self.p.get('area_revision',0)}
    def test_save_reload_and_calibration_only_preserve_image_approval(self):
        self.p['map_confirmed']=True;self.room['approved_image_id']='approved';revision=self.room['revision']
        save_measurement(self.st,self.pid,'plan',self.request());d=self.request();d['scale']={'mode':'dimensions','width':20,'height':10}
        r=save_measurement(self.st,self.pid,'plan',d)
        self.assertFalse(r['map_changed']);self.assertEqual(self.room['revision'],revision);self.assertEqual(self.room['approved_image_id'],'approved')
        loaded=Store(self.tmp.name).project(self.pid);self.assertEqual(loaded['measurements'][0]['scale']['width'],20)
    def test_boundary_change_and_new_section_follow_map_review_gate(self):
        self.p['map_confirmed']=True;d=self.request();d['sections'][0]['polygon']=box_polygon([0,0,.4,1]);d['sections'].append({'name':'Dining','polygon':box_polygon([.4,0,.6,1])})
        r=save_measurement(self.st,self.pid,'plan',d)
        self.assertTrue(r['map_changed']);self.assertFalse(self.p['map_confirmed']);self.assertEqual(len(self.p['rooms']),2);self.assertAlmostEqual(r['summary']['remaining'],0)
    def test_invalid_or_stale_save_has_no_partial_mutation(self):
        d=self.request();d['sections'].append({'name':'Bad room','polygon':[[0,0],[1,1],[1,0],[0,1]]});before=copy.deepcopy(self.st.db)
        with self.assertRaises(ValueError):save_measurement(self.st,self.pid,'plan',d)
        self.assertEqual(self.st.db,before)
        d=self.request();d['map_revision']=-1
        with self.assertRaises(ValueError):save_measurement(self.st,self.pid,'plan',d)
    def test_floor_scales_are_separate(self):
        save_measurement(self.st,self.pid,'plan',self.request())
        room=self.st.add_room(self.pid,'Upper room','Upper floor','plan',[0,0,1,1]);d=self.request();d.update(floor='Upper floor',sections=[{'room_id':room['id'],'polygon':SQUARE}],scale={'mode':'area','value':90})
        save_measurement(self.st,self.pid,'plan',d)
        self.assertEqual(len(self.p['measurements']),2);self.assertEqual(self.p['measurements'][0]['scale']['mode'],'percent')
    def test_multiple_sections_and_floor_ratios(self):
        self.room['bbox']=[0,0,.5,.5]
        d=self.request();d['sections']=[{'room_id':self.rid,'polygon':box_polygon([0,0,.5,.5])}]
        for name,b in [('Living',[.5,0,.5,.5]),('Bedroom',[0,.5,.5,.5]),('Courtyard',[.5,.5,.5,.5])]:
            r=self.st.add_room(self.pid,name,'Lower floor','plan',b);d['sections'].append({'room_id':r['id'],'polygon':box_polygon(b)})
        d.update(map_revision=self.p['map_revision'],scale={'mode':'dimensions','width':20,'height':10})
        result=save_measurement(self.st,self.pid,'plan',d)['summary']
        self.assertEqual(result['percentages'],[25]*4);self.assertEqual(result['area_m2']['sections'],[50]*4);self.assertAlmostEqual(result['remaining_percent'],0)
        d.update(area_revision=self.p['area_revision']);d['sections'][1]['polygon']=box_polygon([.5,0,.25,.5])
        result=save_measurement(self.st,self.pid,'plan',d)['summary'];self.assertAlmostEqual(result['remaining_percent'],12.5);self.assertEqual(result['area_m2']['sections'],[50,25,50,50])

if __name__=='__main__':unittest.main()
