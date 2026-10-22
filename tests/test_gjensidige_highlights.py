import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from ingest_official_pdf import parse_highlights

class GjensidigeHighlightsTests(unittest.TestCase):
    def test_q1_quarter_highlights(self):
        page='''Group highlights
- First quarter 2026 report
First quarter
Group
General insurance
Insurance revenue: NOK 11,004.1 million (9,993.9)
Insurance service result: NOK 2,288.1 million (1,313.6)
Combined ratio: 79.2% (86.9%)
Cost ratio: 11.7% (12.0%)
Profit performance
'''
        rows=parse_highlights([(2,page)],'Gjensidige',2026,1,'https://www.gjensidige.com/q1.pdf','test')
        self.assertEqual({r['metric']:r['value'] for r in rows},
                         {'insurance_revenue':11004.1,'insurance_service_result':2288.1,
                          'combined_ratio':79.2,'expense_ratio':11.7})
    def test_q2_quarter_and_ytd(self):
        page='''Group highlights
- Second quarter 2026 report
Second quarter
Group
General insurance
Insurance revenue: NOK 11,257.8 million (10,493.2)
Insurance service result: NOK 2,375.0 million (2,200.5)
Combined ratio: 78.9% (79.0%)
Cost ratio: 11.7% (12.0%)
Year-to-date
Group
General insurance
Insurance revenue: NOK 22,261.9 million (20,487.1)
Insurance service result: NOK 4,663.1 million (3,514.1)
Combined ratio: 79.1% (82.8%)
Cost ratio: 11.7% (12.0%)
Profit performance
'''
        rows=parse_highlights([(2,page)],'Gjensidige',2026,2,'https://www.gjensidige.com/q2.pdf','test')
        self.assertEqual(len(rows),8)
        self.assertEqual(next(r['value'] for r in rows if r['metric']=='insurance_revenue' and r['period_type']=='ytd'),22261.9)

if __name__=='__main__':
    unittest.main()
