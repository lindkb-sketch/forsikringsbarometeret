"""Unit tests for strict, quarter-independent Gjensidige segment extraction."""
import sys,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from gjensidige_segments import extract

URL="https://issuer.example/investor.xlsx"
PDF="https://issuer.example/report.pdf"

def sheets(period="Q3 2027"):
    return {
      "General Insurance Private Norway":{"A1":period,"A5":"Insurance revenue","A6":"Insurance service result","A7":"Loss ratio","A8":"Expense ratio","A9":"Combined ratio",**{f"B{i}":v for i,v in zip(range(5,10),[100,20,65,15,80])}},
      "General Insurance Commercial Norway":{"A1":period,"A5":"Insurance revenue","A6":"Insurance service result","A7":"Loss ratio","A8":"Expense ratio","A9":"Combined ratio",**{f"B{i}":v for i,v in zip(range(5,10),[200,30,70,15,85])}}
    }
class TestSegments(unittest.TestCase):
    def test_no_fabricated_numbers_and_future_quarter(self):
        source=sheets()
        # Period header is in column B, values must be read from B.
        for cells in source.values():
            cells["B1"]=cells.pop("A1")
        with patch("gjensidige_segments.load_sheets",return_value=source):
            rows=extract("unused",2027,3,URL,PDF)
        self.assertEqual(len(rows),10)
        self.assertEqual({r["segment"] for r in rows},{"Private Norway","Commercial Norway"})
        self.assertEqual([r["value"] for r in rows if r["metric"]=="insurance_revenue"],[100,200])
        self.assertTrue(all(r["source_cell"] and r["source_sheet"] for r in rows))
    def test_missing_period_rejected(self):
        with patch("gjensidige_segments.load_sheets",return_value=sheets()):
            with self.assertRaises(ValueError):
                extract("unused",2028,1,URL,PDF)
if __name__=="__main__":unittest.main()
