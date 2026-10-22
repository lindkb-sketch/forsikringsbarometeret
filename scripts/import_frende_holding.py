#!/usr/bin/env python3
"""Fail-closed Frende Holding issuer-report ingestion.

Frende's 2025+ reports are publisher HTML; discovery alone is not evidence
of financial values. Until a verified parser exists, refuse publication.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CANDIDATES = ROOT / "data/frende_fremtind_candidates.json"

def run():
    snapshot = json.loads(CANDIDATES.read_text(encoding="utf-8"))
    if not snapshot.get("complete"):
        raise ValueError("Frende issuer discovery incomplete")
    pending = [r for r in snapshot.get("candidates", []) if r.get("company") == "Frende"
               and r.get("year", 0) >= 2025]
    if not pending:
        raise ValueError("No recent Frende Holding reports discovered")
    print(json.dumps({"company": "Frende", "status": "awaiting_verified_publisher_parser",
                      "reports_discovered": len(pending), "imported": 0},
                     ensure_ascii=False))
    # Discovery must never be mistaken for completed ingestion.
    raise RuntimeError("Frende Holding: publisher report figures not yet verified; import blocked")

if __name__ == "__main__":
    run()
