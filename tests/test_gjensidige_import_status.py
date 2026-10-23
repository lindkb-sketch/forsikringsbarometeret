"""Regression coverage for Gjensidige discovery and audited historical baseline."""
import contextlib
import io
import json
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from import_gjensidige_latest import import_due, previously_verified_periods

def row(quarter,metric,sha="abc"):
    return dict(company="Gjensidige",year=2026,quarter=quarter,
                scope="group",period_type="quarter",status="reported",
                metric=metric,source_url="https://issuer.example/verified.pdf",
                source_page=5,source_sha256=sha)

class ExistingVerifiedTests(unittest.TestCase):
    def test_historical_verified_quarter_is_not_false_warning(self):
        with tempfile.TemporaryDirectory() as folder:
            target=Path(folder)/'observations.json'
            required=("insurance_revenue","insurance_service_result",
                      "combined_ratio","expense_ratio")
            target.write_text(json.dumps({"observations":[row(1,m) for m in required]}))
            calls=[]
            def importer(year,quarter):
                calls.append((year,quarter))
                return {"status":"not_discovered","period":f"Q{quarter} {year}","imported":0}
            out=io.StringIO()
            with contextlib.redirect_stdout(out):
                statuses=import_due(date(2026,10,23),importer,target)
            self.assertEqual(calls,[(2026,1),(2026,2),(2026,3)])
            self.assertEqual([r["status"] for r in statuses],
                             ["previously_verified","not_discovered","not_discovered"])
            self.assertNotIn("::warning::Gjensidige Q1",out.getvalue())
            self.assertIn("::warning::Gjensidige Q2",out.getvalue())
            self.assertIn("::warning::Gjensidige Q3",out.getvalue())

    def test_partial_or_unproven_records_are_not_approved(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'observations.json'
            path.write_text(json.dumps({"observations":[
                row(1,m,sha="") for m in
                ("insurance_revenue","insurance_service_result","combined_ratio","expense_ratio")]}))
            self.assertEqual(previously_verified_periods(path),set())

    def test_new_quarter_still_requires_discovery(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'observations.json'
            required=("insurance_revenue","insurance_service_result","combined_ratio","expense_ratio")
            path.write_text(json.dumps({"observations":[row(1,m) for m in required]}))
            def importer(year,quarter):
                return {"status":"not_discovered","period":f"Q{quarter} {year}","imported":0}
            statuses=import_due(date(2027,2,1),importer,path)
            self.assertEqual(statuses[-1]["period"],"Q4 2026")
            self.assertEqual(statuses[-1]["status"],"not_discovered")

if __name__=="__main__":unittest.main()
