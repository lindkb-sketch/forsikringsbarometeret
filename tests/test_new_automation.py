import sys,unittest,tempfile,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from import_uploaded_norway_excel import parse_tryg,parse_gjensidige
from update_stock_prices import update
class AutomationTests(unittest.TestCase):
 def test_tryg_only_quarters(self):
  p=Path('/mnt/data/Tryg Group - Q3 2025 - Investor tables (1).xlsx')
  if not p.exists():self.skipTest('Original workbook not installed')
  rows=parse_tryg(p);self.assertTrue(rows);self.assertEqual({'quarter'},{r['period_type'] for r in rows})
 def test_gjensidige_only_quarters(self):
  p=Path('/mnt/data/b0ab985d8284a746.xlsx')
  if not p.exists():self.skipTest('Original workbook not installed')
  rows=parse_gjensidige(p);self.assertTrue(rows);self.assertEqual({'quarter'},{r['period_type'] for r in rows})
 def test_stock_fetch_failure_does_not_erase_previous_close(self):
  with tempfile.TemporaryDirectory() as d:
   out=Path(d)/'stocks.json';out.write_text(json.dumps({'prices':{'Tryg':{'close':100,'trading_date':'2026-10-01'}}}))
   def fail(symbol):raise ConnectionError('Offline')
   result=update(fail,out);self.assertEqual(result['prices']['Tryg']['close'],100);self.assertEqual(len(result['errors']),5)
if __name__=='__main__':unittest.main()
