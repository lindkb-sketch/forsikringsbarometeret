import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from discover_frende_fremtind import candidates,scan
class OfficialArchiveDiscovery(unittest.TestCase):
 def test_frende_external_publisher_from_official_archive(self):
  html='<a href="https://frende.wrep.it/q3.pdf">3. kvartal Frende Holding AS 2026</a>'
  rows=candidates('Frende',html)
  self.assertEqual([(r['year'],r['quarter']) for r in rows],[(2026,3)])
  self.assertEqual(rows[0]['status'],'requires_pdf_entity_and_period_verification')
 def test_frende_official_filename(self):
  html='<a href="https://www.frende.no/documents/306/Frende_Holding_AS_Kvartalsrapport_Q3_2024.pdf">PDF</a>'
  rows=candidates('Frende',html)
  self.assertEqual([(r['year'],r['quarter']) for r in rows],[(2024,3)])
 def test_reject_unapproved_host_and_nonquarter(self):
  html='<a href="https://evil.example/q3.pdf">3. kvartal Frende Holding AS 2026</a><a href="/annual.pdf">Årsrapport Frende Holding AS 2026</a>'
  self.assertEqual(candidates('Frende',html),[])
 def test_fremtind_cdn_cannot_claim_period(self):
  html='<a href="https://cdn.sanity.io/files/abc/report.pdf">PDF</a><a href="https://evil.example/report.pdf">PDF</a>'
  with self.assertRaises(ValueError):
   candidates('Fremtind',html) # Unscoped PDFs are not trusted
 def test_partial_failure_never_marks_complete(self):
  def fetch(url):
   if 'frende.no' in url:raise OSError('offline')
   return '<a href="https://cdn.sanity.io/files/abc/report.pdf">PDF</a>'
  result=scan(fetch)
  self.assertFalse(result['complete'])
  self.assertFalse(result['publication_authorized'])
class CoverageNeverEquatesDiscoveryWithImport(unittest.TestCase):
 def test_discovered_reports_not_automatically_complete(self):
  import json,tempfile
  from report_coverage import build
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);(root/'data').mkdir()
   (root/'data/financial_observations.json').write_text(json.dumps({'observations':[]}))
   (root/'data/report_sources.json').write_text(json.dumps({'sources':[]}))
   (root/'data/frende_fremtind_candidates.json').write_text(json.dumps({'complete':True,'candidates':[{'company':'Frende'},{'company':'Fremtind'}]}))
   coverage=build(root)
   self.assertFalse(coverage['all_seven_automatic'])
   for company in ('Frende','Fremtind'):
    row=next(x for x in coverage['companies'] if x['company']==company)
    self.assertEqual(row['official_report_candidates'],1)
    self.assertFalse(row['automatic_complete'])
if __name__=='__main__':unittest.main()
