#!/usr/bin/env python3
"""One-shot batch verification of legacy official PDF source fingerprints.

Each distinct PDF is downloaded exactly once. An SHA-256 fingerprint proves
which file was consulted, not independently that a number is correct.
"""
import hashlib
import json
from collections import defaultdict
from urllib.parse import urlparse

import pdfplumber
import io
from audit_financials import DATA, audit
from ingest_official_pdf import download
from publish_geographic_workbooks import atomic_write

def backfill(data, fetch=download):
    rows=data["observations"]
    missing=defaultdict(list)
    for r in rows:
        if r.get("source_type")=="official_quarterly_report" and not r.get("source_sha256"):
            missing[r["source_url"]].append(r)
    unresolved=[]
    updated=0
    for url, associated in sorted(missing.items()):
        try:
            if urlparse(url).scheme!="https":
                raise ValueError("HTTPS required")
            blob=fetch(url)
            if not blob.startswith(b"%PDF-"):
                raise ValueError("Document is not PDF")
            digest=hashlib.sha256(blob).hexdigest()
            with pdfplumber.open(io.BytesIO(blob)) as pdf:
                pages=len(pdf.pages)
                if pages<1 or pages>250:
                    raise ValueError("Invalid PDF page count")
                for row in associated:
                    page=row.get("source_page")
                    if type(page) is not int or not 1<=page<=pages:
                        raise ValueError("Source page missing from official document")
                    if not (pdf.pages[page-1].extract_text() or "").strip():
                        raise ValueError("Referenced PDF page has no extractable text")
            for row in associated:
                row["source_sha256"]=digest
                row["source_integrity_check"]="pdf_signature_page_and_sha256"
                updated+=1
            print("OFFICIAL_PDF_FINGERPRINTED",len(associated),url,flush=True)
        except Exception as exc:
            unresolved.append({"url":url,"rows":len(associated),"error":str(exc)[:250]})
            print("::warning::PDF_FINGERPRINT_UNRESOLVED",url,str(exc)[:160],flush=True)
    if not audit(data)["ok"]:
        raise ValueError("Source fingerprint backfill failed financial audit")
    return data,{"fingerprinted":updated,"remaining":sum(x["rows"] for x in unresolved),
                 "unresolved":unresolved,"distinct_pdfs":len(missing),
                 "note":"Document hash and page checks are not numeric extraction verification."}

def run():
    data=json.loads(DATA.read_text(encoding="utf-8"))
    updated,result=backfill(data)
    if result["fingerprinted"]:
        atomic_write(DATA,updated)
    print("SOURCE_FINGERPRINT_BACKFILL",json.dumps(result,ensure_ascii=False),flush=True)
    if result["remaining"]:
        raise SystemExit("Some PDF fingerprints remain unresolved; see warnings")
if __name__=="__main__":
    run()
