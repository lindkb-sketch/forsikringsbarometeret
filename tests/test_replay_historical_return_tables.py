"""Historical issuer ROE/ROOF parsing must identify correct original quarter columns."""
import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from replay_historical_return_tables import from_page

class HistoricalReturnTableTests(unittest.TestCase):
 def test_fremtind_q3_2025_uses_adjusted_not_unadjusted_roe(self):
  text=('Fremtind Holding Q3 2025\n'
        'Annualisert egenkapitalavkastning 26,4 % 24,2 %\n'
        'Annualisert egenkapitalavkastning justert for\n'
        '3) Skattekostnaden er estimert\n'
        'transaksjonen med Eika Forsikring AS 41,4 % 24,2 %\n')
  self.assertEqual(from_page(text,'Fremtind',2025,3)[0],41.4)
 def test_fremtind_q4_2025_wrapped_entity_label(self):
  text=('Fremtind Holding Q4 2025\n'
        'Annualisert egenkapitalavkastning 24,8 %\n'
        'Annualisert egenkapitalavkastning justert for transaksjonen med Eika\n'
        '2) En fotnote\n'
        'Forsikring AS 39,7 % 30,1 % 40,5 %\n')
  self.assertEqual(from_page(text,'Fremtind',2025,4)[0],39.7)
 def test_fremtind_unadjusted_roe_not_substituted(self):
  with self.assertRaises(ValueError):
   from_page('Fremtind Holding Q3 2025\nAnnualisert egenkapitalavkastning 26,4 %',
             'Fremtind',2025,3)
 def test_gjensidige_q4_year_end_group_roe_with_footnote(self):
  text=('Gjensidige Forsikring Group\n'
        'NOK millions Q4 2025 Q4 2024 YTD 2025 YTD 2024\n'
        'Return on equity, annualised ¹ % 27.3 22.7\n'
        'Gjensidige Forsikring ASA\n'
        'Return on equity, annualised ¹ % 42.2 33.1')
  self.assertEqual(from_page(text,'Gjensidige',2025,4)[0],27.3)
 def test_tryg_q4_is_not_full_year_return(self):
  text=('Income overview\nQ4 Q4\nDKKm 2025 2024 2025 2024 2023\n'
        'Return on Own Funds (%) 36.8 21.9 40.3 34.1 24.8\n')
  self.assertEqual(from_page(text,'Tryg',2025,4)[0],36.8)
 def test_tryg_q4_header_must_be_unambiguous(self):
  text=('Income overview\nQ4 Q4\nDKKm 2025 2024 2025 2024 2023\n'
        'Return on Own Funds (%) 36.8 21.9 40.3 34.1 24.8\n')
  with self.assertRaises(ValueError):
   from_page(text.replace('Q4 Q4','FY Q4'),'Tryg',2025,4)
 def test_tryg_q3_wrapped_roof(self):
  text=('Management review Q1-Q3 2026 results\n'
        'Tryg own funds\nown funds (ROOF) was 47.0%.\n')
  self.assertEqual(from_page(text,'Tryg',2026,3)[0],47.0)
 def test_no_wrong_quarter_fallback(self):
  with self.assertRaises(ValueError):
   from_page('Fremtind Holding Q2 2025\nAnnualisert egenkapitalavkastning justert for\n'
             'Eika Forsikring AS 41,4 %','Fremtind',2025,3)

if __name__=='__main__':unittest.main()
