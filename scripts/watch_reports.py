#!/usr/bin/env python3
"""Monitor a registry of explicitly approved quarterly-report PDF URLs.
No financial numbers are inferred from downloads. Hashes flag changed PDFs.
"""
import hashlib,json,urllib.request,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SOURCES=ROOT/"data/report_sources.json"
MANIFEST=ROOT/"data/report_manifest.json"
def verify_pdf(blob):
    return blob.startswith(b"%PDF-") and len(blob)>1024
def fetch(url):
    if not url.startswith("https://"):raise ValueError("Only HTTPS report URLs are allowed")
    req=urllib.request.Request(url,headers={"User-Agent":"Forsikringsbarometeret-report-monitor/1.0"})
    with urllib.request.urlopen(req,timeout=25) as response:
        if response.geturl().split(":")[0]!="https":raise ValueError("Unsafe redirect")
        blob=response.read(30*1024*1024+1)
    if len(blob)>30*1024*1024:raise ValueError("PDF exceeds 30 MB")
    if not verify_pdf(blob):raise ValueError("Not a PDF")
    return blob
def scan(fetcher=fetch):
    entries=json.loads(SOURCES.read_text())["sources"]
    previous={}
    if MANIFEST.exists():
        previous={x["document_url"]:x for x in json.loads(MANIFEST.read_text()).get("reports",[])}
    reports=[]; errors=[]
    for item in entries:
        if item.get("discovery_only"):continue
        if item.get("document_type")!="official_quarterly_report":
            errors.append(item.get("company","?")+": unsupported source type");continue
        try:
            pdf=fetcher(item["document_url"])
            digest=hashlib.sha256(pdf).hexdigest()
            reports.append({**item,"sha256":digest,"bytes":len(pdf),"change_status":"changed" if item["document_url"] in previous and previous[item["document_url"]]["sha256"]!=digest else ("new" if item["document_url"] not in previous else "unchanged")})
        except Exception as e:
            errors.append(f"{item.get('company')}: {type(e).__name__}: {e}")
    return {"reports":reports,"errors":errors,"all_sources_reachable":not errors}
if __name__=="__main__":
    result=scan()
    # On partial failures do not overwrite previous manifest.
    if result["all_sources_reachable"]:
        MANIFEST.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\\n")
    print(json.dumps(result,ensure_ascii=False,indent=2))
    if result["errors"]:sys.exit(1)
