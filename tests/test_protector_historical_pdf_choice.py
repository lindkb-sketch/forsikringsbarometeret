import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from protector_publish import discover_pdf
P='https://storage.mfn.se/34613cd2-9b91-47d8-bae6-1c5274fa1298/interim-report-q3-2025-prot.pdf'
B='https://storage.mfn.se/other-q3-2025.pdf'
def fetch(*args):
 return ('<a href="'+P+'">Q3 2025 report</a><a href="'+B+'">Q3 2025 report</a>').encode()
class TestProtectorArchive(unittest.TestCase):
 def test_duplicate_pdf_discovery_selects_issuer_verified_q3(self):
  self.assertEqual(discover_pdf(2025,3,fetch=fetch),P)
if __name__=='__main__':unittest.main()
