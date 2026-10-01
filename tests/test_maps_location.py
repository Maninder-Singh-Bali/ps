import sys,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from maps_location import extract,resolve,allowed

class MapsLocation(unittest.TestCase):
 def test_place_pin_has_priority_over_camera_centre(self):
  r=extract('https://www.google.com/maps/place/Test/@20,70,17z/data=!3d28.5!4d77.2')
  self.assertEqual((r['latitude'],r['longitude'],r['source']),(28.5,77.2,'place_pin'))
 def test_camera_centre_is_not_mislabelled_as_pin(self):
  r=extract('https://www.google.com/maps/@20,70,17z');self.assertEqual(r['source'],'map_centre');self.assertTrue(r['warning'])
 def test_query_and_markdown(self):
  r=resolve('[map](https://www.google.com/maps?q=-33.8%2C151.2)');self.assertEqual(r['latitude'],-33.8)
 def test_unsupported_destinations_and_routes_rejected(self):
  for url in ['http://www.google.com/maps?q=1,2','https://evil.com/maps?q=1,2','https://www.google.com.evil.com/maps?q=1,2','https://www.google.com/maps/dir/a/b/@1,2,3z']:
   with self.assertRaises(ValueError):extract(url)
 def test_ambiguous_and_invalid_coordinates(self):
  for url in ['https://www.google.com/maps/data=!3d1!4d2!3d3!4d4','https://www.google.com/maps?q=91,2']:
   with self.assertRaises(ValueError):extract(url)
 def test_plain_place_without_coordinates_is_unresolved(self):
  self.assertIsNone(extract('https://www.google.com/maps/place/Delhi'))
 def test_unsafe_short_redirect_is_rejected(self):
  from urllib.parse import urlsplit
  class Response:
   status=302
   def getheader(self,key):return 'https://127.0.0.1/maps?q=1,2'
  class Connection:
   def __init__(self,*args):pass
   def request(self,*args,**kw):pass
   def getresponse(self):return Response()
   def close(self):pass
  with patch('maps_location.public_target',return_value=(urlsplit('https://maps.app.goo.gl/test'),'maps.app.goo.gl',443,'8.8.8.8')),patch('maps_location.PinnedHTTPS',Connection):
   with self.assertRaises(ValueError):resolve('https://maps.app.goo.gl/test')

if __name__=='__main__':unittest.main()
