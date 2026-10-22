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
 def test_reject_unapproved_host_and_nonquarter(self):
  html='<a href="https://evil.example/q3.pdf">3. kvartal Frende Holding AS 2026</a><a href="/annual.pdf">Årsrapport Frende Holding AS 2026</a>'
  self.assertEqual(candidates('Frende',html),[])
 def test_fremtind_cdn_cannot_claim_period(self):
  html='<a href="https://cdn.sanity.io/files/abc/report.pdf">PDF</a><a href="https://evil.example/report.pdf">PDF</a>'
  rows=candidates('Fremtind',html)
  self.assertEqual(len(rows),1)
  self.assertNotIn('quarter',rows[0])
  self.assertNotIn('year',rows[0])
 def test_partial_failure_never_marks_complete(self):
  def fetch(url):
   if 'frende.no' in url:raise OSError('offline')
   return '<a href="https://cdn.sanity.io/files/abc/report.pdf">PDF</a>'
  result=scan(fetch)
  self.assertFalse(result['complete'])
  self.assertFalse(result['publication_authorized'])
if __name__=='__main__':unittest.main()
