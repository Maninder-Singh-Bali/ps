import copy,tempfile,unittest
from pathlib import Path
from PIL import Image,ImageDraw
import source_panels as source
from engine import register_asset
from store import Store
from raster_reconstruction import elements,correct
from wall_runs import groups

class SourcePanels(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir=Path(__file__).parent);self.root=Path(self.tmp.name)
        self.st=Store(self.root/'data');self.p=self.st.create_project('Synthetic panels')
        im=Image.new('RGB',(600,600),'white');d=ImageDraw.Draw(im)
        d.rectangle((60,60,540,540),outline='black',width=8);d.line((300,60,300,400),fill='black',width=8)
        self.path=self.root/'synthetic.png';im.save(self.path)
        self.a=register_asset(self.st,self.p['id'],self.path,'plan');self.p['floor_plans']=[self.a['id']]
    def tearDown(self):self.tmp.cleanup()
    def test_plan_and_colored_perspective_gate(self):
        self.assertEqual(source.classify(self.path)['kind'],'plan')
        Image.new('RGB',(600,600),(80,120,60)).save(self.path)
        s=source.classify(self.path);self.assertEqual(s['kind'],'perspective_or_photo');self.assertFalse(s['automatic_trace'])
    def test_mixed_sheet_is_not_automatically_traced(self):
        with Image.open(self.path) as im:plan=im.copy().resize((300,300))
        sheet=Image.new('RGB',(600,600),(85,120,70));sheet.paste(Image.new('RGB',(600,300),'white'),(0,300));sheet.paste(plan,(0,300));sheet.paste(plan,(300,300));sheet.save(self.path)
        s=source.classify(self.path);self.assertEqual(s['kind'],'mixed');self.assertTrue(s['panels']);self.assertFalse(s['automatic_trace'])
        self.assertTrue(all(p['bbox'][1]>.45 for p in s['panels']))
    def test_source_change_stale_form_and_undo_preserve_saved_drawing(self):
        source.ensure(self.st,self.p['id'],self.a['id']);self.a['source_review']['reviewed']=True;self.a['drawing']={'features':[{'id':'saved'}]}
        old=copy.deepcopy(self.a['drawing'])
        source.save(self.st,self.p['id'],self.a['id'],dict(revision=0,kind='perspective_or_photo',panels=[],checked=True))
        self.assertFalse(source.valid(self.a));self.assertEqual(old,self.a['drawing'])
        with self.assertRaisesRegex(ValueError,'changed'):source.save(self.st,self.p['id'],self.a['id'],dict(revision=0,action='undo'))
        source.save(self.st,self.p['id'],self.a['id'],dict(revision=1,action='undo'));self.assertTrue(source.valid(self.a))
        with self.assertRaisesRegex(ValueError,'rectangular'):
            source.save(self.st,self.p['id'],self.a['id'],dict(revision=2,kind='plan',panels=[None],checked=True))
        self.a['sha256']='changed';self.assertFalse(source.valid(self.a))
    def test_old_report_cannot_extrude_after_crop_change(self):
        source.ensure(self.st,self.p['id'],self.a['id']);self.a['source_review']['reviewed']=True;self.a['raster_geometry']={'analysis_size':[600,600],'walls':[{'id':'w','width_px':8,'geometry':{'points':[[60,60],[540,60]],'type':'line'}}]}
        self.assertEqual(elements(self.a),[])
        self.a['raster_geometry']['source_scope']=source.digest(self.a['source_review']['panels']);self.assertEqual(len(elements(self.a)),1)
        self.a['source_review']['kind']='perspective_or_photo';self.assertEqual(elements(self.a),[])
    def test_group_review_is_atomic_undoable_and_does_not_bridge_gaps(self):
        self.a['raster_geometry']={'source_sha256':self.a['sha256'],'analysis_size':[600,600],'walls':[
            {'id':k,'width_px':8,'geometry':{'type':'line','points':p}} for k,p in [('a',[[10,10],[50,10]]),('b',[[50,10],[90,10]]),('c',[[110,10],[150,10]])]],'openings':[],'uncertain_spans':[]}
        self.assertEqual(groups(self.a),[['a','b'],['c']])
        args=dict(ids=['a','b'],action='accept',revision=0,source_sha256=self.a['sha256'])
        correct(self.st,self.p['id'],self.a['id'],args)
        self.assertEqual(set(self.a['raster_corrections']),{'a','b'})
        correct(self.st,self.p['id'],self.a['id'],dict(action='undo',revision=1,source_sha256=self.a['sha256']))
        self.assertFalse(self.a['raster_corrections'])
        with self.assertRaises(ValueError):correct(self.st,self.p['id'],self.a['id'],{**args,'ids':['a','missing'],'revision':2})
        self.assertFalse(self.a['raster_corrections'])
