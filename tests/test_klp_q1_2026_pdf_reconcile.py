import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from klp_q1_2026_pdf_reconcile import verify_pages
def fixture():
    pages=['']*21
    pages[5]='''KLP Skadeforsikring AS 1. kvartal 2026
Resultatregnskap
MILLIONER KRONER 1. kvartal 2026 1. kvartal 2025 31.12.2025
3 Forsikringsinntekter 1 045,8 786,1 3 116,7
Forsikringskostnader -866,0 -588,2 -2 709,6
4 Forsikringsrelaterte driftskostnader -144,8 -119,0 -370,5
Gjenforsikringsresultat -38,9 -69,1 -51,2
Forsikringsresultat etter gjenforsikring -3,9 9,9 -14,6
Resultat før skattekostnad 36,9 32,3 334,8'''
    pages[20]='''Note 10 Nøkkeltall - akkumulert
MILLIONER KRONER 1. kvartal 2026 4. kvartal 2025 3. kvartal 2025
Skadeprosent brutto 82,8 % 86,9 % 73,2 %
Gjenforsikringsprosent 3,7 % 1,6 % 5,9 %
Skadeprosent etter gjenforsikring 86,5 % 88,6 % 79,0 %
Kostnadsprosent 13,8 % 11,9 % 13,3 %
Totalskadeprosent 100,4 % 100,5 % 92,3 %
Resultat før skatt 36,9 334,8 408,5
Avkastning på midler til forvaltning 0,5 % 6,2 % 4,5 %
Solvenskapitaldekning 231 % 233 % 261 %'''
    return pages
class KLPRealPDFReconciliationTests(unittest.TestCase):
    def test_q1_issuer_values_and_rounded_ratios(self):
        r=verify_pages(fixture())
        self.assertEqual(r['reported_quarter_amounts']['insurance_revenue'],1045.8)
        self.assertAlmostEqual(r['ratios']['combined_ratio'],100.34,places=1)
        self.assertEqual(r['reported_ytd_ratios']['combined_ratio'],100.4)
        self.assertEqual(r['reported_management_metrics']['solvency_ratio'],231)
        self.assertNotIn('investment_return_ytd',r['reported_management_metrics'])
    def test_wrong_note_blocks(self):
        x=fixture();x[20]=x[20].replace('100,4 %','97,0 %')
        with self.assertRaisesRegex(ValueError,'reconciliation'):verify_pages(x)
    def test_wrong_column_order_blocks(self):
        x=fixture();x[5]=x[5].replace('1. kvartal 2026 1. kvartal 2025','1. kvartal 2025 1. kvartal 2026')
        with self.assertRaisesRegex(ValueError,'column order'):verify_pages(x)
if __name__=='__main__':unittest.main()
