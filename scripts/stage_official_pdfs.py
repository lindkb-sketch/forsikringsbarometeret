#!/usr/bin/env python3
"""Check actual registered official PDFs; never infer numbers."""
import json,hashlib,urllib.request,argparse
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def collect(registry,fetch=None):
    if fetch is None:
        def fetch(url):
            req=urllib.request.Request(url,headers={"User-Agent":"Forsikringsbarometeret/1.0"})
            with urllib.request.urlopen(req,timeout=40) as r:
                if not r.geturl().startswith("https://"):raise ValueError("Insecure redirect")
                return r.read(30_000_001)
    sources=[]
    for x in registry.get("workbooks",[]):
        if not x.get("approved"):continue
        url=x["report_pdf_url"]
        if not url.startswith("https://"):raise ValueError("PDF must use HTTPS")
        data=fetch(url)
        if len(data)>30_000_000 or not data.startswith(b"%PDF-"):raise ValueError("Not a valid bounded PDF")
        sources.append({"company":x["company"],"year":x["year"],"quarter":x["quarter"],"url":url,"sha256":hashlib.sha256(data).hexdigest(),"size":len(data)})
    return {"sources":sources,"note":"PDF provenance only; no unverified numerical observations"}
def main():
    a=argparse.ArgumentParser();a.add_argument("--registry",default=str(ROOT/"data/geographic_workbooks.json"));a.add_argument("--output",default=str(ROOT/"data/pdf_source_checks.json"));args=a.parse_args()
    result=collect(json.loads(Path(args.registry).read_text()))
    Path(args.output).write_text(json.dumps(result,indent=2)+"\n")
    print("Checked",len(result["sources"]),"PDF files")
if __name__=="__main__":main()
