"""Official-source discovery tests: no guessing, no cross-period pairing."""
import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from discover_gjensidige_sources import discover

class DiscoveryTests(unittest.TestCase):
    def test_explicit_official_pair(self):
        html='''<a href="https://mb.cision.com/Public/1122/2027/Q1_2027_investor_tables.xlsx">Q1 2027 Investor tables</a>
<a href="https://mb.cision.com/Public/1122/2027/Q1_2027_interim_report.pdf">Q1 2027 interim report</a>'''
        rows=discover(html)
        self.assertEqual([(r["year"],r["quarter"]) for r in rows],[(2027,1)])
        self.assertFalse(rows[0]["approved"])
    def test_untrusted_domain_rejected(self):
        html='''<a href="https://evil.example/Q1_2027_investor_tables.xlsx">Q1 2027 Investor tables</a>
<a href="https://evil.example/Q1_2027_interim_report.pdf">Q1 2027 interim report</a>'''
        self.assertEqual(discover(html),[])
    def test_no_cross_period_pair(self):
        html='''<a href="https://mb.cision.com/Q1_2027_investor_tables.xlsx">Q1 2027 Investor tables</a>
<a href="https://mb.cision.com/Q2_2027_interim_report.pdf">Q2 2027 interim report</a>'''
        self.assertEqual(discover(html),[])
    def test_ambiguous_workbook_rejected(self):
        html='''<a href="https://mb.cision.com/a/Q1_2027_investor_tables.xlsx">Q1 2027 Investor tables</a>
<a href="https://mb.cision.com/b/Q1_2027_investor_tables.xlsx">Q1 2027 Investor tables</a>
<a href="https://mb.cision.com/Q1_2027_interim_report.pdf">Q1 2027 interim report</a>'''
        self.assertEqual(discover(html),[])
if __name__=="__main__":unittest.main()
