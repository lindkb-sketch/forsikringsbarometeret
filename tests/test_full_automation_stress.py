#!/usr/bin/env python3
"""Read-only stress assertions over the clean-baseline replay evidence.

Never treats successful subprocess exit as proof of financial restoration.
Records gaps per insurer and verifies fail-closed data publication contracts.
"""
import json
import unittest
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from audit_financials import audit
from build_verified_feed import build
from live_historical_replay import PLANS

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/"data/financial_observations.json"
REPORT=ROOT/"data/live_historical_replay.json"

class StressContracts(unittest.TestCase):
 def test_every_issuer_has_clean_replay_evidence(self):
  if not REPORT.exists():self.skipTest("Replay artifact is created only in isolated replay workflow")
  data=json.loads(REPORT.read_text())
  by={r["company"]:r for r in data["results"]}
  self.assertEqual(set(by),set(PLANS))
  for company,r in by.items():
   with self.subTest(company=company):
    self.assertIn("historical_rows_expected",r)
    self.assertIn("historical_rows_recovered",r)
    self.assertIn("historical_rows_missing",r)
    self.assertEqual(r["historical_rows_expected"],
                     r["historical_rows_recovered"]+r["historical_rows_missing"])
    self.assertEqual(r["clean_replay_certified"],
      r["import_commands_passed"] and r["historical_rows_missing"]==0
      and not r["golden_value_mismatches"] and r["staged_feed_parity"] and r["historical_rows_expected"]>0)

 def test_protector_replay_restores_official_norway_comparatives(self):
  self.assertEqual(PLANS["Protector"][:2],
                   ["protector_publish.py","import_protector_norway_historical_pdf.py"])
  if not REPORT.exists():
   return
  data=json.loads(REPORT.read_text())
  protector=next(r for r in data["results"] if r["company"]=="Protector")
  completed={e["step"]:e["code"] for e in protector["steps"]}
  self.assertEqual(completed.get("import_protector_norway_historical_pdf.py"),0)
  missing={tuple(k) for k in protector["missing_keys"]}
  for year in (2024,2025):
   self.assertNotIn(("Protector",year,3,"norway","quarter","insurance_revenue",None),missing)
  # The verified Norway segment table also contains four additional
  # Q3 2025 metrics and their 2024 comparative columns.
  self.assertNotIn("norway/quarter/Q3-2025",protector["missing_by_scope_period"])
  self.assertNotIn("norway/quarter/Q3-2024",protector["missing_by_scope_period"])

 def test_replay_uses_live_official_importers_for_three_priority_issuers(self):
  self.assertIn("import_gjensidige_pdf_norway.py",PLANS["Gjensidige"])
  self.assertIn("migrate_gjensidige_ytd_pdf.py",PLANS["Gjensidige"])
  self.assertIn("storebrand_q4_group.py",PLANS["Storebrand"])
  self.assertIn("protector_2025_pdf_backfill.py",PLANS["Protector"])
  self.assertIn("protector_2024_official_backfill.py",PLANS["Protector"])
  if not REPORT.exists():
   return
  results={r["company"]:r for r in json.loads(REPORT.read_text())["results"]}
  for company in ("Gjensidige","Storebrand","Protector"):
   completed={e["step"] for e in results[company]["steps"]}
   self.assertTrue(set(PLANS[company]).issubset(completed),
                   company+" replay exited before all historical sources were attempted")

 def test_same_source_build_is_idempotent(self):
  original=json.loads(SOURCE.read_text())
  first=build(original)
  self.assertEqual(first,build(original))
  self.assertEqual(len(first["observations"]),
                   len({(r["company"],r["year"],r["quarter"],r["scope"],
                         r["period_type"],r["metric"],r.get("segment")) for r in first["observations"]}))

 def test_provisional_observations_not_published(self):
  original=json.loads(SOURCE.read_text())
  candidate=dict(original["observations"][0])
  candidate.update(year=2029,quarter=4,status="provisional",value=999999)
  original["observations"].append(candidate)
  feed=build(original)
  self.assertFalse(any(r.get("year")==2029 and r.get("value")==999999
                       for r in feed["observations"]))

 def test_conflicting_source_rejected(self):
  original=json.loads(SOURCE.read_text())
  candidate=dict(original["observations"][0])
  candidate["value"]=candidate["value"]+999
  original["observations"].append(candidate)
  self.assertFalse(audit(original)["ok"])
  with self.assertRaises(ValueError):build(original)

 def test_fault_recovery_does_not_alter_published_snapshot(self):
  from gjensidige_report_check import official_report_links
  before=SOURCE.read_bytes()
  self.assertEqual(official_report_links("<html>unavailable</html>",
                   "https://www.gjensidige.com/",3,2026),[])
  self.assertEqual(before,SOURCE.read_bytes())

 def test_schedule_remains_half_hourly(self):
  workflow=(ROOT/".github/workflows/update.yml").read_text()
  self.assertIn("cron: '17,47 * * * *'",workflow)

if __name__=="__main__":unittest.main()
