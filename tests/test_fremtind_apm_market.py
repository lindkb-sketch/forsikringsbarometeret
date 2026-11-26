import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from fremtind_apm_market import parse_income,parse_cr,parse_growth,emit,check_apm_batch
URL='https://cdn.sanity.io/files/rppnrdtw/production/example.pdf'
SHA='a'*64
PAGES=[(1,'Fremtind Holding Kvartalsrapport Q3 2026'),(2,'Innhold'),
       (3,'MNOK Q3 2026 Q3 2025 30.09.2026 30.09.2025 31.12.2025\nCombined ratio, netto etter gjenforsikring per\nResultat før skatt 1 810 1 621 4 933 3 845 5 335 segment (%)\nSkatt -469 -372 -1 162 -916 -1 274 PM 71,6 % 78,4 % 75,9 % 82,0 % 80,2 %\nBM 80,8 % 67,2 % 81,1 % 82,4 % 84,0 %'),
       (9,'Resultatutvikling i kvartalet sett. millioner kroner.\nInntekter fra forsikringstjenester ble 6 305 millioner kroner (6 047) i tredje\nkvartal. Det er en økning på 4,3 prosent hvor privatmarkedet har en økning i Resultat før skatt i tredje kvartal ble 1 810 millioner kroner, økning på 189\ninntekter fra forsikringstjenester på 4,4 prosent og bedriftsmarkedet har en millioner kroner fra tredje kvartal 2025 (1 621).\nøkning på 3,6 prosent.'),
       (10,'Segmentresultater - 30.09.2026\nMNOK PM BM Totalt\nInntekter fra forsikringstjenester 15 497 2 877 18 373')]
PREV=[(1,'Fremtind Holding Kvartalsrapport Q2 2026'),(2,'Innhold'),(9,'Segmentresultater – 30.06.2026\nMNOK PM BM Totalt\nInntekter fra forsikringstjenester 10 156 1 912 12 068')]
class FremtindAPMTests(unittest.TestCase):
    def test_reported_cr_and_growth_preferred(self):
        end=parse_income(PAGES,2026,3,URL,SHA)
        before=parse_income(PREV,2026,2,URL,'b'*64)
        cr=parse_cr(PAGES,2026,3,URL,SHA)
        growth=parse_growth(PAGES,2026,3,URL,SHA)
        anchor=dict(year=2026,quarter=3,source_url=URL,source_sha256=SHA,value=6305)
        rows=emit(anchor,end,before,cr,growth)
        self.assertTrue(check_apm_batch(rows,anchor))
        m={(r['segment'],r['year'],r['metric']):r for r in rows}
        for s,revenue,ratio,prior,g in [('Private',5341,71.6,78.4,4.4),('Commercial',965,80.8,67.2,3.6)]:
            self.assertEqual(m[s,2026,'insurance_revenue']['value'],revenue)
            self.assertEqual(m[s,2026,'combined_ratio']['value'],ratio)
            self.assertEqual(m[s,2025,'combined_ratio']['value'],prior)
            self.assertEqual(m[s,2026,'insurance_revenue_growth']['value'],g)
            self.assertEqual(m[s,2026,'combined_ratio']['status'],'reported')
        self.assertFalse(any(r['metric'] in ('loss_ratio','expense_ratio') for r in rows))
        rows[0]['value']+=10
        self.assertFalse(check_apm_batch(rows,anchor))
    def test_no_ytd_growth_leak(self):
        self.assertIsNone(parse_growth([(9,next(t for n,t in PAGES if n==9).replace('Resultatutvikling i kvartalet','Resultatutvikling hittil i år'))],2026,3,URL,SHA))
if __name__=='__main__':unittest.main()
