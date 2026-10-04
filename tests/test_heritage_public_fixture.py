"""Public inspection payload checks; no private Store or worker access."""
import json,re,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class HeritagePublicFixture(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.raw=(ROOT/'staging-preview/fixtures/heritage-courtyard.json').read_text();cls.pack=json.loads(cls.raw);cls.doc=cls.pack['docs']['heritage-floor-1'];cls.project=cls.pack['state']['projects']['synthetic-ui']
 def test_complete_geometry_and_hosts(self):
  fs=self.doc['features'];walls={f['id'] for f in fs if f['kind']=='wall'};openings=[f for f in fs if f['kind'] in ('door','window','sliding_door')]
  self.assertEqual(len(walls),54);self.assertEqual(len(openings),26);self.assertTrue(all(f['host_wall_id'] in walls for f in openings))
  rooms=self.project['rooms'];self.assertEqual(len(rooms),32);self.assertEqual(sum(len(r['block_layout']['items']) for r in rooms),64)
  design=self.doc['surface_design'];hosts={s['id'] for s in design['surfaces']};self.assertEqual(len(design['items']),59);self.assertTrue(all(o['surface_id'] in hosts for o in design['items']))
  roomids={r['id'] for r in rooms};self.assertTrue(all(s.get('room_id') in roomids for s in design['surfaces'] if s.get('room_id')))
 def test_no_private_media_paths_or_connections(self):
  for token in ('/Users/','/private/','127.0.0.1','192.168.','data:image','base64','remote.local','api_key','access_token','BEGIN PRIVATE KEY'):self.assertNotIn(token,self.raw)
  self.assertEqual(set(self.pack['state']['assets']),{'plan-1'});self.assertEqual(self.pack['state']['jobs'],{})
  for r in self.project['rooms']:
   self.assertEqual(r['references'],[]);self.assertEqual(r['images'],[]);self.assertEqual(r['videos'],[]);self.assertFalse(r['view_approvals'])
  self.assertFalse(self.project['map_confirmed']);self.assertEqual(self.project['generation_phase']['status'],'paused')
 def test_metric_scale_and_saved_camera(self):
  self.assertEqual(self.doc['calibration']['metres_per_pixel'],.032);self.assertEqual(self.doc['wall_height_m'],3)
  r=next(r for r in self.project['rooms'] if r['id']=='room-1');c=r['camera_views']['view-1']['camera'];self.assertEqual(c['height'],1.5);self.assertEqual(c['horizontal_fov'],60)
  scene=self.pack['scenes']['heritage-floor-1'];self.assertTrue(scene['static_fixture']);self.assertGreater(len(scene['surfaces']),6000)
if __name__=='__main__':unittest.main()
