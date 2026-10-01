import sys,unittest,tempfile,hashlib,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PIL import Image,ImageDraw
try:
 import scipy
 import raster_geometry
except ImportError:raster_geometry=None

@unittest.skipUnless(raster_geometry,'Requires installed local SciPy runtime')
class PixelTests(unittest.TestCase):
 def test_wall_evidence_excludes_thin_symbols_and_preserves_gap(self):
  with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as tmp:
   root=Path(tmp);source=root/'plan.png';im=Image.new('RGB',(300,300),'white');d=ImageDraw.Draw(im)
   d.line([(40,30),(40,125)],fill='black',width=9);d.line([(40,155),(40,270)],fill='black',width=9)
   d.rectangle((130,130,190,180),outline='black',width=1);d.arc((110,40,190,120),0,150,fill='black',width=1);d.text((120,220),'Room 01',fill='black')
   im.save(source);before=source.read_bytes();result=raster_geometry.run(source,root/'out')
   mask=Image.open(root/'out/wall-mask.png');self.assertGreater(mask.getpixel((40,70)),0)
   self.assertEqual(mask.getpixel((40,140)),0);self.assertEqual(mask.getpixel((150,130)),0)
   self.assertFalse(result['geometry_validated']);self.assertEqual(source.read_bytes(),before)
   self.assertEqual(result['source_sha256'],hashlib.sha256(before).hexdigest())
 def test_curve_fit_is_not_replaced_by_box(self):
  import math
  points=[[100+70*math.cos(t/30),100+70*math.sin(t/30)] for t in range(45)]
  fit=raster_geometry.fit_path(points)
  self.assertEqual(fit['type'],'arc');self.assertGreater(len(fit['points']),4)
 def test_enhancement_does_not_supply_missing_walls(self):
  with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as tmp:
   root=Path(tmp);original=root/'original.png';enhanced=root/'enhanced.png'
   im=Image.new('RGB',(250,250),'white');ImageDraw.Draw(im).line([(40,30),(40,220)],fill='black',width=9);im.save(original)
   ImageDraw.Draw(im).line([(150,30),(150,220)],fill='black',width=9);im.save(enhanced)
   raster_geometry.run(original,root/'out',enhanced)
   self.assertEqual(Image.open(root/'out/wall-mask.png').getpixel((150,100)),0)
if __name__=='__main__':unittest.main()
