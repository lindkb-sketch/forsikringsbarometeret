import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from klp_q2_q3_discovery import classify,discover

class KLPQ2Q3DiscoveryTests(unittest.TestCase):
    def test_q2_q3_and_other_insurers(self):
        self.assertEqual(classify('https://www.klp.no/Kvartalsrapport%20KLP%20Skadeforsikring%20AS%20Q2%202026.pdf'),2)
        self.assertEqual(classify('https://www.klp.no/Kvartalsrapport%20KLP%20Skadeforsikring%20AS%20Q3%202026.pdf'),3)
        self.assertIsNone(classify('https://www.klp.no/Kvartalsrapport%20KLP%20Bank%20Q3%202026.pdf'))
    def test_does_not_infer_period_from_link_order(self):
        html='<a href="/Skadeforsikring-Q3-2026.pdf">Q3</a><a href="/Skadeforsikring-Q2-2026.pdf">Q2</a>'
        found=discover(html)
        self.assertEqual(len(found[2]),1)
        self.assertEqual(len(found[3]),1)
if __name__=='__main__':unittest.main()
