import sys,unittest,tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from extract_report_tables import extract
class ExtractionTests(unittest.TestCase):
 def test_reject_non_pdf(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/"fake.pdf";p.write_bytes(b"<html>bad</html>")
   with self.assertRaises(ValueError):extract(p,"Tryg","https://tryg.com/report.pdf")
 def test_reject_non_https(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/"test.pdf";p.write_bytes(b"%PDF-1.7")
   with self.assertRaises(ValueError):extract(p,"Tryg","http://tryg.com/report.pdf")
if __name__=="__main__":unittest.main()
