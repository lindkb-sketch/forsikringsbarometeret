import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from klp_quarter_from_ytd import isolated

def row(q,revenue,claims,expenses,result):
    return {'company':'KLP Skadeforsikring','year':2026,'quarter':q,
            'period_type':'quarter','scope':'group','currency':'NOK',
            'unit':'NOK million','revenue_definition':'verified issuer revenue',
            'claims_definition':'verified issuer claims','expenses_definition':'verified issuer expenses',
            'source_url':'https://www.klp.no/test.pdf','source_sha256':'a'*64,
            'source_pages':[2,3],
            'amounts':{'insurance_revenue':revenue,'claims_cost':claims,
                       'operating_expenses':expenses,'insurance_service_result':result}}

class KLPQuarterTests(unittest.TestCase):
    def test_q1_direct(self):
        self.assertEqual(isolated(row(1,100,70,15,15))['ratios']['combined_ratio'],85)
    def test_q3_direct_quarter_column(self):
        result=isolated(row(3,160,102,24,34))
        self.assertEqual(result['amounts']['insurance_revenue'],160)
        self.assertAlmostEqual(result['ratios']['loss_ratio'],63.75)
        self.assertAlmostEqual(result['ratios']['combined_ratio'],78.75)
    def test_reject_ytd_column(self):
        data=row(3,360,252,54,54);data['period_type']='ytd'
        with self.assertRaisesRegex(ValueError,'isolated quarter'):
            isolated(data)
    def test_reject_subtraction(self):
        with self.assertRaisesRegex(ValueError,'directly'):
            isolated(row(3,160,102,24,34),row(2,200,150,30,20))
    def test_reject_missing_basis(self):
        data=row(3,160,102,24,34);data['claims_definition']=''
        with self.assertRaisesRegex(ValueError,'basis'):isolated(data)
    def test_roe_solvency_not_derived(self):
        data=row(3,160,102,24,34);data['return_on_equity']=12;data['solvency_ratio']=200
        result=isolated(data)
        self.assertNotIn('return_on_equity',result['ratios'])
        self.assertNotIn('solvency_ratio',result['ratios'])
if __name__=='__main__':unittest.main()
