import json
import sys
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from render_progress import initialize,event_fields,sampling_plan

class ProgressTest(unittest.TestCase):
    def setUp(self):
        self.g=json.loads((ROOT/'templates/flux.json').read_text(encoding='utf8'))
        self.j={'id':'test','status':'running','prompt_id':'ours','kind':'image'}
        self.j.update(initialize(self.j,self.g))
    def event(self,kind,at=100,**data):
        fields=event_fields(self.j,{'type':kind,'data':{'prompt_id':'ours',**data}},self.g,at)
        self.j.update(fields);return fields
    def test_templates_steps(self):
        self.assertEqual(sampling_plan(self.g)['21']['total'],4)
        v=json.loads((ROOT/'templates/ltx.json').read_text(encoding='utf8'))
        self.assertEqual(sampling_plan(v)['19']['total'],8)
    def test_step_eta_and_hold_during_decode(self):
        self.event('executing',node='21')
        self.event('progress',110,node='21',value=1,max=4)
        self.assertEqual(self.j['progress'],25);self.assertIsNone(self.j['eta'])
        self.event('progress',114,node='21',value=2,max=4)
        self.assertEqual(self.j['progress'],50);self.assertEqual(self.j['eta']['seconds'],8)
        self.assertEqual(self.j['eta']['scope'],'sampling')
        self.assertFalse(self.event('progress',119,node='21',value=1,max=4))
        self.assertEqual(self.j['progress'],50)
        self.event('progress',122,node='21',value=4,max=4)
        self.event('executing',123,node='22')
        self.event('progress',124,node='22',value=1,max=9)
        self.assertEqual(self.j['progress'],100);self.assertIn('Decoding',self.j['stage'])
        self.assertEqual(self.j['render_tracking']['sampling_finished_at'],122)
    def test_cached_and_other_prompt(self):
        self.assertFalse(event_fields(self.j,{'type':'progress','data':{'prompt_id':'someone-else','node':'21','value':3,'max':4}},self.g,1))
        self.event('execution_cached',nodes=['21'])
        self.assertEqual(self.j['progress'],100)
        self.event('executing',node='22')
        self.assertEqual(self.j['progress'],100)
    def test_full_eta_uses_only_matching_successful_history(self):
        history={**self.j,'status':'completed','finished':120,'render_tracking':{**self.j['render_tracking'],'sampling_finished_at':110}}
        self.j.update(initialize(self.j,self.g,[history]))
        self.event('progress',210,node='21',value=1,max=4)
        self.event('progress',214,node='21',value=2,max=4)
        self.assertEqual(self.j['eta']['seconds'],18);self.assertEqual(self.j['eta']['scope'],'total')
        self.event('progress',222,node='21',value=4,max=4)
        self.event('executing',224,node='22')
        self.assertEqual(self.j['eta']['seconds'],8)
        other=json.loads(json.dumps(self.g));other['20']['inputs']['width']=1280
        self.assertIsNone(initialize(self.j,other,[history])['render_tracking']['tail_estimate'])
    def test_missed_steps_no_fabricated_progress_or_eta(self):
        self.event('executing',node='21')
        self.event('executing',node='22')
        self.assertEqual(self.j['progress'],0);self.assertIsNone(self.j['eta'])
    def test_terminal_and_invalid_events(self):
        self.assertFalse(self.event('progress',node='21',value='bad',max=4))
        self.assertFalse(self.event('progress',node='21',value=1,max=100))
        self.j['status']='cancelled'
        self.assertFalse(self.event('progress',node='21',value=4,max=4))
    def test_multiple_samplers_accumulate(self):
        self.g['26']=self.g['21'];self.j.update(initialize(self.j,self.g))
        self.event('progress',node='21',value=4,max=4)
        self.assertEqual(self.j['progress'],50)
        self.event('executing',node='26')
        self.assertEqual(self.j['progress'],50)
        self.event('progress',node='26',value=2,max=4)
        self.assertEqual(self.j['progress'],75)

if __name__=='__main__':unittest.main()
