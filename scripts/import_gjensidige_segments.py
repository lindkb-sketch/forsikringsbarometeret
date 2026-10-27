#!/usr/bin/env python3
"""Automatically publish independently reconciled Gjensidige PM/BM Norway quarters.

Use only the exact official XLSX/PDF pairs already verified for Norway totals.
No financial constants, inferred quarters or unverified publication.
"""
import hashlib
import json
import tempfile
from pathlib import Path
from audit_financials import DATA, audit
from build_verified_feed import publish
from gjensidige_segments import extract
from reconcile_gjensidige_segments import reconcile
from publish_geographic_workbooks import download, atomic_write

METRICS = {"insurance_revenue", "insurance_service_result", "loss_ratio", "expense_ratio", "combined_ratio"}
KEYS = ("company", "year", "quarter", "scope", "segment", "period_type", "metric")

def key(row):
    return tuple(row.get(k) for k in KEYS)

def prepare(data, fetcher=download):
    observations = data["observations"]
    periods = sorted({(r["year"], r["quarter"]) for r in observations
                      if r.get("company") == "Gjensidige" and r.get("scope") == "norway"
                      and r.get("period_type") == "quarter" and r.get("metric") in METRICS})
    existing = {key(r): r for r in observations}
    additions = []
    for year, quarter in periods:
        norway = [r for r in observations if r.get("company") == "Gjensidige"
                  and r.get("scope") == "norway" and r.get("period_type") == "quarter"
                  and (r.get("year"), r.get("quarter")) == (year, quarter)
                  and r.get("metric") in METRICS]
        if {r["metric"] for r in norway} != METRICS or len(norway) != len(METRICS):
            continue
        pairs = {(r.get("source_url"), r.get("source_document_url")) for r in norway}
        if len(pairs) != 1:
            continue
        url, pdf = next(iter(pairs))
        if not isinstance(url, str) or not url.lower().split("?")[0].endswith(".xlsx") or not isinstance(pdf, str) or not pdf.startswith("https://"):
            continue
        # The Norway source is independently approved before segment publication.
        blob = fetcher(url)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "official.xlsx"
            path.write_bytes(blob)
            extracted = extract(path, year, quarter, url, pdf)
        reconcile(extracted, observations, year, quarter)
        digest = hashlib.sha256(blob).hexdigest()
        for row in extracted:
            row["source_sha256"] = digest
            row["source_scope"] = "reported_segment"
            k = key(row)
            if k in existing:
                old = existing[k]
                if abs(old["value"] - row["value"]) > (0.001 if row["unit"] == "MNOK" else 0.01):
                    raise ValueError(f"Previously published PM/BM value changed: {k}")
                continue
            if any(key(r) == k for r in additions):
                raise ValueError(f"Duplicate PM/BM observation: {k}")
            additions.append(row)
    merged = {**data, "observations": observations + additions}
    result = audit(merged)
    if not result["ok"]:
        raise ValueError("PM/BM financial audit failed: " + repr(result["errors"]))
    return merged, len(additions)

def run():
    data = json.loads(DATA.read_text(encoding="utf-8"))
    merged, count = prepare(data)
    if count:
        atomic_write(DATA, merged)
    publish()
    print(f"Gjensidige Norway PM/BM: {count} new source-reconciled observations")

if __name__ == "__main__":
    run()
