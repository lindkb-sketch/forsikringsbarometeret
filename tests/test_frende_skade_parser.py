import sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from import_frende_skade import parse_table
def report(year=2026,q=3):
 rows=[
 ['Resultatregnskap',f'{q}.kv.{year}',f'{q}.kv.{year-1}'],
 ['Premieinntekter for egen regning','1 000 000','900 000'],
 ['Resultat av teknisk regnskap i skadeforsikring','150 000','90 000'],
 ['Kostnadsandel %','15,0 %','17,0 %'],
 ['Skade % E/R','70,0 %','73,0 %'],
 ['Combined Ratio','85,0 %','90,0 %']]
 return '<table>'+''.join('<tr>'+''.join('<td>'+x+'</td>' for x in row)+'</tr>' for row in rows)+'</table>'
class FrendeSkadeParserTests(unittest.TestCase):
 def test_real_report_layout_q1_2026(self):
  report='Resultatregnskap 1.kv.2026 1.kv.2025 31.12.2025 I tusen kroner Teknisk regnskap for skadeforsikring Premieinntekter for egen regning 893 535 773 391 3 275 575 Erstatningskostnader for egen regning 685 018 649 203 2 231 872 Forskringsrelaterte driftskostnader 150 421 140 599 598 135 Resultat av teknisk regnskap i skadeforsikring 58 095-16 410 445 567 Nøkkelinformasjon Kostnadsandel %16,8 %18,2 %18,3 % Skade % E/R 76,7 %83,9 %68,1 % Combined Ratio 93,5 %102,1 %86,4 %'
  rows=parse_table(report,2026,1,'https://frende.wrep.it/q1-2026-frende-skadeforsikring-as','abc')
  by={(r['year'],r['metric']):r['value'] for r in rows}
  self.assertEqual(by[2026,'insurance_revenue'],893.535)
  self.assertEqual(by[2025,'insurance_service_result'],-16.41)
  self.assertEqual(by[2026,'expense_ratio'],16.8)
  self.assertEqual(by[2026,'loss_ratio'],76.7)
  self.assertEqual(by[2026,'combined_ratio'],93.5)

 def test_current_and_prior_same_quarter_separate_entity(self):
  rows=parse_table(report(),2026,3,'https://frende.wrep.it/q3-2026-frende-skadeforsikring-as','abc')
  self.assertEqual(len(rows),10)
  by={(r['year'],r['metric']):r for r in rows}
  self.assertEqual(by[2026,'insurance_revenue']['value'],1000)
  self.assertEqual(by[2025,'insurance_revenue']['value'],900)
  self.assertEqual(by[2026,'insurance_service_result']['value'],150)
  self.assertEqual(by[2026,'combined_ratio']['value'],85)
  self.assertTrue(all(r['scope']=='norway' and r['source_entity']=='Frende Skadeforsikring AS' and r['source_page']==1 for r in rows))
 def test_reject_missing_kpi(self):
  with self.assertRaises(ValueError):parse_table(report().replace('Combined Ratio','Unknown'),2026,3,'https://frende.wrep.it/a','abc')
 def test_reject_mismatched_quarter(self):
  with self.assertRaises(ValueError):parse_table(report(),2027,1,'https://frende.wrep.it/a','abc')
