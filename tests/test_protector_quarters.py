import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from protector_kpi_check import extract, METRICS

class ProtectorQuarterTests(unittest.TestCase):
    def sample(self, periods):
        def table(title):
            return '<div>'+title+'</div><div>'+''.join('<span>'+p+'</span>' for p in periods)+'</div>'+''.join('<div>'+label+'</div>'+''.join('<span>'+str(100+i if metric in ('insurance_revenue','insurance_service_result') else (70+i if metric=='loss_ratio' else 10+i if metric=='expense_ratio' else 80+2*i))+'</span>' for i in range(5)) for label,metric in METRICS.items())
        return table('Protector')+table('Norway')
    def test_q4_and_next_year(self):
        values=extract(self.sample(['Q1 27','Q4 26','Q3 26','Q2 26','Q1 26']))
        self.assertEqual(len(values),30)
        self.assertEqual(values[('group',2027,1,'insurance_revenue')],100)
        self.assertEqual(values[('norway',2026,4,'combined_ratio')],82)
    def test_no_future_data_fabricated(self):
        with self.assertRaises(ValueError):
            extract(self.sample(['2027','2026','2025','2024','2023']))
if __name__ == '__main__':
    unittest.main()
