import io
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from ingest_official_pdf import download

class FakeResponse:
    def __enter__(self):return self
    def __exit__(self,*args):return False
    def geturl(self):return "https://issuer.example/report.pdf"
    def read(self,size):return b"%PDF-1.4\nverified bytes"

class SharedPdfCacheTests(unittest.TestCase):
    def test_one_network_request_for_repeated_pdf_in_same_run(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch.dict(os.environ,{"BAROMETER_PDF_RUN_CACHE":folder}):
                with patch("urllib.request.urlopen",return_value=FakeResponse()) as opener:
                    first=download("https://issuer.example/report.pdf")
                    self.assertEqual(download("https://issuer.example/report.pdf"),first)
                    self.assertEqual(opener.call_count,1)
    def test_cache_not_reused_between_runs(self):
        with tempfile.TemporaryDirectory() as parent:
            for run in ("first","second"):
                with patch.dict(os.environ,{"BAROMETER_PDF_RUN_CACHE":str(Path(parent)/run)}):
                    with patch("urllib.request.urlopen",return_value=FakeResponse()) as opener:
                        download("https://issuer.example/report.pdf")
                        self.assertEqual(opener.call_count,1)

if __name__=="__main__":
    unittest.main()
