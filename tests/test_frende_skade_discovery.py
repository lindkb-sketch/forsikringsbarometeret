import unittest
from scripts.discover_frende_skade_reports import build, discover, ARCHIVE, EXCHANGE, discover_exchange_pdfs

class FrendeSkadeDiscovery(unittest.TestCase):
    def test_discovers_new_2027_quarter_without_hardcoding(self):
        html='<a href="/documents/next.pdf">1. kvartal Frende Skadeforsikring AS 2027</a>'
        reports=build(html)['reports']
        self.assertIn((2027,1), {(x['year'],x['quarter']) for x in reports})
        self.assertEqual(next(x['source_url'] for x in reports if x['year']==2027), 'https://www.frende.no/documents/next.pdf')
    def test_2026_q1_q2_q3_present(self):
        data=build('')
        self.assertTrue({(2026,1),(2026,2),(2026,3)} <= {(r['year'],r['quarter']) for r in data['reports']})
    def test_spreadsheet_and_untrusted_links_rejected(self):
        html='<a href="https://evil.example/x.pdf">1. kvartal Frende Skadeforsikring AS 2027</a><a href="/file.xlsx">2. kvartal Frende Skadeforsikring AS 2027</a>'
        self.assertFalse(discover(html))
    def test_existing_pdf_provenance_is_preserved(self):
        url='https://live.euronext.com/sites/default/files/company_press_releases/attachments_oslo/2026/10/28/skade.pdf'
        previous={'reports':[{'year':2026,'quarter':3,'source_url':ARCHIVE,'pdf_url':url}]}
        result=build('',previous)
        self.assertEqual(next(x for x in result['reports'] if x['year']==2026 and x['quarter']==3)['pdf_url'],url)
    def test_future_q4_pdf_discovered_without_hardcoding(self):
        filename='/sites/default/files/company_press_releases/attachments_oslo/2027/02/20/Frende_Skadeforsikring_Q4_2026.pdf'
        listing='<a data-node-nid="123">Frende Forsikring 4. kvartal 2026</a>'
        page='<a download href="'+filename+'">Frende Skadeforsikring AS Q4 PDF</a>'
        found=discover_exchange_pdfs(fetch=lambda url: listing if url==EXCHANGE else page)
        self.assertEqual(found[(2026,4)],'https://live.euronext.com'+filename)
    def test_previous_reports_retained_on_issuer_archive_lag(self):
        old={'reports':[{'year':2027,'quarter':1,'source_url':ARCHIVE}]}
        self.assertIn((2027,1),{(r['year'],r['quarter']) for r in build('',old)['reports']})
if __name__=='__main__':unittest.main()
