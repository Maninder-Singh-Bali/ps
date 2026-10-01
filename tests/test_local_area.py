import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import local_area
class LocalAreaTests(unittest.TestCase):
    def test_indian_city_located_offline(self):
        area=local_area.nearest(26.9124,75.7873)
        self.assertEqual(area['country_code'],'IN');self.assertEqual(area['city'],'Jaipur');self.assertLess(area['distance_km'],10);self.assertFalse(area['coordinates_shared']);self.assertFalse(area['delivery_verified'])
    def test_worldwide_and_invalid_coordinates(self):
        self.assertEqual(local_area.nearest(51.5074,-.1278)['country_code'],'GB')
        with self.assertRaises(ValueError):local_area.nearest(float('nan'),0)
        with self.assertRaises(ValueError):local_area.nearest(99,0)
