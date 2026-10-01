import sys,json,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from flux_layout_prompt import compile_prompt
from plan_reading import instruction

class OpenSpaces(unittest.TestCase):
 def test_open_connection_reaches_both_views_without_inventing_partition(self):
  f={'id':'open1','kind':'space','label':'Living to kitchen','notes':'Continuous open wing','bbox':[.1,.4,.2,.02],'floor':'Lower','room_id':'living','connection_room_id':'kitchen','review_status':'confirmed','shape':'unspecified'}
  plan={'plan_reading':{'features':[f]}}
  for key in ('living','kitchen'):
   room={'id':key,'name':key,'floor':'Lower','bbox':[0,0,1,1]}
   prompt,_=compile_prompt({},room,[],plan)
   item=json.loads(prompt)['architecture'][0]
   self.assertEqual(item['shared_feature_id'],'open1')
   self.assertIn('no dividing wall',item['constraint'])
   self.assertIn('no dividing wall',instruction(plan,room))
  prompt,_=compile_prompt({}, {'id':'other','name':'Other','floor':'Lower'},[],plan)
  self.assertEqual(json.loads(prompt)['architecture'],[])
if __name__=='__main__':unittest.main()
