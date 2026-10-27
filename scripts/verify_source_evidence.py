#!/usr/bin/env python3
"""Independently download original source documents and report per-observation evidence.

A numeric occurrence on a page is only a candidate, NOT proof that the correct
table/period/segment was selected. Only exact source-file SHA256 can be marked
as a verified document identity; unsupported sources are explicitly unresolved.
"""
import argparse
import hashlib
import io
import json
import re
import urllib.request
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/financial_observations.json"
OUT = ROOT / "data/source_evidence_audit.json"

def run():
    rows = json.loads(DATA.read_text(encoding="utf-8"))["observations"]
    groups = defaultdict(list)
    for i, row in enumerate(rows):
        groups[row["source_url"]].append((i, row))
    results = [None] * len(rows)
    documents = []
    for url, entries in sorted(groups.items()):
        doc = {"url": url, "observations": len(entries), "status": "unverified"}
        blob = None
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (source evidence audit)"})
            with urllib.request.urlopen(req, timeout=45) as response:
                blob = response.read(35_000_001)
            if len(blob) > 35_000_000:
                raise ValueError("Source exceeds 35 MB audit limit")
            sha = hashlib.sha256(blob).hexdigest()
            doc["sha256"] = sha
            doc["bytes"] = len(blob)
            expected = {r.get("source_sha256") for _, r in entries if r.get("source_sha256")}
            if expected and (len(expected) != 1 or sha not in expected):
                raise ValueError("Downloaded document SHA256 does not match recorded source hash")
            doc["status"] = "hash_verified" if expected else "downloaded_no_recorded_hash"
            pages = None
            if blob.startswith(b"%PDF"):
                import pdfplumber
                with pdfplumber.open(io.BytesIO(blob)) as pdf:
                    pages = [(page.extract_text() or "") for page in pdf.pages]
            for i, row in entries:
                item = {"index": i, "company": row["company"], "year": row["year"],
                        "quarter": row["quarter"], "metric": row["metric"],
                        "scope": row["scope"], "period_type": row["period_type"],
                        "value": row["value"], "source_url": url,
                        "source_page": row.get("source_page"), "source_cell": row.get("source_cell"),
                        "document_status": doc["status"], "status": "unresolved"}
                if pages is not None:
                    page = row.get("source_page")
                    if isinstance(page, int) and 1 <= page <= len(pages):
                        text = pages[page-1]
                        value = row["value"]
                        # The candidate check is intentionally NOT a verified metric match.
                        variants = {str(value), format(value, "g"), format(value, ",g")}
                        variants |= {v.replace(".", ",") for v in variants}
                        item["numeric_candidate_on_page"] = any(
                            re.search(r"(?<![\\d.,])" + re.escape(v) + r"(?![\\d.,])", text)
                            for v in variants
                        )
                        item["status"] = "numeric_candidate_only" if item["numeric_candidate_on_page"] else "value_not_located_on_page"
                    else:
                        item["status"] = "invalid_pdf_page"
                else:
                    item["status"] = "non_pdf_requires_format_specific_cell_or_section_check"
                results[i] = item
        except Exception as exc:
            doc["status"] = "download_or_identity_failed"
            doc["error"] = str(exc)
            for i, row in entries:
                results[i] = {"index": i, "company": row["company"], "year": row["year"],
                              "quarter": row["quarter"], "metric": row["metric"],
                              "value": row["value"], "source_url": url,
                              "source_page": row.get("source_page"),
                              "status": "source_unavailable_or_hash_mismatch",
                              "error": str(exc)}
        documents.append(doc)
        print(doc["status"], url, flush=True)
    summary = {"total": len(results), "documents": len(documents),
               "hash_verified_documents": sum(d["status"] == "hash_verified" for d in documents),
               "source_failures": sum(d["status"] == "download_or_identity_failed" for d in documents),
               "fully_verified_values": 0,
               "note": "Page-level numeric candidates are NOT independently verified table-cell values. All observations require table/period/segment extraction before approval."}
    report = {"schema_version": 1, "summary": summary, "documents": documents, "observations": results}
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))
    return summary["source_failures"] == 0

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--fail-on-source-errors", action="store_true")
    args = parser.parse_args()
    ok = run()
    if args.fail_on_source_errors and not ok:
        raise SystemExit(1)
