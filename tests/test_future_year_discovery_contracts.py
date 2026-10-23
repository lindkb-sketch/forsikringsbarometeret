"""Year-rollover contracts for official report discovery.

These offline tests verify report link recognition and that calendar timing
cannot gate import. They do not claim unknown future PDF tables can be parsed.
"""
import io
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from discover_frende_fremtind import candidates
from discover_tryg import parse as parse_tryg, run as run_tryg
from gjensidige_report_check import official_report_links
from storebrand_automation_check import choose_reports

class FakeResponse:
    def __init__(self,html):self.html=html.encode()
    def __enter__(self):return self
    def __exit__(self,*args):return False
    def geturl(self):return 'https://tryg.com/en/downloads-2027'
    def read(self,n):return self.html

class YearRolloverTests(unittest.TestCase):
    def test_frende_q3_2027_issuer_archive(self):
        markup='<a href="https://frende.wrep.it/q3-2027-frende-holding-as">3. kvartal Frende Holding AS 2027</a>'
        matches=candidates('Frende',markup)
        self.assertEqual([(x['year'],x['quarter']) for x in matches],[(2027,3)])

    def test_fremtind_new_year_2027_holding_row(self):
        markup='<table><tr><td>Fremtind Holding 2027</td><td><a href="https://cdn.sanity.io/files/abc/q1.pdf">PDF</a></td></tr></table>'
        self.assertTrue(any(x.get('year')==2027 and x.get('quarter')==1 for x in candidates('Fremtind',markup)))

    def test_gjensidige_2027_quarter_source_link(self):
        html='<a href="https://mb.cision.com/Public/1122/55555/report.pdf">Interim report Q1 2027</a>'
        self.assertEqual(len(official_report_links(html,'https://www.gjensidige.com/investor-relations/',1,2027)),1)

    def test_tryg_2027_pairs(self):
        html=('''<a href="/2027/Interim_report_Q1_2027.pdf">Interim report Q1 2027</a>'''
              '''<a href="/2027/Investor_tables_Q1_2027.xlsx">Investor tables Q1 2027</a>''')
        self.assertEqual([(r['year'],r['quarter']) for r in parse_tryg(html,2027)],[(2027,1)])

    def test_tryg_reject_unpaired_pdf(self):
        html='<a href="/2027/Interim_report_Q1_2027.pdf">Interim report Q1 2027</a>'
        self.assertEqual(parse_tryg(html,2027),[])

    def test_storebrand_2027_pair_selection(self):
        records=[
          {'scope':'group','year':2027,'quarter':1,'document_url':'https://www.storebrand.com/group.pdf'},
          {'scope':'norway','year':2027,'quarter':1,'document_url':'https://www.storebrand.com/norway.pdf'}]
        self.assertEqual(set(choose_reports(records,2027,1)),{'group','norway'})

    def test_tryg_no_year_lock_in_default(self):
        import discover_tryg
        with patch('discover_tryg.date') as mock_date:
            mock_date.today.return_value=__import__('datetime').date(2027,2,10)
            with patch('discover_tryg.urllib.request.urlopen',return_value=FakeResponse(
                '<a href="/2027/Interim_report_Q1_2027.pdf">Interim report Q1 2027</a><a href="/2027/Investor_tables_Q1_2027.xlsx">Investor tables Q1 2027</a>')):
                with patch.object(discover_tryg,'OUT') as output:
                    output.write_text=lambda *args,**kwargs:None
                    pairs=run_tryg()
        self.assertIn(2027,{r['year'] for r in pairs})

if __name__=='__main__':unittest.main()
