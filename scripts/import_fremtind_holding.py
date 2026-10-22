#!/usr/bin/env python3
"""Fail-closed Fremtind Holding quarterly importer from issuer-linked PDFs.

Only PDF links discovered on the official issuer archive are eligible.
The first report summary table must have the expected entity, period and
three-column layout. Never infer data from a press release or link ordering.
"""
import hashlib
import io
import json
import re
import tempfile
import urllib.parse
import urllib.request
from pathlib import Path
import pdfplumber
from audit_financials import DATA, audit

ROOT = Path(__file__).resolve().parents[1]
CANDIDATES = ROOT / "data/frende_fremtind_candidates.json"
FIELDS = {
    "Inntekter fra forsikringstjenester": ("insurance_revenue", "NOKm"),
    "Resultat fra forsikringstjenester": ("insurance_service_result", "NOKm"),
    "Skadeprosent, netto etter gjenforsikring (%)": ("loss_ratio", "percent"),
    "Kostnadsprosent (%)": ("expense_ratio", "percent"),
    "Combined ratio, netto etter gjenforsikring (%)": ("combined_ratio", "percent"),
}
NUM = re.compile(r"^-?\d+(?:[ .,]\d+)*\s*%?$")

def read_pdf(url):
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or parsed.hostname != "cdn.sanity.io" or not parsed.path.lower().endswith(".pdf"):
        raise ValueError("PDF not on approved official archive CDN")
    req = urllib.request.Request(url, headers={"User-Agent": "Forsikringsbarometeret/1.0"})
    with urllib.request.urlopen(req, timeout=12) as response:
        if urllib.parse.urlparse(response.geturl()).hostname != "cdn.sanity.io":
            raise ValueError("PDF redirected outside trusted CDN")
        blob = response.read(20_000_001)
    if len(blob) > 20_000_000 or not blob.startswith(b"%PDF-"):
        raise ValueError("Invalid or oversized PDF")
    return blob

def number(text):
    value = text.strip().replace("\u00a0", " ").replace("%", "").replace(" ", "").replace(",", ".")
    if not re.fullmatch(r"-?\d+(?:\.\d+)?", value):
        raise ValueError("Invalid financial number: " + text)
    return float(value)

def extract(blob, url):
    with pdfplumber.open(io.BytesIO(blob)) as pdf:
        if len(pdf.pages) < 3:
            raise ValueError("Report too short")
        pages = [p.extract_text() or "" for p in pdf.pages[:4]]
        heading = " ".join(pages[:2])
        periods = set(re.findall(r"Kvartalsrapport\s+Q([1-4])\s+(20\d{2})", heading, re.I))
        if len(periods) != 1 or "Fremtind Holding" not in heading:
            raise ValueError("Holding entity or report quarter not verified")
        q, year = next(iter(periods))
        q, year = int(q), int(year)
        # Require a labeled key-figures table and a header with the correct quarter.
        target = None
        for i, text in enumerate(pages):
            if "Resultatutvikling og nøkkeltall" in text and re.search(rf"Q{q}\s+{year}", text):
                target = (i, text)
                break
        if target is None:
            raise ValueError("Missing expected Holding key figures table")
        page_index, text = target
        columns = 3 if q == 1 else 5
        rows = {}
        amount = re.compile(r"-?(?:\d{1,3}(?: \d{3})+|\d+)(?:,\d+)?%?")
        for line in text.splitlines():
            for label, (metric, unit) in FIELDS.items():
                at = line.find(label)
                if at < 0 or (at > 0 and line[at-1].isalnum()):
                    continue
                rest = line[at + len(label):].strip()
                rest = re.split(r"(?<=\d)\s+(?=[A-Za-zÆØÅæøå])", rest, maxsplit=1)[0]
                tokens = rest.replace("\u00a0", " ").replace(" %", "%").split()
                def partitions(start, values):
                    if len(values) == columns:
                        if start == len(tokens):
                            yield tuple(values)
                        return
                    for stop in range(start + 1, len(tokens) + 1):
                        candidate = " ".join(tokens[start:stop])
                        if not amount.fullmatch(candidate):
                            continue
                        value = number(candidate)
                        if metric in ("insurance_revenue", "insurance_service_result") and abs(value) > 100000:
                            continue
                        yield from partitions(stop, values + [value])
                matches = set(partitions(0, []))
                if len(matches) == 1:
                    rows[metric] = (next(iter(matches)), unit, label)
                elif len(matches) > 1:
                    raise ValueError(f"Ambiguous financial columns for {metric}: {sorted(matches)}")
        if len(rows) != len(FIELDS):
            raise ValueError("Missing or ambiguous Holding key figures: " + repr(sorted(rows)) + "; table rows: " + repr([line[:180] for line in text.splitlines() if any(label in line for label in FIELDS)][:8]))
        for column in ([0] if q == 1 else [0, 2]):
            if abs(rows["combined_ratio"][0][column] - rows["loss_ratio"][0][column] - rows["expense_ratio"][0][column]) > 0.25:
                raise ValueError(f"Combined ratio reconciliation failed for column {column}")
        digest = hashlib.sha256(blob).hexdigest()
        result = []
        for column, period in ([(0, "quarter")] if q == 1 else [(0, "quarter"), (2, "ytd")]):
            for metric, (values, unit, label) in rows.items():
                result.append({
                    "company": "Fremtind", "year": year, "quarter": q,
                    "scope": "group", "period_type": period,
                    "metric": metric, "value": values[column], "unit": unit,
                    "status": "reported", "source_type": "official_quarterly_report",
                    "source_url": url, "source_page": page_index + 1,
                    "source_entity": "Fremtind Holding konsern",
                    "source_document_period": f"Q{q} {year}",
                    "source_definition": label, "source_sha256": digest,
                })
        return result

def run():
    candidates = json.loads(CANDIDATES.read_text())
    if not candidates.get("complete"):
        raise ValueError("Issuer discovery incomplete")
    links = list(dict.fromkeys(c["document_url"] for c in candidates["candidates"]
                    if c.get("company") == "Fremtind" and c.get("source_entity") == "Fremtind Holding" and c["document_url"].lower().endswith(".pdf")))
    if not links:
        raise ValueError("No issuer-verified Fremtind Holding PDF candidates; refusing false success")
    existing = json.loads(DATA.read_text())
    existing_keys = {(r["year"], r["quarter"], r["period_type"], r["metric"])
                     for r in existing["observations"] if r["company"] == "Fremtind" and r.get("scope") == "group"}
    imported = []
    errors = []
    # Every issuer-linked PDF is checked for its actual legal entity and period.
    for url in links[:30]:
        try:
            rows = extract(read_pdf(url), url)
            if rows[0]["year"] < 2025:
                continue
            for r in rows:
                key = (r["year"], r["quarter"], r["period_type"], r["metric"])
                if key not in existing_keys:
                    imported.append(r)
                    existing_keys.add(key)
        except Exception as exc:
            errors.append({"url": url, "reason": str(exc)[:1500]})
    # Q1 YTD equals Q1 standalone, by definition.
    allrows = existing["observations"] + imported
    for r in list(allrows):
        if r["company"] == "Fremtind" and r["scope"] == "group" and r["quarter"] == 1 and r["period_type"] == "quarter":
            k = (r["year"], 1, "ytd", r["metric"])
            if k not in existing_keys:
                copy = {**r, "period_type": "ytd"}
                imported.append(copy)
                existing_keys.add(k)
    allrows = existing["observations"] + imported
    index = {(r["year"], r["quarter"], r["period_type"], r["metric"]): r
             for r in allrows if r["company"] == "Fremtind" and r["scope"] == "group"}
    for (year, quarter, period, metric), current in list(index.items()):
        if period != "ytd" or quarter == 1:
            continue
        previous = index.get((year, quarter-1, "ytd", metric))
        if previous is None or (year, quarter, "quarter", metric) in index:
            continue
        revenue = index.get((year, quarter, "ytd", "insurance_revenue"))
        prev_revenue = index.get((year, quarter-1, "ytd", "insurance_revenue"))
        if metric in ("insurance_revenue", "insurance_service_result"):
            value = current["value"] - previous["value"]
            formula = "current_ytd - previous_ytd"
        elif metric in ("loss_ratio", "expense_ratio", "combined_ratio") and revenue and prev_revenue and revenue["value"] > prev_revenue["value"]:
            # Ratio of the isolated quarter, revenue-weighted from the two
            # official YTD ratios. Explicitly marked calculated, not reported.
            value = (current["value"]*revenue["value"] - previous["value"]*prev_revenue["value"]) / (revenue["value"]-prev_revenue["value"])
            formula = "(current_ytd_ratio*current_ytd_revenue - previous_ytd_ratio*previous_ytd_revenue)/(current_ytd_revenue - previous_ytd_revenue)"
        else:
            continue
        derived = {**current, "period_type": "quarter", "value": round(value, 3),
                   "status": "calculated", "calculation": formula,
                   "source_definition": current["source_definition"] + " (derived quarter from adjacent official YTD reports)",
                   "inputs": [previous["source_url"], current["source_url"]]}
        imported.append(derived)
        index[(year, quarter, "quarter", metric)] = derived
    if not imported and not any(r.get("company") == "Fremtind" for r in existing["observations"]):
        raise ValueError("Fremtind: no validated official PDF observations; sample failures: " + json.dumps(errors[:5]))
    if imported:
        merged = {**existing, "observations": existing["observations"] + imported}
        check = audit(merged)
        if not check["ok"]:
            raise ValueError("Audit failed: " + "; ".join(check["errors"]))
        import os
        fd, path = tempfile.mkstemp(dir=DATA.parent, prefix=".fremtind-", suffix=".json")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(merged, f, ensure_ascii=False, indent=2)
                f.write("\n")
            os.replace(path, DATA)
        finally:
            if os.path.exists(path): os.unlink(path)
    print(json.dumps({"imported": len(imported), "quarters": sorted({(r["year"], r["quarter"]) for r in imported}),
                      "rejected_documents": len(errors), "sample_errors": errors[:4]}))
    return len(imported)

if __name__ == "__main__":
    run()
