import sys,tempfile,unittest,xml.etree.ElementTree as ET
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import numpy as np
from PIL import Image,ImageDraw
from plan_vector import trace_plan,thin_ink

class VectorTest(unittest.TestCase):
    def test_trace_is_scalable_linework_not_embedded_bitmap(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'tests') as temp:
            source=Path(temp)/'source.png';target=Path(temp)/'trace.svg'
            im=Image.new('RGB',(240,160),'white');d=ImageDraw.Draw(im)
            d.rectangle((20,20,210,140),outline='black',width=3);d.line((120,20,120,70),fill='black',width=3);d.line((120,100,120,140),fill='black',width=3);im.save(source)
            trace_plan(source,target);svg=ET.parse(target).getroot()
            self.assertEqual(svg.attrib['viewBox'],'0 0 240 160')
            paths=svg.findall('{http://www.w3.org/2000/svg}path')
            self.assertTrue(paths);self.assertTrue(all(p.attrib['fill']=='none' and p.attrib['d'] for p in paths))
            self.assertFalse(svg.findall('.//{http://www.w3.org/2000/svg}image'))
    def test_thinning_keeps_an_open_door_gap(self):
        mask=np.zeros((100,100),bool);mask[10:40,45:49]=True;mask[65:90,45:49]=True
        result=thin_ink(mask)
        self.assertFalse(result[40:65].any());self.assertTrue(result[10:40].any());self.assertTrue(result[65:90].any())

if __name__=='__main__':unittest.main()
