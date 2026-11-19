import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from import_alm_brand_presentation import reconcile, PRESENTATION, EXPECTED

BASE={'company':'Alm. Brand','year':2026,'quarter':3,'scope':'group','currency':'DKK',
      'status':'verified_issuer_announcement','metrics':{
      'insurance_revenue':3054,'insurance_service_result':755,'combined_ratio':75.3,
      'loss_ratio':59.2,'expense_ratio':16.1,'insurance_revenue_growth':1.6}}
EVIDENCE={'source_type':'official_results_presentation','source_url':PRESENTATION,
          'source_sha256':'a'*64,'source_page':19,'year':2026,'quarter':3,
          'scope':'group','currency':'DKK','metrics':EXPECTED}

class PresentationTests(unittest.TestCase):
 def test_reconcile_preserves_reported_financials(self):
  row=reconcile(BASE,EVIDENCE)
  self.assertEqual(row['metrics']['solvency_ratio'],238)
  self.assertEqual(row['metrics']['insurance_revenue'],3054)
  self.assertEqual(row['presentation_evidence']['source_page'],19)
 def test_conflicting_solvency_rejected(self):
  row=dict(BASE,metrics=dict(BASE['metrics'],solvency_ratio=225))
  with self.assertRaisesRegex(ValueError,'Conflicting'):reconcile(row,EVIDENCE)
 def test_wrong_scope_rejected(self):
  with self.assertRaisesRegex(ValueError,'scope'):reconcile(dict(BASE,scope='company'),EVIDENCE)
 def test_existing_metric_conflict_rejected(self):
  row=dict(BASE,metrics=dict(BASE['metrics'],insurance_revenue=3055))
  with self.assertRaisesRegex(ValueError,'override'):reconcile(row,EVIDENCE)
 def test_missing_pdf_rejected(self):
  from import_alm_brand_presentation import verify_pdf
  with self.assertRaises(ValueError):verify_pdf(b'not a pdf')
if __name__=='__main__':unittest.main()
