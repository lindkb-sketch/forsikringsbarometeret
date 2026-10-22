import sys
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import gjensidige_publish as g

class GjensidigePublisherTests(unittest.TestCase):
    def test_missing_mandatory_pdf_blocks(self):
        with patch.object(g, 'discover_quarter', return_value=None):
            with self.assertRaisesRegex(ValueError, 'Q1'):
                g.prepare({'observations': []}, (1,))
    def test_unrelated_company_remains_unchanged(self):
        baseline = {'observations': []}
        def fake_parse(pages, company, year, quarter, url, sha):
            return [dict(company='Gjensidige',year=year,quarter=quarter,scope='group',
                         source_scope='group',period_type='quarter',metric=metric,value=value,
                         unit='percent' if 'ratio' in metric else 'MNOK',status='reported',
                         source_url=url,source_type='official_quarterly_report',source_page=2)
                    for metric,value in [('insurance_revenue',11004.1),('insurance_service_result',2288.1),
                                         ('combined_ratio',79.2),('expense_ratio',11.7)]]
        with patch.object(g, 'discover_quarter', return_value='https://www.gjensidige.com/Q1-2026-report.pdf'), \
             patch.object(g, 'read_pdf', return_value=[(1,'Gjensidige Interim report 1st quarter 2026')]), \
             patch.object(g, 'parse_group_table', side_effect=fake_parse):
            merged, feed, summary = g.prepare(baseline,(1,),downloader=lambda _:b'%PDF-test')
        self.assertEqual(summary['added'],4)
        self.assertEqual(len(feed['observations']),4)
        self.assertEqual(len(merged['observations']),4)
    def test_reject_wrong_pdf_cover(self):
        with patch.object(g, 'discover_quarter', return_value='https://www.gjensidige.com/Q1-2026-report.pdf'), \
             patch.object(g, 'read_pdf', return_value=[(1,'Gjensidige Interim report Q4 2025')]):
            with self.assertRaisesRegex(ValueError, 'cover'):
                g.prepare({'observations': []},(1,),downloader=lambda _:b'%PDF-test')

if __name__ == '__main__':
    unittest.main()
