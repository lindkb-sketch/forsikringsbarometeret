import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from discover_frende_fremtind import fremtind_rows
class HoldingArchiveTests(unittest.TestCase):
 def test_correct_row_and_quarter(self):
  html='''<table><tr><th>Selskap</th><th>År</th><th>Q1</th><th>Q2</th><th>Q3</th></tr>
<tr><td>Fremtind Forsikring</td><td>2026</td><td><a href="https://cdn.sanity.io/files/a.pdf">PDF</a></td><td></td><td><a href="https://cdn.sanity.io/files/b.pdf">PDF</a></td></tr>
<tr><td>Fremtind Holding</td><td>2026</td><td><a href="https://cdn.sanity.io/files/c.pdf">PDF</a></td><td></td><td><a href="https://cdn.sanity.io/files/d.pdf">PDF</a></td></tr></table>'''
  result=fremtind_rows(html)
  self.assertEqual([(r['year'],r['quarter'],r['document_url']) for r in result],[(2026,1,'https://cdn.sanity.io/files/c.pdf'),(2026,3,'https://cdn.sanity.io/files/d.pdf')])
 def test_combined_entity_year_cell_does_not_shift_quarters(self):
  html='<table><tr><td>Fremtind Holding 2026</td><td><a href="https://cdn.sanity.io/files/q1.pdf">PDF</a></td><td></td><td><a href="https://cdn.sanity.io/files/q3.pdf">PDF</a></td></tr></table>'
  rows=fremtind_rows(html)
  self.assertEqual([(r['quarter'],r['document_url'].split('/')[-1]) for r in rows],[(1,'q1.pdf'),(3,'q3.pdf')])
 def test_reject_untrusted_host(self):
  html='<table><tr><td>Fremtind Holding</td><td>2026</td><td><a href="https://bad.example/a.pdf">PDF</a></td></tr></table>'
  self.assertEqual(fremtind_rows(html),[])
if __name__=='__main__':unittest.main()
