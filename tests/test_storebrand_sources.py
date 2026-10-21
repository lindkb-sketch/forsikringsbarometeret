import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from storebrand_sources import discover, ASA, FORSIKRING

class TestStorebrandSources(unittest.TestCase):
 def test_separate_entities_and_quarters(self):
  pages={
   ASA+'/2026': '<h2>3rd quarter</h2><a href="/q3.pdf">Interim report</a><a href="/slides.pdf">Analyst presentation</a><h2>2nd quarter</h2><a href="/q2.pdf">Interim report</a>',
   FORSIKRING: '<h2>2026</h2><a href="/f3.pdf">3rd quarter</a><a href="/f2.pdf">2nd quarter</a><h2>2025</h2><a href="/old.pdf">3rd quarter</a>'}
  result=discover(lambda url:pages[url]); records=result['reports']
  self.assertEqual(len(records),4)
  self.assertEqual({(r['scope'],r['quarter']) for r in records},{('group',3),('group',2),('norway',3),('norway',2)})
  self.assertTrue(all(r['status']=='discovered_not_imported' for r in records))
 def test_no_false_success(self):
  result=discover(lambda _: '<h2>2026</h2>')
  self.assertEqual(result['reports'],[])
  self.assertTrue(result['discovery_only'])
if __name__=='__main__': unittest.main()
