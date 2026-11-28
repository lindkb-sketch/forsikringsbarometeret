import sys, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from company_segment_details import observation, add_aggregates, amount_row, gj_rows, result_matches, preferred, sampo_rows, alm_roe_layout, alm_roe_rows

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
    def test_sampo_overview_shared_header_before_both_segments(self):
        a=anchor('Sampo',2025,3)
        known=[observation(a,2025,s,'insurance_revenue',v,7) for s,v in [('Private Nordic',1014),('Nordic Commercial',554)]]
        pages=[(7,'Financial overview Unit 7–9/2025 7–9/2024 1–9/2025 1–9/2024 2024\nSampo Group\nInsurance revenue, net EURm 2303 2137 6755 6214 8386\nPrivate Nordic\nInsurance revenue, net EURm 1014 925 2968 2730 3667\nPrivate UK\nInsurance revenue, net EURm 518 440 1487 1208 1659\nNordic Commercial\nInsurance revenue, net EURm 554 537 1640 1583 2128\nNordic Industrial\nInsurance revenue, net EURm 141 165 439 490 657')]
        rows=sampo_rows(a,pages,known)
        self.assertEqual(len(rows),8)
        self.assertEqual(next(r['value'] for r in rows if r['year']==2024 and r['segment']=='Nordic Commercial' and r['period_type']=='ytd'),1583)
        self.assertEqual(sampo_rows(a,[(8,pages[0][1])],known),[])
    def test_alm_roe_right_hand_crop_and_fy_are_distinct(self):
        from unittest.mock import patch
        self.assertEqual(alm_roe_layout('FY Q1 Q1 FY\n25 DKKm 2026 2025 2025',2026,1),(3,0,1))
        self.assertEqual(alm_roe_layout('Q4 Q4 FY FY\nDKKm 2025 2024 2025 2024',2025,4),(4,2,3))
        with self.assertRaises(ValueError):alm_roe_layout('FY FY\nDKKm 2025 2024',2025,4)
        for y,q,head,values,expected in [
            (2026,1,'FY Q1 Q1 FY\n25 DKKm 2026 2025 2025','9.6 14.5 14.4',9.6),
            (2025,4,'Q4 Q4 FY FY\nDKKm 2025 2024 2025 2024','14.8 11.4 14.4 9.6',14.8)]:
            a={**anchor('Gjensidige',y,q),'company':'Alm. Brand'}
            right=head+'\nReturn on equity after tax (% p.a. ) **) '+values
            full='Financial highlights and key ratios\nInsurance revenue\nTechnical provisions\n'+right
            with patch('rolling_alm_brand_reports.read_report',return_value=(['Alm. Brand Group Interim report Q'+str(q)+' '+str(y),'',full],{2:{'right':right}})):
                rows=alm_roe_rows(a,b'%PDF-fixture')
            self.assertEqual(next(r['value'] for r in rows if r['year']==y and r['period_type']=='quarter'),expected)
            self.assertEqual(len(rows),4)
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
