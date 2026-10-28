import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from import_gjensidige_pdf_norway import parse

class GjensidigeNorwayPdfRatioTest(unittest.TestCase):
    def test_signed_amounts_produce_pm_bm_and_norway_ratios(self):
        def segment(name, revenue, claims, expenses, premiums, recovered):
            cr=-(claims+expenses+premiums+recovered)/revenue*100
            return "\n".join([
                "General Insurance "+name,
                "Q2 2026 Q2 2025",
                f"Insurance revenue {revenue:.1f} {revenue:.1f}",
                "Insurance service result 20.0 20.0",
                "Loss ratio, net of reinsurance 1.0 1.0",
                "Cost ratio 1.0 1.0",
                f"Combined ratio {cr:.2f} {cr:.2f}",
                f"Incurred claims and changes in past and future service {claims:.1f} {claims:.1f}",
                f"Other incurred insurance service expenses {expenses:.1f} {expenses:.1f}",
                f"Reinsurance premiums {premiums:.1f} {premiums:.1f}",
                f"Amounts recovered from reinsurance {recovered:.1f} {recovered:.1f}",
            ])
        pages=[(9,segment("Private Norway",100,-60,-10,-5,2)),
               (10,segment("Commercial Norway",300,-200,-30,-20,10))]
        rows=parse(pages,2026,2,"https://example.org/report.pdf","a"*64)
        def value(name,metric):
            return next(r["value"] for r in rows if r["year"]==2026 and r["segment"]==name and r["metric"]==metric)
        self.assertAlmostEqual(value("Private Norway","loss_ratio"),63)
        self.assertAlmostEqual(value("Private Norway","expense_ratio"),10)
        self.assertAlmostEqual(value("Private Norway","combined_ratio"),73)
        self.assertAlmostEqual(value("Commercial Norway","loss_ratio"),70)
        self.assertAlmostEqual(value("Commercial Norway","expense_ratio"),10)
        self.assertAlmostEqual(value("Commercial Norway","combined_ratio"),80)
        rev={s:value(s,"insurance_revenue") for s in ("Private Norway","Commercial Norway")}
        norway_loss=sum(value(s,"loss_ratio")*rev[s] for s in rev)/sum(rev.values())
        norway_cost=sum(value(s,"expense_ratio")*rev[s] for s in rev)/sum(rev.values())
        self.assertAlmostEqual(norway_loss,68.25)
        self.assertAlmostEqual(norway_cost,10)
        self.assertAlmostEqual(norway_loss+norway_cost,78.25)

if __name__=="__main__":
    unittest.main()
