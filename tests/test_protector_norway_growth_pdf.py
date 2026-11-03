"""PDF-only Norway comparators must be sourced from the Norway columns."""
import unittest
from scripts.import_protector_norway_historical_pdf import parse_norway_revenue

URL='https://storage.mfn.se/34613cd2-9b91-47d8-bae6-1c5274fa1298/interim-report-q3-2025-prot.pdf'
PAGE='''Interim Report (unaudited)Q3 and Q1-Q3 2025|Notes
Segment information - Q3
UK Sweden Norway Denmark France
NOKm Q3 2025 Q3 2024 Q3 2025 Q3 2024 Q3 2025 Q3 2024 Q3 2025 Q3 2024 Q3 2025 Q3 2024
Gross written premium 940 995 315 316 229 231 122 121 71
Insurance revenue 1,489 1,293 812 704 665 589 469 415 94
Insurance service result 295 284 108 168 78 178 132 (126) (16)'''

class ProtectorNorwayGrowthPDFTests(unittest.TestCase):
    def test_q3_norway_2024_comes_from_norway_revenue_column(self):
        rows=parse_norway_revenue([(14,PAGE)],URL,'a'*64)
        self.assertEqual([(r['year'],r['value']) for r in rows],[(2025,665),(2024,589)])
        self.assertTrue(all(r['scope']=='norway' and r['source_page']==14 for r in rows))
        self.assertTrue(all(r['source_document_period']=='Q3 2025' for r in rows))
    def test_no_group_totals_or_wrong_quarter(self):
        with self.assertRaises(ValueError):
            parse_norway_revenue([(14,PAGE.replace('Norway','Norwayx'))],URL,'a'*64)
        with self.assertRaises(ValueError):
            parse_norway_revenue([(14,PAGE.replace('Segment information - Q3','Segment information - Q2'))],URL,'a'*64)

if __name__=='__main__':
    unittest.main()
