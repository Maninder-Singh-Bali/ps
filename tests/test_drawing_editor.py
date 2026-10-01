import sys,tempfile,unittest,copy
from pathlib import Path
from datetime import datetime
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from drawing_editor import get_document,save_document,export_svg,clean_changes,sanitized,combine_wall_edges
from scene_sun import clean_site,solar_summary,position,lighting_instruction
from store import Store
from xml.etree import ElementTree as ET
from unittest.mock import patch
from PIL import Image

class SolarTests(unittest.TestCase):
    def site(self,**kw):return clean_site(dict(latitude=0,longitude=0,north_confirmed=True,north_angle=0,date='2026-03-20',time='12:00',utc_offset=0,sun_enabled=True,**kw))
    def test_equator_equinox_and_compass(self):
        s=self.site();r=solar_summary(s)
        self.assertGreater(r['elevation'],87)
        self.assertTrue(r['sunrise']['time'].startswith('06:'));self.assertTrue(r['sunset']['time'].startswith('18:'))
        self.assertAlmostEqual(r['sunrise']['azimuth'],90,delta=1);self.assertAlmostEqual(r['sunset']['azimuth'],270,delta=1)
        s['north_angle']=90;new=solar_summary(s);self.assertAlmostEqual(new['plan_angle'],(r['azimuth']+90)%360)
    def test_utc_offsets_same_instant(self):
        a=self.site();b={**a,'timezone':'Asia/Kolkata','utc_offset':5.5};x=position(a,datetime(2026,3,20,6));y=position(b,datetime(2026,3,20,11,30));self.assertAlmostEqual(x['azimuth'],y['azimuth']);self.assertAlmostEqual(x['elevation'],y['elevation'])
    def test_polar_and_invalid_data(self):
        s={**self.site(),'latitude':80,'date':'2026-06-21'};r=solar_summary(s);self.assertIsNone(r['sunrise']);self.assertIsNone(r['sunset']);self.assertTrue(r['daylight'])
        for v in [{'latitude':91},{'latitude':0,'longitude':float('nan')},{'sun_enabled':True},{'date':'2026-02-30'}]:
            with self.assertRaises(ValueError):clean_site(v)
    def test_lighting_is_opt_in_and_night_has_no_direct_sun(self):
        self.assertEqual(lighting_instruction({}),('',None));s={**self.site(),'time':'00:00'};text,meta=lighting_instruction({'drawing':{'site':s}});self.assertIn('No direct sunlight',text);self.assertFalse(meta['solar']['daylight'])

class DrawingTests(unittest.TestCase):
    def test_double_boundaries_form_one_wall_without_bridging_openings(self):
        elements=[{'id':'base1','kind':'wall','svg':'<path class="wall" d="M8 22 H212"/>'},{'id':'base2','kind':'wall','svg':'<path class="wall" d="M8 24 H212"/>'},{'id':'base3','kind':'wall','svg':'<path class="wall" d="M220 22 H240"/>'}]
        paired=combine_wall_edges(copy.deepcopy(elements),{},473,355)
        self.assertEqual(paired[1]['absorbed_by'],'base1');self.assertNotIn('absorbed_by',paired[2]);self.assertIn('height="2.0"',paired[0]['svg'])
        svg=export_svg({'width':473,'height':355,'elements':paired},{},[])
        self.assertEqual(svg.count('<rect class="wall"'),1);self.assertNotIn('M8 24 H212',svg)
        corrected=combine_wall_edges(copy.deepcopy(elements),{'base2':{'dy':10}},473,355)
        self.assertNotIn('absorbed_by',corrected[1])
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir=Path(__file__).parent);self.st=Store(self.tmp.name);self.p=self.st.create_project('Drawing QA');self.pid=self.p['id'];self.root=Path(self.tmp.name)
        svg=self.root/'base.svg';svg.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100"><path class="wall" d="M10 10 H90"/><g transform="translate(30 30)"><path class="opening" d="M0 0 V10"/></g><script>alert(1)</script><image href="https://bad.invalid/a"/><text x="20" y="20">5</text></svg>')
        self.st.db['assets'].update(plan={'id':'plan','project_id':self.pid,'width':100,'height':100,'path':str(self.root/'plan.png'),'cad_redraw_id':'base'},base={'id':'base','project_id':self.pid,'path':str(svg)})
        self.p['floor_plans']=['plan'];self.r=self.st.add_room(self.pid,'Living','Lower','plan',[0,0,1,1]);self.p['map_confirmed']=True
    def tearDown(self):self.tmp.cleanup()
    def req(self):
        doc=get_document(self.st,self.pid,'plan');return dict(revision=doc['revision'],map_revision=doc['map_revision'],edits={'base0':{'dy':5}},features=[{'id':'new1','kind':'window','points':[[10,20],[30,20]]}],site={'north_confirmed':True,'north_angle':90,'latitude':0,'longitude':0,'date':'2026-03-20','time':'08:00','utc_offset':0,'sun_enabled':True})
    def fake_raster(self,source,dest):Image.new('RGB',(240,240),'white').save(dest)
    def test_sanitized_import_and_reject_foreign_element(self):
        doc=get_document(self.st,self.pid,'plan');self.assertEqual(len(doc['elements']),3);self.assertNotIn('script',str(doc));self.assertNotIn('https',str(doc))
        with self.assertRaises(ValueError):clean_changes(doc,{'edits':{'other':{}}})
        for f in [{'id':'new1','kind':'door','points':[[0,0],[float('nan'),1]]},{'id':'new1','kind':'line','points':[[0,0],[0,0]]}]:
            with self.assertRaises(ValueError):clean_changes(doc,{'features':[f]})
    def test_versioned_save_reopen_review_gate_and_original_preserved(self):
        before=Path(self.st.asset('base')['path']).read_bytes();req=self.req();self.r['approved_image_id']='x'
        with patch('drawing_editor.rasterize',self.fake_raster):result=save_document(self.st,self.pid,'plan',req)
        self.assertTrue(result['map_changed']);self.assertFalse(self.p['map_confirmed']);self.assertIsNone(self.r['approved_image_id']);self.assertEqual(before,Path(self.st.asset('base')['path']).read_bytes())
        reopened=get_document(Store(self.tmp.name),self.pid,'plan');self.assertEqual(reopened['revision'],1);self.assertEqual(reopened['base_asset_id'],'base');self.assertEqual(reopened['features'][0]['kind'],'window');self.assertEqual(reopened['site']['north_angle'],90)
        self.assertTrue(self.st.asset(self.st.asset('plan')['drawing']['guidance_asset_id'])['path'].endswith('.png'))
        arch=Path(self.st.asset(self.st.asset('plan')['drawing']['guidance_asset_id'])['path']).with_suffix('.svg').read_text();self.assertNotIn('<text',arch)
        with self.assertRaises(ValueError):save_document(self.st,self.pid,'plan',req)
    def test_running_generation_and_export_failure_are_atomic(self):
        req=self.req();j=self.st.new_job(self.pid,'image',self.r['id'])
        with self.assertRaises(ValueError):save_document(self.st,self.pid,'plan',req)
        self.st.update_job(j['id'],status='completed');original=copy.deepcopy(self.st.db)
        with patch('drawing_editor.rasterize',side_effect=ValueError('export failed')):
            with self.assertRaises(ValueError):save_document(self.st,self.pid,'plan',req)
        self.assertEqual(original,self.st.db)
    def test_real_vector_export_to_guidance_png(self):
        from drawing_editor import rasterize
        doc=get_document(self.st,self.pid,'plan');svg=self.root/'test.svg';svg.write_text(export_svg(doc,{},[]));png=self.root/'test.png';rasterize(svg,png)
        with Image.open(png) as im:self.assertEqual(im.size,(2400,2400));self.assertLess(min(im.convert('L').getextrema()),100)
    def test_raster_only_plan_does_not_duplicate_new_elements_on_reopen(self):
        self.st.asset('plan').pop('cad_redraw_id');req=self.req();req['edits']={}
        with patch('drawing_editor.rasterize',self.fake_raster):save_document(self.st,self.pid,'plan',req)
        reopened=get_document(self.st,self.pid,'plan');self.assertEqual(reopened['elements'],[]);self.assertEqual(len(reopened['features']),1)

if __name__=='__main__':unittest.main()
