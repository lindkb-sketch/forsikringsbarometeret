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
