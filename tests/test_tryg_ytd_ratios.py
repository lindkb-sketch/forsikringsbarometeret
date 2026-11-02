import sys, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from quarterly_ytd import derive_ytd, add_tryg_ytd

class TrygYtdRatioTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = []
        for quarter, values in enumerate(((70,10,80),(75,12,87),(78.2,14.6,92.8)), 1):
            for metric, value, unit in (
                ('insurance_revenue', 100, 'DKKm'),
                ('loss_ratio', values[0], 'percent'),
                ('expense_ratio', values[1], 'percent'),
                ('combined_ratio', values[2], 'percent'),
            ):
                cls.rows.append(dict(company='Tryg',scope='norway',year=2025,
                    quarter=quarter,period_type='quarter',metric=metric,value=value,unit=unit,
                    source_type='official_quarterly_report',source_page=36,
                    source_url='https://tryg.com/official-quarterly-report.pdf'))

    def test_pdf_q3_ratios(self):
        result = derive_ytd(self.rows, 2025, 3)
        self.assertAlmostEqual(result['loss_ratio']['value'], 74.4)
        self.assertAlmostEqual(result['expense_ratio']['value'], 12.2)
        self.assertAlmostEqual(result['combined_ratio']['value'], 86.6)
        self.assertAlmostEqual(result['combined_ratio']['value'],
            result['loss_ratio']['value'] + result['expense_ratio']['value'])

    def test_recalculate_all_periods_from_pdf(self):
        rows = add_tryg_ytd(self.rows)
        metrics = {r['metric'] for r in rows if r['company']=='Tryg'
                   and r['year']==2025 and r['quarter']==3 and r['period_type']=='ytd'}
        self.assertTrue({'combined_ratio','loss_ratio','expense_ratio'} <= metrics)
        self.assertTrue(all(r['source_type']=='official_quarterly_report' for r in rows))

    def test_missing_quarter_no_ratio(self):
        rows = [r for r in self.rows if r['quarter'] != 2]
        self.assertNotIn('combined_ratio', derive_ytd(rows, 2025, 3))

if __name__ == '__main__':
    unittest.main()
