import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from gjensidige_report_check import candidates, is_official_pdf, official_report_links

class GjensidigeReportCheckTests(unittest.TestCase):
    def test_accept_official_pdf(self):
        self.assertTrue(is_official_pdf('https://www.gjensidige.com/files/Q3-2026-report.pdf'))
    def test_reject_offdomain(self):
        self.assertFalse(is_official_pdf('https://example.org/Q3-2026-report.pdf'))
    def test_no_unrelated_presentation(self):
        html = '''<a href="/files/Q3-2026-report.pdf">Q3 2026 interim report</a>
<a href="/files/Q3-2026-presentation.pdf">Q3 2026 presentation</a>
<a href="https://evil.example/Q3-2026-report.pdf">Q3 2026 report</a>
<a href="/files/Q2-2026-report.pdf">Q2 2026 report</a>'''
        self.assertEqual(candidates(html), ['https://www.gjensidige.com/files/Q3-2026-report.pdf'])
    def test_official_cision_download_link(self):
        page = '<a href="https://mb.cision.com/Main/123/456/789.pdf">13 July 2026 Interim report Q2 2026 (PDF)</a>'
        self.assertEqual(official_report_links(page, 'https://www.gjensidige.com/investor-relations/', 2, 2026),
                         ['https://mb.cision.com/Main/123/456/789.pdf'])
    def test_reject_nonissuer_download(self):
        page = '<a href="https://example.org/report.pdf">Interim report Q2 2026</a>'
        self.assertEqual(official_report_links(page, 'https://www.gjensidige.com/investor-relations/', 2, 2026), [])
    def test_empty_index_fails_closed(self):
        self.assertEqual(candidates('<html><body>Not published yet</body></html>'), [])

if __name__ == '__main__':
    unittest.main()
