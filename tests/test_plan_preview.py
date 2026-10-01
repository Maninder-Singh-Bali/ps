import sys,tempfile,unittest,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from PIL import Image,ImageDraw
from store import Store
from engine import register_asset
from plan_preview import ensure_preview

class PreviewTest(unittest.TestCase):
    def test_enhancement_preserves_original_and_coordinates_and_reuses_result(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'tests') as temp:
            st=Store(temp);p=st.create_project('QA plan');path=Path(p['storage_path'])/'plan.png'
            im=Image.new('RGB',(473,355),'white');ImageDraw.Draw(im).rectangle((30,30,250,250),outline='black',width=2);im.save(path)
            original=path.read_bytes();asset=register_asset(st,p['id'],path,'plan');result=ensure_preview(st,asset)
            self.assertEqual(path.read_bytes(),original)
            self.assertEqual((result['width'],result['height']),(1892,1420))
            self.assertEqual(result['width']/result['height'],473/355)
            self.assertTrue(result['output_upscaled']);self.assertEqual(ensure_preview(st,asset)['id'],result['id'])
            self.assertTrue(Path(result['path']).is_relative_to(Path(p['storage_path'])))
    def test_large_plan_is_not_needlessly_resized(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'tests') as temp:
            st=Store(temp);p=st.create_project('QA large plan');path=Path(p['storage_path'])/'plan.png'
            Image.new('RGB',(2400,1800),'white').save(path);asset=register_asset(st,p['id'],path,'plan')
            self.assertEqual(ensure_preview(st,asset)['id'],asset['id'])
            self.assertNotIn('clear_preview_id',asset)

if __name__=='__main__':unittest.main()
