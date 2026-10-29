import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from check_reported_returns_coverage import coverage

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
              obs("Gjensidige","return_on_equity",definition="ROE")]
        self.assertTrue(all(x["state"]=="verified" for x in coverage(rows).values()))
        rows.append(obs("Tryg","insurance_revenue",2026,4))
        self.assertEqual(coverage(rows)["Tryg"]["state"],"missing_or_ambiguous")
    def test_reject_wrong_definition_and_non_pdf_source(self):
        rows=[obs("Tryg","insurance_revenue"),
              obs("Tryg","return_on_equity",definition="ordinary ROE",
                  source="https://issuer.example/excel.xlsx")]
        self.assertEqual(coverage(rows)["Tryg"]["state"],"missing_or_ambiguous")
    def test_pipeline_runs_coverage_after_verified_feed(self):
        source=(Path(__file__).resolve().parents[1]/"scripts/run_pipeline.py").read_text()
        self.assertIn("'check_reported_returns_coverage.py'",source)

if __name__=="__main__":unittest.main()
