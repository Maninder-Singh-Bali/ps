"""Compare browser-only 2D envelopes with the production resolver on synthetic cases."""
import copy,json,math,os,subprocess,unittest
from pathlib import Path
from shapely import Polygon,unary_union
import wall_junctions as J
ROOT=Path(__file__).resolve().parents[1]
def wall(key,a,b,t=20):return dict(id=key,kind='wall',points=[a,b],thickness=t)
def shape(r):return unary_union([Polygon(p['outer'],p['holes']) for p in r['rings']])
class StagingJunctions(unittest.TestCase):
 def test_envelope_parity_after_edits(self):
  cases=[]
  for angle in [3,15,35,90,135,179]:
   end=[200*math.cos(math.radians(angle)),200*math.sin(math.radians(angle))]
   for width in [10,20,40]:cases.append([wall('a',[0,0],[200,0]),wall('b',[0,0],end,width)])
  cases += [[wall('a',[-100,0],[100,0]),wall('b',[0,0],[0,100],40)],
   [wall('a',[-100,0],[100,0]),wall('b',[0,-100],[0,100],40)],
   [wall('a',[0,0],[100,0]),wall('b',[101,0],[200,0])],
   [wall('a',[0,0],[100,0]),wall('b',[100,0],[200,0])],
   [wall('a',[0,0],[100,0]),wall('b',[0,0],[200,0],40)],
   [wall('a',[0,0],[400,0]),wall('b',[0,0],[0,100]),dict(id='window',kind='window',host_wall_id='a',offset=120,width=90,points=[[120,0],[210,0]],thickness=10)]]
  shell=[wall('a',[0,0],[400,0]),wall('b',[400,0],[400,300]),wall('c',[400,300],[0,300]),wall('d',[0,300],[0,0])];cases.append(shell)
  # Metadata-only merge must retain the exact boundary, openings and voids.
  merged=copy.deepcopy(shell)
  for w in merged:w['wall_chain_id']='merged';w['review_note']='Synthetic merge'
  cases.append(merged)
  # Both bundled floors include intersections, openings and a rounded corner.
  fixtures=ROOT/'verification/https-staging-ui-20261004/site/app'
  for name in ['ui-fixtures.json','multi-room-fixtures.json']:
   for doc in json.loads((fixtures/name).read_text())['docs'].values():cases.append(doc['features'])
  node=os.environ.get('PIXELOID_NODE','node')
  js="const J=require('./staging-preview/joined-footprints.js');const cases=JSON.parse(require('fs').readFileSync(0,'utf8'));process.stdout.write(JSON.stringify(cases.map(fs=>{let before=JSON.stringify(fs),r=J.resolve(fs);if(JSON.stringify(fs)!==before)throw Error('mutated');return r})))"
  results=json.loads(subprocess.check_output([node,'-e',js],cwd=ROOT,input=json.dumps(cases).encode()))
  for i,(fs,result) in enumerate(zip(cases,results)):
   with self.subTest(case=i):
    expected=shape(J.resolve(fs));actual=shape(result)
    self.assertTrue(actual.is_valid)
    self.assertLess(expected.symmetric_difference(actual).area,1e-5)
  self.assertEqual(results[24]['rings'],results[25]['rings'])
  print(f'{len(cases)} synthetic envelopes matched the production 2D resolver; source features unchanged')
if __name__=='__main__':unittest.main()
