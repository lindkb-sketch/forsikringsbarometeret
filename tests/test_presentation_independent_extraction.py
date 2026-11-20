import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from reconcile_nine_pdf_metrics import discover_presentation_metrics,reconcile_extracted

class PresentationEvidenceTests(unittest.TestCase):
 def test_explicit_q3_group_slide(self):
  rows=discover_presentation_metrics([(19,'Q3 2026 Group\nSolvency ratio: 238%')],2026,3)
  self.assertEqual([(x['metric'],x['value'],x['source_page']) for x in rows],
                   [('solvency_ratio',238.0,19)])
 def test_no_group_scope(self):
  self.assertEqual(discover_presentation_metrics([(1,'Q3 2026 Norway\nSolvency ratio: 238%')],2026,3),[])
 def test_prior_period(self):
  self.assertEqual(discover_presentation_metrics([(1,'Q2 2026 Group\nSolvency ratio: 238%')],2026,3),[])
 def test_multiple_period_values(self):
  self.assertEqual(discover_presentation_metrics([(1,'Q3 2026 Group\nSolvency ratio 238% 230%')],2026,3),[])
 def test_no_currency_guessing(self):
  self.assertEqual(discover_presentation_metrics([(1,'Q3 2026 Group\nInsurance revenue 3054')],2026,3),[])
 def test_independent_report_match(self):
  pres=discover_presentation_metrics([(19,'Q3 2026 Group\nSolvency ratio: 238%')],2026,3)
  report=[dict(pres[0],document_type='quarterly_report')]
  self.assertEqual(reconcile_extracted(pres+report)[0]['status'],'match')
if __name__=='__main__':unittest.main()
