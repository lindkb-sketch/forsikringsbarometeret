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
        def fake_parse(pages, year, quarter, url, sha):
            return [dict(company='Gjensidige',year=year,quarter=quarter,scope='group',
                         source_scope='group',period_type='quarter',metric=metric,value=value,
                         unit='percent' if 'ratio' in metric else 'MNOK',status='reported',
                         source_url=url,source_type='official_quarterly_report',source_page=2)
                    for metric,value in [('insurance_revenue',11004.1),('insurance_service_result',2288.1),
                                         ('combined_ratio',79.2),('expense_ratio',11.7),('loss_ratio',67.5)]]
        with patch.object(g, 'discover_quarter', return_value='https://www.gjensidige.com/Q1-2026-report.pdf'), \
             patch.object(g, 'read_pdf', return_value=[(1,'Gjensidige Interim report 1st quarter 2026')]), \
             patch.object(g, 'parse_group_table', side_effect=fake_parse):
            merged, feed, summary = g.prepare(baseline,(1,),downloader=lambda _:b'%PDF-test')
        self.assertEqual(summary['added'],5)
        self.assertEqual(len(feed['observations']),5)
        self.assertEqual(len(merged['observations']),5)
    def test_prior_year_comparatives_do_not_override_current_year_reference(self):
        values={
            2026:{'insurance_revenue':11004.1,'insurance_service_result':2288.1,
                  'combined_ratio':79.2,'expense_ratio':11.7,'loss_ratio':67.5},
            2025:{'insurance_revenue':9993.9,'insurance_service_result':1313.6,
                  'combined_ratio':86.9,'expense_ratio':12.0,'loss_ratio':74.9},
        }
        def fake_parse(pages,year,quarter,url,sha):
            return [dict(company='Gjensidige',year=y,quarter=1,scope='group',
                         period_type='quarter',metric=m,value=v,
                         unit='percent' if 'ratio' in m else 'MNOK',status='reported',
                         source_type='official_quarterly_report',source_url=url,source_page=4)
                    for y,metrics in values.items() for m,v in metrics.items()]
        with patch.object(g,'discover_quarter',return_value='https://mb.cision.com/Public/1122/q1-2026.pdf'), \
             patch.object(g,'read_pdf',return_value=[(1,'Gjensidige interim report 1st quarter 2026')]), \
             patch.object(g,'parse_group_table',side_effect=fake_parse):
            merged,feed,summary=g.prepare({'observations':[]},(1,),downloader=lambda _:b'%PDF-test')
        self.assertEqual(summary['added'],10)
        self.assertEqual(len(merged['observations']),10)
        self.assertEqual(len(feed['observations']),10)

    def test_reject_wrong_pdf_cover(self):
        with patch.object(g, 'discover_quarter', return_value='https://www.gjensidige.com/Q1-2026-report.pdf'), \
             patch.object(g, 'read_pdf', return_value=[(1,'Gjensidige Interim report Q4 2025')]):
            with self.assertRaisesRegex(ValueError, 'cover'):
                g.prepare({'observations': []},(1,),downloader=lambda _:b'%PDF-test')

if __name__ == '__main__':
    unittest.main()
