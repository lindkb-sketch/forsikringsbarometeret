import unittest,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class StorebrandMigration(unittest.TestCase):
 def test_roe_observations(self):
  records=json.loads((ROOT/'data/financial_observations.json').read_text())['observations']
  self.assertGreaterEqual(len([r for r in records if r['company']=='Storebrand' and r['metric']=='return_on_equity']),5)
 def test_no_invalid_tryg_estimate(self):
  html=(ROOT/'index.html').read_text()
  self.assertNotIn("growth:'≈ 5,7 %'",html)
  self.assertNotIn('kommunikasjon.ntb.no/pressemelding/19098538',html)
if __name__=='__main__':unittest.main()
