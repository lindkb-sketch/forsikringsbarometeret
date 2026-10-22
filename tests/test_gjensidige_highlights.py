import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from gjensidige_publish import parse_group_table

Q1 = """NOK millions YTD 2026 YTD 2025 FY 2025
Insurance service result general insurance 2,288.1 1,313.6 7,081.4
Insurance revenue from general insurance 11,004.1 9,993.9 42,769.5
Loss ratio, net of reinsurance³ 67.5 % 74.9 % 70.8 %
Cost ratio³ 11.7 % 12.0 % 12.7 %
Combined ratio³ 79.2 % 86.9 % 83.4 %
"""
Q2 = """NOK millions Q2 2026 Q2 2025 YTD 2026 YTD 2025 FY 2025
Insurance service result general insurance 2,375.0 2,200.5 4,663.1 3,514.1 7,081.4
Insurance revenue from general insurance 11,257.8 10,493.2 22,261.9 20,487.1 42,769.5
Loss ratio, net of reinsurance³ 67.2 % 67.1 % 67.4 % 70.9 % 70.8 %
Cost ratio³ 11.7 % 12.0 % 11.7 % 12.0 % 12.7 %
Combined ratio³ 78.9 % 79.0 % 79.1 % 82.8 % 83.4 %
"""

class GjensidigeHighlightsTests(unittest.TestCase):
    def test_official_q1_table(self):
        rows = parse_group_table([(4,Q1)],2026,1,'https://mb.cision.com/q1.pdf','sha')
        self.assertEqual(len(rows),5)
        self.assertEqual({r['metric']:r['value'] for r in rows if r['period_type']=='quarter'},
                         {'insurance_revenue':11004.1,'insurance_service_result':2288.1,
                          'combined_ratio':79.2,'expense_ratio':11.7,'loss_ratio':67.5})
        self.assertTrue(all(r['source_page']==4 for r in rows))
    def test_official_q2_table_quarter_and_ytd(self):
        rows = parse_group_table([(4,Q2)],2026,2,'https://mb.cision.com/q2.pdf','sha')
        self.assertEqual(len(rows),10)
        quarter = {r['metric']:r['value'] for r in rows if r['period_type']=='quarter'}
        ytd = {r['metric']:r['value'] for r in rows if r['period_type']=='ytd'}
        self.assertEqual(quarter['insurance_revenue'],11257.8)
        self.assertEqual(ytd['insurance_revenue'],22261.9)
        self.assertEqual(ytd['insurance_service_result'],4663.1)
    def test_reject_ambiguous_group_table(self):
        with self.assertRaisesRegex(ValueError,'uniquely'):
            parse_group_table([(4,Q2),(5,Q2)],2026,2,'https://mb.cision.com/q2.pdf','sha')

if __name__=='__main__':
    unittest.main()
