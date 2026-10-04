import copy,json,os,subprocess,unittest
from pathlib import Path
from chair_orientation import orient_proposals
from furniture_meshes import mesh

class ChairOrientation(unittest.TestCase):
 def setUp(self):
  self.plan={'width':1000,'height':2000}
  self.table={'id':'table','kind':'table','x':.5,'y':.5,'width':.2,'depth':.2,'angle':0}
  self.chairs=[{'id':k,'kind':'chair','x':x,'y':y,'width':.06,'depth':.025,'angle':0} for k,x,y in [('west',.35,.5),('east',.65,.5),('north',.5,.375),('south',.5,.625)]]
 def test_faces_table_and_preserves_footprint_in_both_renderers(self):
  rows=[self.table,*self.chairs];original=copy.deepcopy(rows);actual=orient_proposals(rows,self.plan)
  self.assertEqual([v['angle'] for v in actual[1:]],[270,90,0,180]);self.assertEqual(rows,original)
  for v in actual[1:]:
   back=[p for f in mesh(v,self.plan) if f['part']=='back' for p in f['points']]
   bx=sum(p[0] for p in back)/len(back);by=sum(p[1] for p in back)/len(back)
   self.assertGreater((v['x']-bx)*(.5-v['x'])*1000**2+(v['y']-by)*(.5-v['y'])*2000**2,0)
  js="const m=require('./static/traced-furniture.js');const x=JSON.parse(process.argv[1]);console.log(JSON.stringify(m.orientProposals(x.rows,x.plan)))"
  browser=json.loads(subprocess.check_output([os.environ['PIXELOID_NODE'],'-e',js,json.dumps({'rows':rows,'plan':self.plan})],cwd=Path(__file__).resolve().parents[1]))
  self.assertEqual(browser,actual)
  self.assertAlmostEqual(actual[1]['width']*1000,50);self.assertAlmostEqual(actual[1]['depth']*2000,60)
 def test_ambiguous_distant_and_explicit_rotation_unchanged(self):
  c=self.chairs[0];near={**self.table,'id':'other','x':.2}
  for rows in ([self.table,near,c],[self.table,{**c,'x':.01}],[self.table,{**c,'angle':42}]):
   self.assertEqual(orient_proposals(rows,self.plan),rows)
 def test_proposals_apply_inference(self):
  from furniture_blocks import proposals
  from types import SimpleNamespace
  features=[{'kind':'furniture','object_type':v['kind'],'label':v['id'],'bbox':[v['x']-v['width']/2,v['y']-v['depth']/2,v['width'],v['depth']]} for v in [self.table,*self.chairs]]
  store=SimpleNamespace(asset=lambda _: {**self.plan,'plan_reading':{'features':features}})
  result=proposals(store,{'plan_id':'p','bbox':[0,0,1,1],'floor':'Floor 1'},include_unknown=False)
  self.assertEqual([v['angle'] for v in result[1:]],[270,90,0,180])
