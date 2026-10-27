"""Regression guards for existing Norwegian and Nordic segment data bindings."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "scripts/quarterly_runtime.js").read_text(encoding="utf-8")
ROWS = json.loads((ROOT / "data/verified_financial_feed.json").read_text(encoding="utf-8"))["observations"]

class SegmentBindingTest(unittest.TestCase):
    def test_existing_cards_are_connected_to_reported_scopes(self):
        for token in ("['Norge total','norway',null]",
                      "['Private Nordic','reported_segment','Private Nordic']",
                      "['Nordic Commercial','reported_segment','Nordic Commercial']",
                      "['Norge PM','reported_segment','Private Norway']",
                      "['Norge BM','reported_segment','Commercial Norway']"):
            self.assertIn(token, JS)
        self.assertIn("segmentData[company]=specs.map", JS)
        self.assertIn("if(!segmentData[name]||segmentSpecs[name])continue;", JS)
        self.assertIn("r.period_type==='quarter'&&r.metric===metric", JS)
        self.assertIn("r.year===yr&&r.quarter===quarter", JS)

    def test_published_q2_source_rows_for_supported_cards(self):
        for company, scope, segment in (
            ("Tryg", "norway", None),
            ("Gjensidige", "norway", None),
            ("Sampo", "reported_segment", "Private Nordic"),
            ("Sampo", "reported_segment", "Nordic Commercial"),
        ):
            with self.subTest(company=company, segment=segment):
                subset = [r for r in ROWS if r["company"] == company
                          and r["scope"] == scope and r.get("segment") == segment
                          and r["year"] == 2026 and r["quarter"] == 2
                          and r["period_type"] == "quarter"]
                self.assertTrue(subset)
                self.assertTrue(any(r["metric"] == "combined_ratio" for r in subset))
                self.assertTrue(all(r.get("source_url") and (r.get("source_page") or r.get("source_cell") or r.get("source_sheet")) for r in subset))

    def test_missing_pm_bm_not_faked_from_static_html(self):
        for segment in ("Private Norway", "Commercial Norway"):
            self.assertFalse(any(r["company"] == "Gjensidige"
                and r["scope"] == "reported_segment" and r.get("segment") == segment
                for r in ROWS))
        self.assertIn("Ingen kildeverifiserte segmenttall", JS)

if __name__ == "__main__":
    unittest.main()
