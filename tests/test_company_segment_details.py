import sys, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from company_segment_details import observation, add_aggregates, amount_row, gj_rows, result_matches, preferred, sampo_rows

SHA='a'*64
def anchor(c,y=2026,q=3):
    return dict(company=c,year=y,quarter=q,source_sha256=SHA,source_url='https://www.sampo.com/official.pdf' if c=='Sampo' else 'https://mb.cision.com/official.pdf')
class CompanySegmentDetailsTests(unittest.TestCase):
    def test_exact_gjensidige_group_and_geographic_columns(self):
        a=anchor('Gjensidige')
        def table(rev):
            return f'NOK millions Q3 2026 Q3 2025 YTD 2026 YTD 2025 FY 2025\nInsurance revenue {rev} 1000 3000 2800 4000\nInsurance service result {rev*.2} 200 600 560 800\nLoss ratio, net of reinsurance 68 68 68 68 68\nCost ratio 12 12 12 12 12\nCombined ratio 80 80 80 80 80'
        pages=[(5,'General Insurance Private'),(6,table(1100)),(7,'General Insurance Private Norway\n'+table(1000)),(8,'General Insurance Commercial'),(9,table(1200)),(10,'General Insurance Commercial Norway\n'+table(900))]
        rows=gj_rows(a,pages)
        self.assertEqual(next(r['value'] for r in rows if r['segment']=='Private' and r['year']==2026 and r['period_type']=='quarter' and r['metric']=='insurance_service_result'),220)
        self.assertEqual(next(r['value'] for r in rows if r['segment']=='Private Norway' and r['year']==2025 and r['period_type']=='ytd' and r['metric']=='insurance_revenue'),2800)
        self.assertTrue(any(r['scope']=='norway' and r['metric']=='insurance_revenue' and r['value']==1900 for r in add_aggregates(rows)))
    def test_sampo_same_table_comparative_requires_current_anchor(self):
        a=anchor('Sampo',2025,3)
        known=[observation(a,2025,'Private Nordic','insurance_revenue',1000,9)]
        pages=[(9,'Private Nordic\n7–9/2025 7–9/2024 1–9/2025 1–9/2024 2024\nInsurance revenue, net EURm 1,000 900 2,900 2,600 3,500')]
        rows=sampo_rows(a,pages,known)
        self.assertEqual(next(r['value'] for r in rows if r['year']==2024 and r['period_type']=='quarter'),900)
        self.assertEqual(next(r['value'] for r in rows if r['year']==2024 and r['period_type']=='ytd'),2600)
        self.assertEqual(sampo_rows(a,pages,[{**known[0],'value':999}]),[])
    def test_complete_same_scope_additive_ytd_only(self):
        rows=[observation(anchor('Sampo',2025,q),2025,'Private Nordic','insurance_revenue',100*q,q) for q in (1,2,3)]
        got=add_aggregates(rows)
        self.assertEqual(next(r['value'] for r in got if r['quarter']==3 and r['period_type']=='ytd'),600)
        self.assertFalse(any(r['quarter']==3 and r['period_type']=='ytd' for r in add_aggregates(rows[1:])))
    def test_ambiguous_result_and_conflicting_source_rejected(self):
        self.assertIsNone(amount_row(['Insurance service result 10 20 30','Insurance service result 11 20 30'],'Insurance service result',3))
        self.assertTrue(result_matches(1000,80,200))
        self.assertFalse(result_matches(1000,80,300))
        r=observation(anchor('Gjensidige'),2026,'Private','insurance_revenue',1000,2)
        self.assertEqual(preferred([r,{**r,'value':1001}]),[])
if __name__=='__main__':unittest.main()
