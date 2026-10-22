#!/usr/bin/env python3
"""Historical regression: parse actual official Storebrand Q4 2025 issuer PDF.

Download and parse in a temporary directory; never change published financial data.
"""
import tempfile,unittest,urllib.request,urllib.error,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from import_storebrand_reports import parse_group
URL='https://www.storebrand.no/en/investor-relations/quarterly-reporting/storebrand-asa/2025/_/attachment/inline/a54538ec-e317-4386-adfa-38c2849bcbb2:a00900f3b30486ee15cba89559dbecbf1def35f5/2025-4q-interim-report-storebrand-asa.pdf'
class HistoricalStorebrandQ4(unittest.TestCase):
 def test_official_q4_2025_pdf_golden_values(self):
  req=urllib.request.Request(URL,headers={'User-Agent':'Mozilla/5.0'})
  try:
   with urllib.request.urlopen(req,timeout=65) as response:
    blob=response.read(35_000_001)
  except urllib.error.HTTPError as exc:
   if exc.code in (403, 429):
    self.skipTest(f'Issuer blocks GitHub-hosted runner (HTTP {exc.code}); live PDF regression unavailable')
   raise
  self.assertTrue(blob.startswith(b'%PDF-'))
  self.assertLessEqual(len(blob),35_000_000)
  with tempfile.TemporaryDirectory() as temp:
   file=Path(temp)/'storebrand_q4_2025.pdf'
   file.write_bytes(blob)
   rows=parse_group(file,url=URL,year=2025,quarter=4)
  values={(r['year'],r['quarter'],r['period_type'],r['metric']):r['value'] for r in rows}
  for metric,quarter,full_year in [
   ('insurance_revenue',2565,9705),
   ('loss_ratio',75,75),
   ('expense_ratio',18,18),
   ('combined_ratio',93,92),
   ('return_on_equity',17.4,16.4),
   ('solvency_ratio',194,194)]:
   self.assertEqual(values[(2025,4,'quarter',metric)],quarter)
   self.assertEqual(values[(2025,4,'ytd',metric)],full_year)
  self.assertEqual(values[(2025,3,'quarter','insurance_revenue')],2475)
  self.assertEqual(values[(2025,2,'quarter','insurance_revenue')],2408)
  self.assertEqual(values[(2025,1,'quarter','insurance_revenue')],2256)
  self.assertEqual(values[(2024,4,'quarter','insurance_revenue')],2134)
  self.assertTrue(all(r['source_document_period']=='Q4 2025' and r['source_page']>0 and r['source_sha256'] for r in rows))
if __name__=='__main__':unittest.main()
