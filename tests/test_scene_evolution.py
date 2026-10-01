import sys,unittest,copy,json,struct,tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from curve_geometry import segments,floor_faces
from plan_area import area
from scene_document import migrate,rollback,from_plan
from model_export import glb
from drawing_scene import resolve

class SceneEvolution(unittest.TestCase):
    def test_curve_roundtrip_retains_source_id_and_curvature(self):
        doc={'elements':[{'id':'curvedwall','kind':'wall','svg':'<path d="M0 0 C0 100 100 100 100 0" stroke-width="4"/>'}],'edits':{}}
        before=copy.deepcopy(doc);rows,unknown=resolve(json.loads(json.dumps(doc)))
        self.assertFalse(unknown);self.assertGreater(len(rows),8);self.assertEqual(doc,before)
        self.assertTrue(all(r['source_id']=='curvedwall' and r['source_geometry']==doc['elements'][0]['svg'] for r in rows))
        self.assertGreater(max(v[1] for r in rows for v in r['points']),70)
    def test_arc_and_relative_quadratic_preserved(self):
        self.assertGreater(len(segments('M0 0 A50 50 0 0 1 100 0')),5)
        self.assertGreater(len(segments('M0 0 q50 100 100 0')),5)
    def test_concave_floor_with_polygonal_void_has_correct_area(self):
        outline=[[0,0],[1,0],[1,.5],[.5,.5],[.5,1],[0,1]]
        hole=[[.1,.1],[.3,.1],[.2,.3]]
        faces=floor_faces(outline,[hole]);self.assertAlmostEqual(sum(area(f) for f in faces),area(outline)-area(hole))
    def test_self_intersecting_floor_rejected(self):
        with self.assertRaises(ValueError):floor_faces([[0,0],[1,1],[0,1],[1,0]])
    def test_saved_fixture_migration_is_additive_idempotent_and_reversible(self):
        plan={'id':'plan1','sha256':'source','drawing':{'revision':4,'features':[{'id':'wall1','kind':'wall','points':[[0,0],[3,4]]}]},
              'plan_reading':{'features':[{'id':'manual1','kind':'furniture','review_status':'confirmed','notes':'Keep my correction','bbox':[.1,.1,.2,.2]}]},'custom_field':{'preserve':True}}
        before=copy.deepcopy(plan);m=migrate(plan)
        self.assertEqual(plan,before);self.assertEqual(migrate(m),m);self.assertEqual(rollback(m),before)
        self.assertEqual(m['scene_document']['elements'][0]['id'],'manual1')
    def test_glb_valid_envelope_and_stable_object_identity(self):
        scene={'surfaces':[{'points':[[0,0,0],[1,0,0],[1,1,0],[0,1,0]],'color':[100,100,100],'kind':'floor','source_id':'floor1'}],
               'geometry_hash':'hash','plan_id':'p','floor':'Ground','calibrated':False,'limits':['Estimated scale'],'unresolved_architecture':[]}
        data=glb(scene);magic,version,length=struct.unpack('<4sII',data[:12]);self.assertEqual((magic,version,length),(b'glTF',2,len(data)))
        size=struct.unpack('<I',data[12:16])[0];doc=json.loads(data[20:20+size]);self.assertEqual(doc['nodes'][0]['extras']['stable_element_id'],'floor1')
        self.assertFalse(doc['extras']['scale_measured'])
    def test_dxf_block_identity_is_retained(self):
        import ezdxf
        from native_source import dxf_manifest
        doc=ezdxf.new();b=doc.blocks.new('chair');b.add_circle((0,0),1);insert=doc.modelspace().add_blockref('chair',(3,5),dxfattribs={'rotation':30})
        result=dxf_manifest(doc,list(doc.modelspace()))
        self.assertEqual(result['entities'][0]['id'],insert.dxf.handle);self.assertIn('chair',result['blocks'])
        self.assertEqual(result['entities'][0]['attributes']['rotation'],30)
    def test_scene_export_carries_native_curves_furniture_and_uncertain_lighting(self):
        wall={'source_id':'base7','native_source_id':'nativeA3','kind':'wall','points':[[0,0],[10,10]],'source_geometry':'<path/>','thickness':2}
        room={'id':'r1','floor':'Ground','block_layout':{'items':[{'id':'chair1','kind':'chair','preset_id':'chair','x':.2,'y':.3,'angle':30,'width':.1,'depth':.1}]}}
        data=from_plan({'id':'p'},[room],[wall])
        self.assertEqual([r['id'] for r in data['elements']],['base7','r1:chair1'])
        self.assertEqual(data['elements'][0]['source']['native_entity_id'],'nativeA3')
        self.assertEqual(data['elements'][1]['orientation_degrees'],30)
        self.assertEqual(data['lighting_status'],'Lighting evidence not established')
    def test_scene_is_plan_scoped_and_design_light_is_not_an_observation(self):
        rooms=[{'id':'r1','plan_id':'p','block_layout':{'items':[{'id':'lamp','preset_id':'floor-lamp'}]}},
               {'id':'r2','plan_id':'other','block_layout':{'items':[{'id':'chair'}]}}]
        scene=from_plan({'id':'p','vision_report':{'coverage_complete':True}},rooms)
        self.assertEqual([e['id'] for e in scene['elements']],['r1:lamp'])
        self.assertEqual(scene['elements'][0]['lighting_origin'],'user_design')
        self.assertEqual(scene['observations'],[])
        self.assertIn('No lighting detected',scene['lighting_status'])

if __name__=='__main__':unittest.main()
