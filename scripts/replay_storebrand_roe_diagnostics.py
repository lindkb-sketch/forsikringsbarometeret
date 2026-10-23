#!/usr/bin/env python3
"""Evidence-only extraction of Storebrand Q2 2026 ROE table and quarter headers."""
import json,tempfile
from pathlib import Path
from audit_financials import ROOT
from storebrand_automation_check import download_pdf
from import_storebrand_reports import pages,_unique_table,row,english
def run():
 source=json.loads((ROOT/"data/financial_observations.json").read_text())["observations"]
 golden=json.loads((ROOT/"data/golden_observations.json").read_text())["observations"]
 candidates=[x for x in golden if x.get("company")=="Storebrand" and x.get("year")==2025 and x.get("quarter")==2 and x.get("metric")=="return_on_equity"]
 if len(candidates)!=1:raise ValueError("Unique existing Storebrand Q2 2025 golden source required")
 url=candidates[0]["source_url"]
 with tempfile.TemporaryDirectory() as folder:
  path=Path(folder)/"q2.pdf"
  download_pdf(url,path)
  texts,sha=pages(path,"Storebrand Group",2026)
  page,table=_unique_table(texts,"Group - Key figures")
  section=table.split("Group - Key figures",1)[1].split("Financial metrics",1)[0]
  vals=row(section,"Cash return on equity, annualised (%)",8,english)
  lines=[line for line in section.splitlines() if ("Q2" in line or "Q4" in line or "2025" in line or "Cash return on equity" in line)][:16]
 result={"source_url":url,"sha256":sha,"page":page+1,"roi_row_cells":vals,"table_header_lines":lines,"golden":[{"quarter":x["quarter"],"value":x["value"]} for x in golden if x.get("company")=="Storebrand" and x.get("year")==2025 and x.get("quarter") in (2,4) and x.get("metric")=="return_on_equity"],"certification":"diagnostic_only; no historical column mapping assumed"}
 (ROOT/"data/storebrand_roe_diagnostics.json").write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n")
 print("STOREBRAND_ROE_DIAGNOSTIC",json.dumps(result,ensure_ascii=False))
if __name__=="__main__":run()
