import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from report_coverage import build, COMPANIES

class TestCoverage(unittest.TestCase):
 def test_all_seven_present_and_not_falsely_certified(self):
  result=build()
  self.assertEqual(len(result['companies']),7)
  self.assertFalse(result['all_seven_automatic'])
  self.assertEqual({x['company'] for x in result['companies']},set(COMPANIES))

 def test_certification_flag_is_consistent_and_has_evidence(self):
  result=build()
  self.assertIs(result['all_seven_automatic'],all(x['automatic_complete'] for x in result['companies']))
  for row in result['companies']:
   self.assertIsInstance(row['automatic_complete'],bool)
   self.assertIsInstance(row['official_archive_registered'],bool)
   self.assertIsInstance(row['candidate_discovery_verified'],bool)
   self.assertIsInstance(row['group_quarter_observations'],int)
   self.assertGreaterEqual(row['group_quarter_observations'],0)
   self.assertIsInstance(row['reason'],str)
   self.assertTrue(row['reason'])
   for key in ('prior_year_growth_quarter','prior_year_growth_ytd'):
    status=row[key]
    self.assertIsInstance(status['available'],bool)
    if not status['available']:
     self.assertTrue(status['reason'])
   # Certification needs independent evidence, not a green CI exit code.
   if row['automatic_complete']:
    self.assertTrue(row['official_archive_registered'])
    self.assertTrue(row['candidate_discovery_verified'])
    self.assertTrue(row['group_quarters_with_required_metrics'])
    self.assertTrue(row.get('source_import_verified'))
    self.assertTrue(row.get('scheduled_publication_verified'))
    self.assertTrue(row.get('historical_replay_verified'))

if __name__=='__main__':unittest.main()
