import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image
from store import Store
from engine import register_asset
import raster_reconstruction as raster
import raster_validation as validation
from raster_identity import identified, correction_for
import shared_floor


class GeometryReview(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir=Path(__file__).parent);self.root=Path(self.tmp.name)
        self.st=Store(self.root/'data');self.p=self.st.create_project('Synthetic lifecycle')
        image=self.root/'source.png';Image.new('RGB',(100,100),'white').save(image)
        self.a=register_asset(self.st,self.p['id'],image,'plan');self.p['floor_plans']=[self.a['id']]
        self.r=self.st.add_room(self.p['id'],'Open living','Ground',self.a['id'],[.1,.1,.8,.8])
        self.r['area_polygon']=[[.1,.1],[.9,.1],[.9,.9],[.1,.9]]
        self.p['measurements']=[{'plan_id':self.a['id'],'floor':'Ground','outline':[[.1,.1],[.9,.1],[.9,.9],[.1,.9]],'exclusions':[]}]
        self.a['drawing']={'features':[],'edits':{},'revision':0}
        self.a['raster_geometry']={'source_sha256':self.a['sha256'],'analysis_size':[100,100],
            'walls':[{'id':'w1','geometry':{'type':'line','points':[[10,10],[10,40]]},'width_px':4},
                     {'id':'w2','geometry':{'type':'line','points':[[10,60],[10,90]]},'width_px':4}],
            'openings':[{'id':'opening0','points':[[10,40],[10,60]],'wall_ids':['w1','w2']}],'uncertain_spans':[]}
    def tearDown(self):self.tmp.cleanup()
    def edit(self,key,action='accept',**kw):
        return raster.correct(self.st,self.p['id'],self.a['id'],dict(id=key,action=action,revision=self.a.get('raster_revision',0),source_sha256=self.a['sha256'],**kw))
    def review_all(self):
        self.edit('w1');self.edit('w2');self.edit('opening0',kind='door')
    def state(self):return validation.status(self.st,self.p['id'],self.a['id'])
    def complete(self,**kw):
        return validation.save(self.st,self.p['id'],self.a['id'],{'fingerprint':self.state()['fingerprint'],'source_checked':True,'estimates_acknowledged':True,**kw})
    def test_completion_requires_review_and_explicit_source_check(self):
        with self.assertRaisesRegex(ValueError,'Review'):self.complete()
        self.review_all();self.assertTrue(self.state()['can_complete'])
        with self.assertRaisesRegex(ValueError,'original'):self.complete(source_checked=False)
        self.assertTrue(self.complete()['geometry_validated'])
        reloaded=Store(self.st.root)
        self.assertTrue(validation.status(reloaded,self.p['id'],self.a['id'])['geometry_validated'])
        self.assertFalse(any('Raster geometry' in s for s in shared_floor.readiness(self.st,self.r)))
    def test_defer_and_edit_require_further_review(self):
        self.review_all();self.edit('w1','defer');self.assertFalse(self.state()['can_complete'])
        self.edit('w1','edit',points=[[11,10],[11,40]]);self.assertFalse(self.state()['can_complete'])
        self.edit('w1');self.assertTrue(self.state()['can_complete'])
    def test_source_drawing_floor_or_semantic_change_revokes_validation(self):
        for mutate in (lambda a,p:a.update(sha256='new-source'),lambda a,p:a['drawing'].update(revision=9),
                       lambda a,p:p['measurements'][0]['outline'].__setitem__(0,[.05,.1]),
                       lambda a,p:a.update(plan_reading={'revision':2,'features':[]})):
            self.review_all();self.complete();before=copy.deepcopy(self.a);project=copy.deepcopy(self.p)
            mutate(self.a,self.p);self.assertFalse(self.state()['geometry_validated'])
            self.a.clear();self.a.update(before);self.p.clear();self.p.update(project)
    def test_undo_cannot_restore_old_approval(self):
        self.review_all();self.complete();self.edit('w1','edit',points=[[11,10],[11,40]])
        self.edit('w1','undo');self.assertFalse(self.state()['geometry_validated']);self.assertTrue(self.state()['can_complete'])
    def test_stale_form_and_failed_save_do_not_approve(self):
        self.review_all();token=self.state()['fingerprint'];self.edit('w1')
        with self.assertRaisesRegex(ValueError,'changed'):self.complete(fingerprint=token)
        before=copy.deepcopy(self.a)
        with patch.object(self.st,'save',side_effect=OSError('disk full')):
            with self.assertRaises(OSError):self.complete()
        self.assertEqual(before,self.a)
    def test_room_box_cannot_substitute_for_floor_outline(self):
        self.review_all();self.p['measurements']=[]
        self.assertIn('outline',[v['code'] for v in self.state()['issues']])
    def test_detached_opening_and_zero_length_path_block_completion(self):
        self.review_all();self.edit('opening0','edit',kind='door',points=[[70,40],[70,60]]);self.edit('opening0',kind='door')
        self.assertIn('opening-host',[v['code'] for v in self.state()['issues']])
        self.edit('opening0','reject');self.edit('w1','edit',points=[[10,10],[10,10]]);self.edit('w1')
        self.assertIn('unresolved',[v['code'] for v in self.state()['issues']])
    def test_open_transition_is_not_a_wall_and_door_cuts_are_buildable(self):
        self.review_all();scene=raster.draft(self.st,self.p['id'],self.a['id'])
        self.assertTrue(any(s['kind']=='door' for s in scene['surfaces']))
        self.edit('opening0',kind='open_transition');self.assertTrue(self.state()['can_complete'])
        self.assertEqual([v['kind'] for v in raster.elements(self.a)],['wall','wall'])
    def test_index_reuse_cannot_transfer_door_to_different_location(self):
        self.review_all();result=copy.deepcopy(self.a['raster_geometry']);result['openings'][0]['points']=[[70,70],[90,70]]
        raster.apply_report(self.a,result)
        key=self.a['raster_geometry']['openings'][0]['id']
        self.assertEqual(correction_for(self.a,key),{});self.assertTrue(self.a['raster_orphaned_corrections'])
        self.assertFalse(any(v['kind']=='door' for v in raster.elements(self.a)))
        self.assertEqual(self.a['raster_undo'],[])
    def test_stable_identity_survives_reorder_and_reversed_path(self):
        self.review_all();before=identified(self.a['raster_geometry'])
        result=copy.deepcopy(self.a['raster_geometry']);result['walls'].reverse();result['openings'][0]['id']='opening9';result['openings'][0]['points'].reverse()
        raster.apply_report(self.a,result)
        self.assertEqual(before['openings'][0]['id'],self.a['raster_geometry']['openings'][0]['id'])
        self.assertEqual(correction_for(self.a,before['openings'][0]['id'])['kind'],'door');self.assertFalse(self.a['raster_orphaned_corrections'])
    def test_source_or_analysis_size_change_never_transfers_corrections(self):
        self.review_all()
        for changes in ({'source_sha256':'other'},{'analysis_size':[200,200]}):
            candidate={**copy.deepcopy(self.a['raster_geometry']),**changes}
            from raster_identity import reconcile
            kept,orphaned=reconcile(self.a,identified(candidate));self.assertEqual(kept,{});self.assertEqual(len(orphaned),3)
    def test_direct_report_mutation_cannot_reuse_bound_correction(self):
        self.review_all();self.a['raster_geometry']['openings'][0]['points']=[[70,70],[90,70]]
        self.assertEqual(correction_for(self.a,'opening0'),{})
        self.assertFalse(any(e['kind']=='door' for e in raster.elements(self.a)))
    def test_legacy_indexed_correction_is_only_migrated_against_same_old_evidence(self):
        self.a['raster_corrections']={'opening0':{'action':'accept','kind':'door'}}
        self.assertEqual(correction_for(self.a,'opening0'),{})
        raster.apply_report(self.a,copy.deepcopy(self.a['raster_geometry']))
        self.assertEqual(next(iter(self.a['raster_corrections'].values()))['kind'],'door')
    def test_duplicate_candidates_do_not_merge_conflicting_corrections(self):
        self.review_all();self.a['raster_geometry']['openings'].append({**copy.deepcopy(self.a['raster_geometry']['openings'][0]),'id':'duplicate'})
        self.edit('duplicate',kind='window');raster.apply_report(self.a,self.a['raster_geometry'])
        self.assertEqual(len(self.a['raster_orphaned_corrections']),2)
    def test_section_boxes_and_overlapping_sections_are_not_validated(self):
        self.review_all();self.r.pop('area_polygon')
        self.assertFalse(self.state()['can_complete'])
        self.r['area_polygon']=[[.1,.1],[.9,.1],[.9,.9],[.1,.9]]
        self.p['rooms'].append({**copy.deepcopy(self.r),'id':'overlap'})
        self.assertIn('overlap',' '.join(i['message'] for i in self.state()['issues']))
    def test_curved_observation_requires_its_specific_curve(self):
        from drawing_scene import resolve
        from curve_review import bind
        self.a['plan_reading']={'features':[{'id':'curve-observation','kind':'curved_wall','floor':'Ground','bbox':[.1,.1,.8,.8],'review_status':'confirmed'}]}
        matching,_=resolve({'elements':[{'id':'curve','kind':'wall','svg':'<path d="M10 10 A80 80 0 0 1 90 90"/>'}]})
        self.assertEqual(shared_floor.unresolved_curves(self.a,matching),['curve-observation'])
        bind(self.a,matching,'curve-observation','curve')
        self.assertEqual(shared_floor.unresolved_curves(self.a,matching),[])
        for rows in ([{'source_id':'straight','kind':'wall','points':[[10,10],[70,70]]}],
                     [{**v,'points':[[p[0]+100,p[1]+100] for p in v['points']]} for v in matching]):
            self.assertEqual(shared_floor.unresolved_curves(self.a,rows),['curve-observation'])
        self.a['plan_reading']['features'][0]['review_status']='pending'
        self.assertEqual(shared_floor.unresolved_curves(self.a,matching),['curve-observation'])

    def test_L_polyline_and_unrelated_curve_cannot_resolve_observation(self):
        from curve_review import bind
        self.a['plan_reading']={'features':[{'id':'curve','kind':'curved_wall','floor':'Ground','bbox':[.1,.1,.8,.8],'review_status':'confirmed'}]}
        rows=[{'source_id':'L-wall','kind':'wall','points':p} for p in ([[10,10],[90,10]],[[90,10],[90,90]])]
        self.assertEqual(shared_floor.unresolved_curves(self.a,rows),['curve'])
        with self.assertRaises(ValueError):bind(self.a,rows,'curve','L-wall')
        from drawing_scene import resolve
        real,_=resolve({'elements':[{'id':'real','kind':'wall','svg':'<path d="M10 10 A80 80 0 0 1 90 90"/>'}]})
        bind(self.a,real,'curve','real')
        self.assertEqual(shared_floor.unresolved_curves(self.a,real),[])
        unrelated=[{**r,'source_id':'other'} for r in real]
        self.assertEqual(shared_floor.unresolved_curves(self.a,unrelated),['curve'])
        altered=[{**r,'points':[[p[0]+1,p[1]] for p in r['points']]} for r in real]
        self.assertEqual(shared_floor.unresolved_curves(self.a,altered),['curve'])

if __name__=='__main__':unittest.main()
