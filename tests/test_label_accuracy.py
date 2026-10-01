import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from analysis import label

class LabelAccuracy(unittest.TestCase):
    def test_unreliable_ocr_is_not_a_room(self):
        for text in ('Ertonce','Wat','er,.chon','Cw. ec','Reswa t'):
            self.assertIsNone(label(text),text)
    def test_exact_aliases_and_small_typos(self):
        for text,expected in [('Restaurant','Dining'),('Entrance Gate','Foyer'),('WC','WC'),('Laundry area','Laundry'),('Living room','Living Room'),('Bedrom','Bedroom')]:
            self.assertEqual(label(text)[0],expected)

if __name__=='__main__':unittest.main()
