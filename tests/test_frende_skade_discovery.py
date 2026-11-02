import sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from discover_frende_skade import discover
class FrendeSkadeDiscovery(unittest.TestCase):
 def test_discovery_is_subsidiary_specific(self):
  html='<a href="https://frende.wrep.it/q3-2026-frende-skadeforsikring-as">3. kvartal Frende Skadeforsikring AS 2026</a><a href="/holding">3. kvartal Frende Holding AS 2026</a>'
  found=discover(html)
  self.assertEqual(len(found),1)
  self.assertEqual((found[0]['year'],found[0]['quarter']),(2026,3))
 def test_display_never_falls_back_to_group(self):
  js=(ROOT/'scripts/quarterly_runtime.js').read_text()
  self.assertIn("Frende:[['Frende Skadeforsikring AS · Norge','norway',null]]",js)
  self.assertIn("r.scope===scope",js)
