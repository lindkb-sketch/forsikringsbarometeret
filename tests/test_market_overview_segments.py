import hashlib
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from build_market_overview_segments import parse_tryg,parse_gjensidige,parse_alm,build
URL='https://tryg.com/report.pdf'
SHA=hashlib.sha256(b'%PDF-test').hexdigest()

def tryg_block(name,revenue,cr):
    return f'{name}\nInsurance revenue {revenue} 1000 1000 1000 1000\nClaims ratio, net of reinsurance {cr-12} 68 68 68 68\nExpense ratio 12 12 12 12 12\nCombined ratio {cr} 80 80 80 80\n'

def gj_table(revenue,cr):
    return f'NOK millions Q3 2026 Q3 2025 YTD 2026 YTD 2025 FY 2025\nInsurance revenue {revenue} 1000.0 2000.0 2000.0 3000.0\nLoss ratio, net of reinsurance¹ {cr-12}.0 68.0 68.0 68.0 68.0\nCost ratio¹ 12.0 12.0 12.0 12.0 12.0\nCombined ratio¹ {cr}.0 80.0 80.0 80.0 80.0\n'

class MarketSegmentTests(unittest.TestCase):
    def test_tryg_exact_quarter_and_segment(self):
        text='Quarterly outline - Segments\nDKKm Q3 Q2 Q1 Q4 Q3\n2026 2026 2026 2025 2025\n'+tryg_block('Private',2000,75)+tryg_block('Commercial',3000,80)
        rows=parse_tryg([(34,text)],2026,3,URL,SHA)
        self.assertEqual(len(rows),16)
        self.assertEqual({r['segment'] for r in rows},{'Private','Commercial'})
        self.assertEqual(next(r['value'] for r in rows if r['segment']=='Private' and r['year']==2026 and r['metric']=='insurance_revenue'),2000)
        with self.assertRaises(ValueError):parse_tryg([(34,text.replace('Quarterly outline - Segments','Quarterly outline - Geography'))],2026,3,URL,SHA)
        with self.assertRaises(ValueError):parse_tryg([(34,text)],2027,3,URL,SHA)
    def test_gjensidige_group_is_not_norway(self):
        pages=[(9,'General Insurance Private'),(10,gj_table(2000,75)),
               (11,'General Insurance Private Norway\n'+gj_table(1000,70)),
               (13,'General Insurance Commercial'),(14,gj_table(3000,80)),
               (15,'General Insurance Commercial Norway\n'+gj_table(2000,77))]
        rows=parse_gjensidige(pages,2026,3,'https://mb.cision.com/report.pdf',SHA)
        self.assertEqual({r['source_page'] for r in rows},{10,14})
        self.assertEqual(len(rows),16)
        with self.assertRaises(ValueError):parse_gjensidige(pages[2:],2026,3,'https://mb.cision.com/report.pdf',SHA)
    def test_bad_hash_excluded_and_no_stale_segment(self):
        row=dict(company='Tryg',year=2026,quarter=3,scope='group',period_type='quarter',metric='insurance_revenue',source_type='official_quarterly_report',status='reported',source_url=URL,source_sha256='a'*64)
        out=build({'observations':[row]},{'observations':[]},lambda _:b'%PDF-test')
        self.assertEqual(out['observations'],[])
        self.assertEqual(out['status']['Tryg']['status'],'not_verified')
if __name__=='__main__':unittest.main()
