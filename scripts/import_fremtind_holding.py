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
        # Report figures have grouped thousands (e.g. 6 205).
        # Extract exactly three numeric columns, not whitespace tokens.
        rows = {}
        amount = r"-?(?:\d{1,3}(?:[ \u00a0]\d{3})+|\d+)(?:,\d+)?\s*%?"
        for line in text.splitlines():
            for label, (metric, unit) in FIELDS.items():
                if not line.startswith(label + " "):
                    continue
                rest = line[len(label):].strip()
                # Greedy grouping can merge adjacent columns: "1 256 843 4 520"
                # must be 1256 | 843 | 4520, not 1256843 | 4 | 520.
                tokens = rest.replace("\u00a0", " ").split()
                matches = []
                for i in range(1, len(tokens)-1):
                    for j in range(i+1, len(tokens)):
                        values = [" ".join(tokens[:i]), " ".join(tokens[i:j]), " ".join(tokens[j:])]
                        if not all(re.fullmatch(amount, v) for v in values):
                            continue
                        nums = tuple(number(v) for v in values)
                        lengths = [len(str(int(abs(n)))) for n in nums]
                        score = max(lengths) - min(lengths)
                        matches.append((score, nums))
                if matches:
                    best = sorted(matches, key=lambda x: x[0])
                    if len(best) == 1 or best[0][0] < best[1][0]:
                        rows[metric] = (best[0][1][0], unit, label)
        if len(rows) != 5:
            raise ValueError("Unambiguous three-column key figures not found: " + repr(sorted(rows)))
        # A Q2/Q3/Q4 summary can show cumulative YTD values. Do not label
        # these as standalone quarters until the table explicitly identifies
        # the numeric column as the isolated quarter rather than YTD.
        if q > 1:
            raise ValueError("Quarter versus YTD column not independently verified; publication blocked")
        if abs(rows["combined_ratio"][0] - rows["loss_ratio"][0] - rows["expense_ratio"][0]) > 0.25:
            raise ValueError("Combined ratio reconciliation failed")
        digest = hashlib.sha256(blob).hexdigest()
        return [{
            "company": "Fremtind", "year": year, "quarter": q,
            "scope": "group", "period_type": "quarter",
            "metric": metric, "value": value, "unit": unit,
            "status": "reported", "source_type": "official_quarterly_report",
            "source_url": url, "source_page": page_index + 1,
            "source_entity": "Fremtind Holding konsern",
            "source_document_period": f"Q{q} {year}",
            "source_definition": label, "source_sha256": digest,
        } for metric, (value, unit, label) in rows.items()]

def run():
    candidates = json.loads(CANDIDATES.read_text())
    if not candidates.get("complete"):
        raise ValueError("Issuer discovery incomplete")
    links = list(dict.fromkeys(c["document_url"] for c in candidates["candidates"]
                    if c.get("company") == "Fremtind" and c.get("source_entity") == "Fremtind Holding" and c["document_url"].lower().endswith(".pdf")))
    existing = json.loads(DATA.read_text())
    seen = {(r["year"], r["quarter"]) for r in existing["observations"] if r["company"] == "Fremtind"}
    imported = []
    errors = []
    # Limit external downloads; only issuer-linked PDFs, never synthetic values.
    for url in links[:12]:
        try:
            rows = extract(read_pdf(url), url)
            key = (rows[0]["year"], rows[0]["quarter"])
            if key in seen: continue
            if rows[0]["year"] < 2025: continue
            imported.extend(rows)
            seen.add(key)
        except Exception as exc:
            errors.append({"url": url, "reason": str(exc)[:200]})
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
    print(json.dumps({"imported": len(imported), "quarters": sorted(seen),
                      "rejected_documents": len(errors), "sample_errors": errors[:4]}))
    return len(imported)

if __name__ == "__main__":
    run()
