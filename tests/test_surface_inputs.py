"""CPU-only input preparation. All uploads are captured locally; no submit path."""
import base64,copy,hashlib,io,json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PIL import Image
import plan_drafts,shared_floor,scene_control,surface_inputs
from engine import Engine
ROOT=Path(__file__).resolve().parents[1]

def fixture():
    buf=io.BytesIO();Image.new('RGB',(24,32),'red').save(buf,'PNG')
    reference={'image':'data:image/png;base64,'+base64.b64encode(buf.getvalue()).decode(),'dimension_status':'assumed','product_url':'https://example.invalid/example','preview_only':True}
    features=[{'id':k,'kind':'wall','points':p,'thickness':15,'height_m':3} for k,p in [('n',[[0,0],[500,0]]),('e',[[500,0],[500,400]]),('s',[[500,400],[0,400]]),('w',[[0,400],[0,0]])]]
    d={'id':'test','name':'Test','width':600,'height':500,'features':features,'wall_height_m':3,'calibration':{'points':[[0,0],[100,0]],'metres':1},'surface_design':{'version':1,'surfaces':[{'id':'wall','kind':'wall','wall_id':'n','side':1},{'id':'ceil','kind':'ceiling','elevation_m':3,'boundary':[[0,0],[500,0],[500,400],[0,400]]},{'id':'floor','kind':'floor','boundary':[[0,0],[500,0],[500,400],[0,400]],'finish':{'kind':'paint','color':'#aaaabb','reference':reference}}],'items':[]}}
    for kind,sid,x,y in [('painting','wall',2.5,1.5),('pendant','ceil',2.5,1.5),('rug','floor',2.5,1)]:
        d['surface_design']['items'].append({'id':kind,'kind':kind,'surface_id':sid,'x':x,'y':y,'width':.6,'height':.8,'depth':.05,'drop':.4 if kind=='pendant' else 0,'reference':reference})
    camera={'position':[.42,.7],'target':[.42,0],'height':1.4,'target_height':1.0,'horizontal_fov':80}
    return d,camera

class SurfaceInputTests(unittest.TestCase):
 def setUp(self):
    self.tmp=tempfile.TemporaryDirectory();self.out=Path(self.tmp.name);self.d,self.camera=fixture()
    self.st,self.r,_=plan_drafts.scene_store(self.d,self.camera);self.plan=self.st.asset('test');self.p=self.st.project('draft')
    path=self.out/'plan.png';Image.new('RGB',(600,500),'white').save(path);self.plan['path']=str(path)
    self.r.update(revision=1,references=[],images=[],notes='');self.p.update(seed=42,style='Natural',map_confirmed=True)
 def tearDown(self):self.tmp.cleanup()
 def test_shared_preview_and_guide(self):
    scene=shared_floor.build(self.st,self.r);self.assertTrue(shared_floor.applies(self.st,self.r));self.assertEqual(len([p for p in scene['products'] if p.get('surface_design')]),3)
    self.assertEqual(plan_drafts.preview(self.d)['surfaces'],scene['surfaces'])
    path,info=shared_floor.create_guide(self.st,self.r,[],self.out)
    self.assertTrue(path.exists());self.assertEqual(info['geometry_hash'],scene['geometry_hash'])
    visible={p['id'] for p in info['projected_objects'] if p['visible_pixels']}
    self.plan['floor_cameras']['preview']['target_height']=2.2
    _,upper=shared_floor.create_guide(self.st,self.r,[],self.out)
    visible|={p['id'] for p in upper['projected_objects'] if p['visible_pixels']}
    self.assertEqual(visible,{'painting','pendant','rug'})
    self.assertEqual(len(info['surface_design_inputs']['references']),4)
 def test_staleness_all_semantics_not_visibility_or_edit_settings(self):
    snap=scene_control.scene_snapshot(self.st,self.p,self.r)
    for mutate in [lambda d:d['items'][0].update(width=.7),lambda d:d['items'][0].update(x=2.4),lambda d:d['items'][1].update(drop=.6),lambda d:d['surfaces'][2]['finish'].update(color='#abcdef'),lambda d:d['items'][0]['reference'].update(product_url='https://example.invalid/changed')]:
        saved=copy.deepcopy(self.plan['drawing']['surface_design']);mutate(self.plan['drawing']['surface_design'])
        with self.assertRaisesRegex(ValueError,'master scene'):scene_control.assert_scene(self.st,self.p,self.r,snap)
        self.plan['drawing']['surface_design']=saved
    self.plan['drawing']['surface_design'].update(hidden_categories=['pendant','wall'],show_ceiling=True)
    self.r['scene_control']={'mode':'region','instruction':'different edit'}
    scene_control.assert_scene(self.st,self.p,self.r,snap)
    self.assertEqual(len(shared_floor.build(self.st,self.r)['products']),3)
 def test_reference_bytes_identity(self):
    info,refs=surface_inputs.prepare(self.plan,self.r,self.out)
    for ref in refs:self.assertEqual(hashlib.sha256(Path(ref['path']).read_bytes()).hexdigest(),ref['sha256'])
    snap=scene_control.scene_snapshot(self.st,self.p,self.r);buf=io.BytesIO();Image.new('RGB',(24,32),'blue').save(buf,'PNG')
    self.plan['drawing']['surface_design']['items'][0]['reference']['image']='data:image/png;base64,'+base64.b64encode(buf.getvalue()).decode()
    with self.assertRaises(ValueError):scene_control.assert_scene(self.st,self.p,self.r,snap)
 def test_missing_host_and_floor_guard(self):
    self.plan['drawing']['surface_design']['surfaces'][0]['wall_id']='missing'
    self.assertTrue(shared_floor.build(self.st,self.r)['surface_design_issues'])
    with self.assertRaisesRegex(ValueError,'missing wall host'):shared_floor.create_guide(self.st,self.r,[],self.out)
    self.plan['drawing'].pop('surface_design_floor')
    with self.assertRaisesRegex(ValueError,'floor assignment'):surface_inputs.prepare(self.plan,self.r,self.out)
 def test_actual_engine_graph_without_upload_or_submit(self):
    self.st.room=lambda pid,rid:self.r
    engine=Engine(self.st,ROOT);uploads=[]
    engine.upload=lambda path:uploads.append(Path(path)) or Path(path).name
    job={'id':'offline','project_id':'draft','room_id':'preview','input_revision':1,'scene_ticket':scene_control.scene_snapshot(self.st,self.p,self.r)}
    # Admission/registration only are stubbed: no active DB, phase or inference.
    with patch('engine.assert_image_gate'),patch('engine.register_asset',return_value={'id':'fixture-guide'}):
        graph,_=engine.build_image(job,self.out)
    self.assertEqual(uploads[0].name,'shared_floor_reference.png')
    self.assertIn('SURFACE DESIGN',graph['6']['inputs']['text'])
    self.assertEqual(len(job['scene_manifest']['surface_reference_conditioning']),4)
    self.assertEqual(job['scene_manifest']['surface_design_inputs']['design']['items'][0]['width'],.6)
    self.assertTrue(any(p.name=='furniture_product_board.png' for p in uploads))
    self.assertTrue((self.out/'scene-manifest.json').exists())

if __name__=='__main__':unittest.main()
