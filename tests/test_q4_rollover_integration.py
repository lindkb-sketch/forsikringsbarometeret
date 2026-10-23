"""Offline Q4 2026 rollover and report-discovery safety contracts.

Synthetic observations are only in memory; they must never be written to
published financial feeds.
"""
import sys
import unittest
from datetime import date
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from build_editorial import build
from e2e_seven_insurers import publication_state,current_report_candidates
from discover_reports import discover

def observation(company,year,quarter,metric,value):
    return {'company':company,'year':year,'quarter':quarter,'metric':metric,
            'value':value,'unit':'MNOK' if metric=='insurance_revenue' else '%',
            'status':'reported','scope':'group','period_type':'quarter',
            'source_url':'https://example.org/official-quarterly-report.pdf',
            'source_page':'1','source_sha256':'simulated-only'}

class Q4RolloverContracts(unittest.TestCase):
    def test_q4_first_verified_report_advances_editorial_without_faking_other_insurers(self):
        rows=[observation('Gjensidige',2026,3,'insurance_revenue',100),
              observation('Gjensidige',2026,3,'combined_ratio',85),
              observation('Gjensidige',2026,4,'insurance_revenue',110),
              observation('Gjensidige',2026,4,'combined_ratio',82)]
        result=build({'observations':rows,'coverage_complete':False},{'items':[]})
        self.assertEqual(result['period'],'Q4 2026')
        self.assertIn('Q3 2026',result['periods'])
        self.assertTrue(any('Gjensidige' in x['companies'] for x in result['brief']))
        self.assertEqual(result['coverage'],'partial')

    def test_year_rollover_requires_verified_next_year_observation(self):
        rows=[observation('Tryg',2026,4,'insurance_revenue',100),
              observation('Tryg',2027,1,'insurance_revenue',105)]
        result=build({'observations':rows},{'items':[]})
        self.assertEqual(result['period'],'Q1 2027')
        self.assertIn('Q4 2026',result['periods'])

    def test_calendar_is_not_evidence_of_financial_results(self):
        calendar={'Sampo / If':{'events':[{'period':'Q4 2026','date':'2027-02-10'}]},
                  'Frende':{'events':[]}}
        self.assertEqual(publication_state('Sampo',date(2027,1,15),calendar,[],2026,4)[0],
                         'awaiting_publication')
        self.assertEqual(publication_state('Frende',date(2027,1,15),calendar,[],2026,4)[0],
                         'publication_unconfirmed')

    def test_explicit_q4_discovery_does_not_match_q3(self):
        page='<a href="/q4-2026-interim-report.pdf">Interim report Q4 2026</a>'
        found=discover(page,'https://issuer.example/reports','Sampo')
        self.assertEqual(len(found),1)
        self.assertEqual(len(current_report_candidates([],found,2026,4)),1)
        self.assertEqual(current_report_candidates([],found,2026,3),[])

    def test_every_insurer_remains_in_import_pipeline(self):
        pipeline=(ROOT/'scripts/run_pipeline.py').read_text(encoding='utf-8')
        for importer in ('ingest_official_pdf.py','import_tryg.py',
                         'import_fremtind_holding.py','import_frende_holding.py',
                         'import_gjensidige_latest.py'):
            with self.subTest(importer=importer):
                self.assertIn(importer,pipeline)
        workflow=(ROOT/'.github/workflows/update.yml').read_text(encoding='utf-8')
        self.assertIn("cron: '17,47 * * * *'",workflow)
        self.assertIn('scripts/run_pipeline.py',workflow)

    def test_browser_auto_period_from_verified_feed(self):
        runtime=(ROOT/'scripts/quarterly_runtime.js').read_text(encoding='utf-8')
        self.assertIn('periodList=calcPeriods()',runtime)
        self.assertIn('selection=latest',runtime)
        self.assertIn("fetch('data/verified_financial_feed.json?t='",runtime)
        self.assertIn('setInterval(refresh,300000)',runtime)

if __name__=='__main__':
    unittest.main()
