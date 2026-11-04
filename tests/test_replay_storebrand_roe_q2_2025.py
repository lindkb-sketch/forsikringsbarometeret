"""Require exact Storebrand Q2 2025 issuer ROE column labels."""
import sys,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import replay_storebrand_roe_q2_2025 as mod

HEADER='Group - Key figures\n2026 2025 01.01 - 30.06 Full year\nQ2 Q1 Q4 Q3 Q2 2026 2025 2025\nCash return on equity, annualised (%)\nFinancial metrics'

class StorebrandReturnReplayTests(unittest.TestCase):
    def parse(self,header=HEADER,values=None):
        values=values or [20.3,12.3,17.4,19.0,18.1,15.9,16.2,18.4]
        with patch.object(mod,'_unique_table',return_value=(4,header)):
            with patch.object(mod,'row',return_value=values):
                return mod.parse_roe([(0,header)])

    def test_q2_2025_is_explicit_fifth_column(self):
        self.assertEqual(self.parse(),(5,18.1,17.4))

    def test_missing_2025_quarter_header_rejected(self):
        with self.assertRaisesRegex(ValueError,'quarter header'):
            self.parse(HEADER.replace('Q2 Q1 Q4 Q3 Q2 2026','Q2 Q1 Q4 Q3 Q1 2026'))

    def test_missing_year_header_rejected(self):
        with self.assertRaisesRegex(ValueError,'year and YTD header'):
            self.parse(HEADER.replace('2026 2025 01.01','2026 2024 01.01'))

    def test_inconsistent_column_count_rejected(self):
        with self.assertRaisesRegex(ValueError,'column count'):
            self.parse(values=[20.3,12.3,17.4])

if __name__=='__main__':unittest.main()
