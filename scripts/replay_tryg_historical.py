#!/usr/bin/env python3
"""Probe Tryg 2024-25 official PDF/XLSX pairs, import only verified Norway observations."""
import json,sys,tempfile
from pathlib import Path
from discover_tryg import run as discover
from publish_geographic_workbooks import download
from geographic_excel import parse
from audit_financials import DATA,audit
ROOT=Path(__file__).resolve().parents[1]
PERIODS={(2024,3),(2024,4),(2025,1),(2025,2),(2025,3),(2025,4)}
def main():
 baseline=json.loads(DATA.read_text())
 report={"requested":sorted([list(x) for x in PERIODS]),"verified":[],"unresolved":[]}
 try:pairs=discover(years=[2024,2025])
 except Exception as exc:
  pairs=[]
  report["discovery_error"]=str(exc)[:300]
 mapping={(p["year"],p["quarter"]):p for p in pairs}
 for y,q in sorted(PERIODS):
  spec=mapping.get((y,q))
  if spec is None:
   report["unresolved"].append({"year":y,"quarter":q,"reason":"Issuer-linked paired PDF/XLSX not discovered"});continue
  try:
   content=download(spec["workbook_url"])
   with tempfile.TemporaryDirectory() as d:
    path=Path(d)/"tryg.xlsx";path.write_bytes(content)
    rows=parse(path,"Tryg",y,q,spec["workbook_url"],spec["report_pdf_url"])["observations"]
   quarter=[row for row in rows if row.get("scope")=="norway" and row.get("year")==y and row.get("quarter")==q and row.get("period_type")=="quarter"]
   expected={row["metric"]:row for row in json.loads((ROOT/"data/golden_observations.json").read_text())["observations"] if row.get("company")=="Tryg" and row.get("scope")=="norway" and row.get("year")==y and row.get("quarter")==q and row.get("period_type")=="quarter"}
   if len(expected)!=5 or {x["metric"] for x in quarter}!=set(expected):
    raise ValueError("Required Norway metric count mismatch")
   if any(abs(row["value"]-expected[row["metric"]]["value"])>max(.15,abs(expected[row["metric"]]["value"])*.00025) for row in quarter):
    raise ValueError("Historical Norway golden mismatch")
   from hashlib import sha256
   for row in quarter:row["source_sha256"]=sha256(content).hexdigest()
   baseline["observations"].extend(quarter)
   if not audit(baseline)["ok"]:raise ValueError("Financial source audit failed")
   report["verified"].append({"year":y,"quarter":q,"metrics":len(quarter)})
  except Exception as exc:
   report["unresolved"].append({"year":y,"quarter":q,"reason":type(exc).__name__+": "+str(exc)[:230]})
 DATA.write_text(json.dumps(baseline,ensure_ascii=False)+"\n")
 print("TRYG_HISTORICAL_REPLAY",json.dumps(report))
if __name__=="__main__":main()
