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
    with urllib.request.urlopen(req, timeout=35) as response:
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
        rows = {}
        for line in text.splitlines():
            for label, (metric, unit) in FIELDS.items():
                if not line.startswith(label + " "):
                    continue
                rest = line[len(label):].strip()
                # pdfplumber generally separates numeric columns by >=2 spaces;
                # otherwise reject rather than guessing thousands grouping.
                cols = re.split(r"\s{2,}", rest)
                if len(cols) < 3:
                    # Q1/Q2 issuer tables commonly use single spaces throughout.
                    # Infer columns only if each is unambiguous in the PDF word geometry.
                    continue
                if not all(NUM.fullmatch(c.strip()) for c in cols[:3]):
                    continue
                rows[metric] = (number(cols[0]), unit, label)
        if len(rows) < 5:
            # Coordinate-aware extraction, using first numeric column aligned
            # with the first Q-year header, avoids ambiguous grouped thousands.
            page = pdf.pages[page_index]
            words = page.extract_words(x_tolerance=2, y_tolerance=3)
            headers = [w for w in words if w["text"] == str(year)]
            qheads = [w for w in words if w["text"] == f"Q{q}"]
            if not headers or not qheads:
                raise ValueError("No coordinate-verifiable quarter header")
            first_x = min(w["x0"] for w in qheads if any(abs(w["top"]-h["top"]) < 4 and h["x0"] > w["x0"] for h in headers))
            # First numeric column is to the right of the row label and its
            # x-position is determined by the table header.
            for label, (metric, unit) in FIELDS.items():
                if metric in rows: continue
                lines = [w for w in words if w["text"] == label.split()[0]]
                for w in lines:
                    top = w["top"]
                    same = sorted((v for v in words if abs(v["top"]-top)<3), key=lambda z:z["x0"])
                    labeltext = " ".join(v["text"] for v in same if v["x0"] < first_x)
                    if label not in labeltext: continue
                    values = [v["text"] for v in same if v["x0"] >= first_x]
                    if not values: continue
                    # Only accept a first value that is a single numeric token.
                    if re.fullmatch(r"-?\d+(?:[.,]\d+)?", values[0]):
                        rows[metric] = (number(values[0]), unit, label)
                    break
        if len(rows) != 5:
            raise ValueError("Insufficient unambiguous Holding metrics: " + repr(sorted(rows)))
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
                    if c.get("company") == "Fremtind" and c["document_url"].lower().endswith(".pdf")))
    existing = json.loads(DATA.read_text())
    seen = {(r["year"], r["quarter"]) for r in existing["observations"] if r["company"] == "Fremtind"}
    imported = []
    errors = []
    # Limit external downloads; only issuer-linked PDFs, never synthetic values.
    for url in links[:18]:
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
