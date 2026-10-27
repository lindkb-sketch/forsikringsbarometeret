#!/usr/bin/env python3
"""Inspect official Gjensidige workbooks on GitHub Actions, without manual uploads.

The URLs are source locations, not financial values. Emits sheet layouts for
review; it never publishes unvalidated observations.
"""
import hashlib,json,tempfile
from pathlib import Path
from geographic_excel import load_sheets
from publish_geographic_workbooks import download
from gjensidige_segments import extract
from reconcile_gjensidige_segments import reconcile

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/"data"/"verified_financial_feed.json"
OUTPUT=ROOT/"data"/"gjensidige_workbook_diagnostics.json"

def inspect():
    rows=json.loads(SOURCE.read_text(encoding="utf-8"))["observations"]
    sources={}
    for row in rows:
        if row.get("company")!="Gjensidige" or row.get("scope")!="norway" or row.get("period_type")!="quarter":
            continue
        url=row.get("source_url","")
        pdf=row.get("source_document_url","")
        if url.lower().split("?")[0].endswith(".xlsx") and pdf.startswith("https://"):
            sources[(row["year"],row["quarter"])]=(url,pdf)
    output={"workbooks":[]}
    for (year,quarter),(url,pdf) in sorted(sources.items()):
        item={"year":year,"quarter":quarter,"url":url,"report_pdf_url":pdf}
        try:
            content=download(url)
            item["sha256"]=hashlib.sha256(content).hexdigest()
            with tempfile.TemporaryDirectory() as folder:
                file=Path(folder)/"official.xlsx"
                file.write_bytes(content)
                sheets=load_sheets(file)
                item["sheets"]=[{"name":name,"labels":[{"cell":addr,"text":val[:120]}
                    for addr,val in cells.items() if isinstance(val,str)][:50]}
                    for name,cells in sheets.items() if "general insurance" in name.lower()]
                try:
                    extracted=extract(file,year,quarter,url,pdf)
                    item["reconciliation"]=reconcile(extracted,rows,year,quarter)
                    item["extraction"]={"status":"ok","observations":len(extracted),
                        "references":[{"segment":r["segment"],"metric":r["metric"],
                                       "sheet":r["source_sheet"],"cell":r["source_cell"]}
                                      for r in extracted]}
                except (ValueError,KeyError) as exc:
                    item["extraction"]={"status":"needs_mapping","reason":str(exc)}
        except Exception as exc:
            item["download_error"]=str(exc)
        output["workbooks"].append(item)
    OUTPUT.write_text(json.dumps(output,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"checked":len(output["workbooks"]),"diagnostics":str(OUTPUT),
                      "results":[{"period":f'{w["year"]}Q{w["quarter"]}',
                                  "extraction":w.get("extraction",{}).get("status"),
                                  "download_error":w.get("download_error")} for w in output["workbooks"]]}))
if __name__=="__main__":
    inspect()
    report=json.loads(OUTPUT.read_text(encoding="utf-8"))
    if not report["workbooks"] or any(w.get("download_error") or w.get("extraction",{}).get("status")!="ok" for w in report["workbooks"]):
        raise SystemExit("Gjensidige official workbook validation incomplete; no PM/BM publication permitted")
