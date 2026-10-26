"""Regression coverage for historical Q4 ingestion and five-quarter diagnostics."""
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class HistoricalQ4PipelineTests(unittest.TestCase):
 def test_sampo_searches_prior_year_reports(self):
  s=(ROOT/'scripts/sampo_publish.py').read_text()
  self.assertIn('for year in range(2025,today.year+1)',s)
 def test_storebrand_accepts_2025_and_retries_q4(self):
  s=(ROOT/'scripts/storebrand_publish_q3.py').read_text()
  p=(ROOT/'scripts/run_pipeline.py').read_text()
  self.assertIn('args.year < 2025',s)
  self.assertIn("'--year','2025','--quarter','4'",p)
 def test_incomplete_quarters_cannot_be_reported_as_complete(self):
  from scripts.audit_profitability_history import audit
  obs=[dict(company='Frende',scope='group',period_type='quarter',status='reported',
       metric=metric,value=80,source_url='https://frende.no/report',year=2025,quarter=4)
       for metric in ('combined_ratio','loss_ratio','expense_ratio')]
  r=audit(obs,2026,3)
  self.assertFalse(r['fully_covered'])
  self.assertEqual(len(r['window']),5)
  self.assertEqual(r['window'][0],'Q3 2025')
if __name__=='__main__':unittest.main()
