import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from klp_ratio_reconciliation import reconcile

def record(kind,amounts):
    return {'company':'KLP Skadeforsikring','year':2026,'quarter':1,
            'scope':'company','currency':'NOK','unit':'NOK million',
            'period_type':kind,'issuer_definition_verified':True,
            'source_url':'https://www.klp.no/report.pdf',
            'source_sha256':'a'*64,'source_pages':[20],
            'ratio_components':amounts}
class KLPReconciliationTests(unittest.TestCase):
    def setUp(self):
        a={'insurance_revenue':100,'gross_claims_cost':82.8,
           'reinsurance_effect':3.7,'operating_expenses':13.8}
        self.q=record('quarter',a)
        self.y=record('ytd',a)
        self.y['reported_ratios']={'gross_loss_ratio':82.8,'reinsurance_ratio':3.7,
            'loss_ratio':86.5,'expense_ratio':13.8,'combined_ratio':100.3}
    def test_reinsurance_is_included(self):
        result=reconcile(self.q,self.y)
        self.assertAlmostEqual(result['ratios']['loss_ratio'],86.5)
        self.assertAlmostEqual(result['ratios']['combined_ratio'],100.3)
    def test_wrong_ytd_ratio_blocks(self):
        self.y['reported_ratios']['combined_ratio']=98.0
        with self.assertRaisesRegex(ValueError,'reconciliation'):reconcile(self.q,self.y)
    def test_ytd_column_not_quarter(self):
        self.q['period_type']='ytd'
        with self.assertRaisesRegex(ValueError,'columns'):reconcile(self.q,self.y)
    def test_missing_reinsurance_blocks(self):
        del self.q['ratio_components']['reinsurance_effect']
        with self.assertRaisesRegex(ValueError,'components'):reconcile(self.q,self.y)
    def test_missing_issuer_definition_blocks(self):
        self.q['issuer_definition_verified']=False
        with self.assertRaisesRegex(ValueError,'definition'):reconcile(self.q,self.y)
    def test_mismatched_scope_blocks(self):
        self.y['scope']='group'
        with self.assertRaisesRegex(ValueError,'basis'):reconcile(self.q,self.y)
if __name__=='__main__':unittest.main()
