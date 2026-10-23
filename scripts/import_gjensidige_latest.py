#!/usr/bin/env python3
"""Import Gjensidige quarter observations from a report linked by its own IR page.

Only an explicit issuer-labelled quarterly report is eligible. An unavailable
source never produces invented numbers; the existing audited feed is retained.
"""
import argparse
import hashlib
import json
import os
import sys
import tempfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from gjensidige_report_check import ARCHIVE, HOME, official_report_links
from ingest_official_pdf import download, read_pdf, merge
from gjensidige_publish import parse_group_table

TARGET = ROOT / "data" / "financial_observations.json"

def index_html(url):
    request = urllib.request.Request(url, headers={"User-Agent": "Forsikringsbarometeret/1.0"})
    with urllib.request.urlopen(request, timeout=30) as response:
        if response.geturl().split("/")[2].lower() not in {"www.gjensidige.com", "gjensidige.com"}:
            raise ValueError("Issuer page redirected outside the trusted domain")
        body = response.read(4_000_001)
    if len(body) > 4_000_000:
        raise ValueError("IR page exceeds size limit")
    return body.decode("utf-8", errors="replace")

def import_period(year, quarter, fetch_index=index_html, fetch_pdf=download, extract=read_pdf, target=TARGET):
    urls = set()
    errors = []
    for index in (HOME, ARCHIVE):
        try:
            urls.update(official_report_links(fetch_index(index), index, quarter, year))
        except Exception as exc:
            errors.append(f"{index}: {type(exc).__name__}: {exc}")
    if not urls:
        return {"status": "not_discovered", "period": f"Q{quarter} {year}", "errors": errors, "imported": 0}
    # Reject ambiguous source selection rather than choosing an arbitrary document.
    if len(urls) != 1:
        return {"status": "ambiguous_sources", "sources": sorted(urls), "errors": errors, "imported": 0}
    url = next(iter(urls))
    try:
        blob = fetch_pdf(url)
        sha = hashlib.sha256(blob).hexdigest()
        pages = extract(blob)
        # The official cover can be image-based or use "Q3"/"interim report"
        # instead of the spelled-out quarter. Require issuer/year/period in
        # extractable report text before parsing the labelled group KPI table.
        import re
        document_head = " ".join(text for _, text in pages[:6]).lower()
        quarter_word = ("first", "second", "third", "fourth")[quarter - 1]
        indicators = (
            rf"\\bq\\s*{quarter}\\b",
            rf"\\b{quarter}(?:st|nd|rd|th)\\s+quarter\\b",
            rf"\\b{quarter}\\.?\\s*kvartal\\b",
            rf"\\b{quarter}\\s*quarter\\b",
            rf"\\b{quarter_word}\\s+quarter\\b",
        )
        if ("gjensidige" not in document_head or str(year) not in document_head or
            not any(re.search(pattern, document_head) for pattern in indicators)):
            raise ValueError("Official PDF text does not confirm Gjensidige and the requested reporting period")
        rows = parse_group_table(pages, year, quarter, url, sha)
        expected = {"insurance_revenue", "insurance_service_result", "combined_ratio", "expense_ratio"}
        present = {r["metric"] for r in rows if r["period_type"] == "quarter"}
        if not expected.issubset(present):
            return {"status": "unverified_report", "source": url, "found_metrics": sorted(present), "imported": 0}
        existing = json.loads(Path(target).read_text())
        merged, count = merge(existing, rows)
        if count:
            fd, temp = tempfile.mkstemp(prefix=".gjensidige-", suffix=".json", dir=Path(target).parent)
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as file:
                    json.dump(merged, file, ensure_ascii=False, indent=2)
                    file.write("\n")
                os.replace(temp, target)
            finally:
                if os.path.exists(temp):
                    os.unlink(temp)
        return {"status": "verified", "source": url, "imported": count, "observations": len(rows)}
    except Exception as exc:
        return {"status": "import_failed", "source": url, "error": f"{type(exc).__name__}: {exc}", "imported": 0}

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", type=int, default=2026)
    parser.add_argument("--quarter", type=int, choices=(1, 2, 3, 4), default=3)
    args = parser.parse_args()
    result = import_period(args.year, args.quarter)
    print(json.dumps(result, ensure_ascii=False))
    if result["status"] != "verified":
        print("::warning::Gjensidige official quarterly data not yet imported: " + result["status"])
