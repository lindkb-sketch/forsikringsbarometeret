import unittest,sys
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import ingest_official_pdf

class IssuerSpecificPdfIngestionTests(unittest.TestCase):
 def test_non_gjensidige_pdf_is_not_downloaded_by_unsupported_parser(self):
  import json,tempfile
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);(root/'data').mkdir()
   (root/'data/report_sources.json').write_text(json.dumps({'sources':[{'company':'Storebrand','document_url':'https://example.org/blocked.pdf','year':2026,'quarter':2}]}))
   (root/'data/financial_observations.json').write_text(json.dumps({'observations':[]}))
   with patch.object(ingest_official_pdf,'ROOT',root),patch.object(ingest_official_pdf,'audit',return_value={'ok':True,'errors':[]}):
    result=ingest_official_pdf.run(fetch=lambda url: (_ for _ in ()).throw(AssertionError('Unsupported issuer downloaded')))
   self.assertEqual(result['added'],0)
   self.assertEqual(result['sources'][0]['status'],'handled_by_dedicated_importer')
if __name__=='__main__':unittest.main()
