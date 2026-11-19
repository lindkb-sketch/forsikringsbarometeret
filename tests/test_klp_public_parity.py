import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from verify_public_pages import klp_metrics_match

SOURCE={'insurance_revenue':1041.0,'insurance_service_result':113.6,
 'combined_ratio':89.08741594620557,'loss_ratio':77.21421709894332,
 'expense_ratio':11.873198847262248,'insurance_revenue_growth':32.83144060227128,
 'solvency_ratio':219.0,'profit_before_tax':154.6}

class KLPParityTests(unittest.TestCase):
 def test_null_roe_allowed(self):
  self.assertTrue(klp_metrics_match(dict(SOURCE,return_on_equity=None),SOURCE))
 def test_all_original_source_values_required(self):
  self.assertFalse(klp_metrics_match(dict(SOURCE,solvency_ratio=220),SOURCE))
 def test_unverified_roe_rejected(self):
  self.assertFalse(klp_metrics_match(dict(SOURCE,return_on_equity=12),SOURCE))
 def test_missing_source_metric_rejected(self):
  bad=dict(SOURCE);bad.pop('profit_before_tax')
  self.assertFalse(klp_metrics_match(bad,bad))
 def test_missing_public_metric_rejected(self):
  bad=dict(SOURCE);bad.pop('profit_before_tax')
  self.assertFalse(klp_metrics_match(bad,SOURCE))
if __name__=='__main__':unittest.main()
