import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from check_reported_returns_coverage import coverage, quarterly_coverage

def obs(company,metric,year=2026,quarter=3,definition="",source="https://issuer.example/quarter.pdf"):
    return dict(company=company,metric=metric,year=year,quarter=quarter,
                scope="group",period_type="quarter",status="reported",
                source_type="official_quarterly_report",source_url=source,
                source_definition=definition,value=21.5)

class ReturnCoverageTests(unittest.TestCase):
    def test_correct_latest_issuer_quarter(self):
        rows=[obs("Fremtind","insurance_revenue"),
              obs("Fremtind","return_on_equity",definition="Eika-adjusted annualised EK return"),
              obs("Tryg","insurance_revenue"),
              obs("Tryg","return_on_equity",definition="ROOF"),
              obs("Protector","insurance_revenue"),
              obs("Protector","return_on_equity",definition="ROE"),
              obs("Gjensidige","insurance_revenue"),
              obs("Gjensidige","return_on_equity",definition="ROE"),
              obs("Storebrand","insurance_revenue"),
              obs("Storebrand","return_on_equity",definition="Cash return on equity, annualised")]
        self.assertTrue(all(x["state"]=="verified" for x in coverage(rows).values()))
        rows.append(obs("Tryg","insurance_revenue",2026,4))
        self.assertEqual(coverage(rows)["Tryg"]["state"],"missing_or_ambiguous")
    def test_reject_wrong_definition_and_non_pdf_source(self):
        rows=[obs("Tryg","insurance_revenue"),
              obs("Tryg","return_on_equity",definition="ordinary ROE",
                  source="https://issuer.example/excel.xlsx")]
        self.assertEqual(coverage(rows)["Tryg"]["state"],"missing_or_ambiguous")
    def test_q1_to_q3_2026_and_future_quarters_are_automatically_checked(self):
        rows=[obs("Tryg","insurance_revenue",2026,q) for q in (1,2,3)]
        rows.append(obs("Tryg","return_on_equity",2026,1,definition="ROOF"))
        result=quarterly_coverage(rows)
        self.assertEqual(result["Tryg Q1 2026"]["state"],"verified")
        self.assertEqual(result["Tryg Q2 2026"]["state"],"missing_or_ambiguous")
        self.assertEqual(result["Tryg Q3 2026"]["state"],"missing_or_ambiguous")
        self.assertNotIn("Tryg Q4 2026",result)
        rows.append(obs("Tryg","insurance_revenue",2026,4))
        self.assertIn("Tryg Q4 2026",quarterly_coverage(rows))
    def test_five_company_q3_2025_to_q3_2026_window(self):
        companies=("Fremtind","Storebrand","Gjensidige","Tryg","Protector")
        periods=((2025,3),(2025,4),(2026,1),(2026,2),(2026,3))
        rows=[obs(c,"insurance_revenue",y,q) for c in companies for y,q in periods]
        coverage_rows=quarterly_coverage(rows)
        self.assertEqual(len(coverage_rows),25)
        self.assertEqual(set(coverage_rows),{f"{c} Q{q} {y}" for c in companies for y,q in periods})
        self.assertTrue(all(row["state"]=="missing_or_ambiguous" for row in coverage_rows.values()))
        rows.append(obs("Storebrand","return_on_equity",2025,3,definition="Cash return on equity, annualised"))
        self.assertEqual(quarterly_coverage(rows)["Storebrand Q3 2025"]["state"],"verified")
    def test_pipeline_runs_coverage_after_verified_feed(self):
        source=(Path(__file__).resolve().parents[1]/"scripts/run_pipeline.py").read_text()
        self.assertIn("'check_reported_returns_coverage.py'",source)

if __name__=="__main__":unittest.main()
