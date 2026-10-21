import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from report_coverage import build
class TestCoverage(unittest.TestCase):
 def test_all_seven_present_and_not_falsely_certified(self):
  result=build()
  self.assertEqual(len(result['companies']),7)
  self.assertFalse(result['all_seven_automatic'])
  self.assertEqual({x['company'] for x in result['companies']},{'Fremtind','Gjensidige','Tryg','Sampo','Frende','Protector','Storebrand'})
if __name__=='__main__':unittest.main()
