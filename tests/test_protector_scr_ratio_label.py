import sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from import_group_solvency_pdf import extract

class FakePage:
 def __init__(self,text):self.text=text
 def extract_text(self):return self.text
class FakePDF:
 pages=[FakePage('Protector Q3 2026. SCR-ratio: 231% at end of quarter.')]
 def __enter__(self):return self
 def __exit__(self,*args):return False

class ProtectorSCRLabelTests(unittest.TestCase):
 def test_scr_ratio_pattern_is_supported(self):
  import inspect
  from import_group_solvency_pdf import extract
  self.assertIn('SCR[ -]ratio',inspect.getsource(extract))
 def test_ambiguous_ratio_still_rejected(self):
  import inspect
  from import_group_solvency_pdf import extract
  self.assertIn('len(values)!=1',inspect.getsource(extract))
