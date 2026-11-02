import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from stage_official_pdfs import collect
class PDFStagingTests(unittest.TestCase):
 def test_pdf_hash(self):
  r=collect({"sources":[{"company":"Tryg","year":2026,"quarter":2,"document_type":"official_quarterly_report","document_url":"https://tryg.com/official.pdf"}]},lambda url:b"%PDF-1.7\nbody")
  self.assertEqual(len(r["sources"][0]["sha256"]),64)
 def test_reject_html(self):
  with self.assertRaises(ValueError):collect({"sources":[{"company":"Tryg","year":2026,"quarter":2,"document_type":"official_quarterly_report","document_url":"https://tryg.com/official.pdf"}]},lambda url:b"<html>")
