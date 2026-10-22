import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from discover_tryg import parse

class TrygDiscoveryTests(unittest.TestCase):
    def test_exact_official_pdf_xlsx_pair(self):
        html='<a href="/system/files/2026-10/Interim%20report%20Q1-Q3%202026%20-%20TRYG%20A_S.pdf">Interim report Q1-Q3 2026 -TRYG A_S.pdf</a><a href="/system/files/2026-10/Tryg%20Group%20-%20Q3%202026%20-%20Investor%20tables.xlsx">Tryg Group - Q3 2026 - Investor tables.xlsx</a>'
        rows=parse(html,2026)
        self.assertEqual([(r['year'],r['quarter']) for r in rows],[(2026,3)])
    def test_reject_external_host(self):
        html='<a href="https://bad.example/Tryg%20Group%20-%20Q3%202026%20-%20Investor%20tables.xlsx">Q3 2026 Investor tables</a>'
        self.assertEqual(parse(html,2026),[])
    def test_no_unpaired_workbook(self):
        self.assertEqual(parse('<a href="/Q3_2026_Investor_tables.xlsx">Q3 2026 Investor tables</a>',2026),[])
if __name__=='__main__':unittest.main()
