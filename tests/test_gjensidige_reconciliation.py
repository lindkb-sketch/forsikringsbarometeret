"""Reconciliation must fail closed on mismatches and missing data."""
import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from reconcile_gjensidige_segments import reconcile

def record(segment,metric,value,scope="reported_segment",unit=None):
    return dict(company="Gjensidige",year=2027,quarter=1,period_type="quarter",
                scope=scope,segment=segment,metric=metric,value=value,
                unit=unit or ("percent" if metric.endswith("ratio") else "MNOK"),
                source_sheet="Official sheet",source_cell="B5")
def fixtures():
    pm=[record("Private Norway",m,v) for m,v in
        [("insurance_revenue",100),("insurance_service_result",20),
         ("loss_ratio",65),("expense_ratio",15),("combined_ratio",80)]]
    bm=[record("Commercial Norway",m,v) for m,v in
        [("insurance_revenue",200),("insurance_service_result",30),
         ("loss_ratio",70),("expense_ratio",15),("combined_ratio",85)]]
    total=[record(None,m,v,"norway") for m,v in
        [("insurance_revenue",300),("insurance_service_result",50),
         ("loss_ratio",68.3333333333),("expense_ratio",15),("combined_ratio",83.3333333333)]]
    return pm+bm,total
class TestReconcile(unittest.TestCase):
    def test_all_metrics_match(self):
        self.assertEqual(len(reconcile(*fixtures(),2027,1)),5)
    def test_mismatch_fails(self):
        segments,norway=fixtures()
        norway[0]["value"]=301
        with self.assertRaisesRegex(ValueError,"reconciliation failed"):
            reconcile(segments,norway,2027,1)
    def test_missing_segment_fails(self):
        segments,norway=fixtures()
        with self.assertRaisesRegex(ValueError,"Missing or ambiguous"):
            reconcile(segments[:-1],norway,2027,1)
    def test_units_must_match(self):
        segments,norway=fixtures()
        segments[0]["unit"]="EURm"
        with self.assertRaisesRegex(ValueError,"unit mismatch"):
            reconcile(segments,norway,2027,1)
if __name__=="__main__":unittest.main()
