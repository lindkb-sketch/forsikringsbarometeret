#!/usr/bin/env python3
"""Validate Gjensidige PM/BM directly against the latest official quarterly PDF.

Read-only: never publishes observations. Fail closed on missing or ambiguous
segment tables, preserving diagnostics for GitHub Actions.
"""
import hashlib
import json
from pathlib import Path

from audit_financials import DATA
from import_gjensidige_pdf_norway import METRICS, SEGMENTS, parse
from ingest_official_pdf import download, read_pdf

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "gjensidige_pdf_diagnostics.json"


def validate():
    observations = json.loads(DATA.read_text(encoding="utf-8"))["observations"]
    candidates = [
        row for row in observations
        if row.get("company") == "Gjensidige"
        and row.get("scope") == "group"
        and row.get("period_type") == "quarter"
        and row.get("metric") == "combined_ratio"
        and row.get("source_type") == "official_quarterly_report"
        and row.get("source_url", "").startswith("https://")
    ]
    if not candidates:
        raise ValueError("No official Gjensidige quarterly PDF source in observations")
    latest = max((r["year"], r["quarter"]) for r in candidates)
    urls = {r["source_url"] for r in candidates
            if (r["year"], r["quarter"]) == latest}
    if len(urls) != 1:
        raise ValueError("Ambiguous official PDF source for latest quarter")
    url = urls.pop()
    blob = download(url)
    if not blob.startswith(b"%PDF-"):
        raise ValueError("Official source is not a PDF")
    digest = hashlib.sha256(blob).hexdigest()
    rows = parse(read_pdf(blob), *latest, url, digest)
    current = [r for r in rows if (r["year"], r["quarter"]) == latest]
    for segment in SEGMENTS:
        found = {r["metric"] for r in current if r["segment"] == segment}
        missing = set(METRICS) - found
        if missing:
            raise ValueError(f"{segment}: missing PDF metrics {sorted(missing)}")
    return {"status": "verified", "year": latest[0], "quarter": latest[1],
            "source_url": url, "source_sha256": digest,
            "segments": list(SEGMENTS), "observations": len(rows),
            "source_pages": sorted({r["source_page"] for r in rows})}


if __name__ == "__main__":
    try:
        result = validate()
    except Exception as exc:
        result = {"status": "blocked", "error": str(exc)}
        OUTPUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(result))
        raise SystemExit(1)
    OUTPUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result))
