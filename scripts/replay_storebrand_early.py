#!/usr/bin/env python3
"""Additional official Storebrand Q1/Q2 imports in disposable replay worktree only."""
import json
from pathlib import Path
from storebrand_automation_check import download_pdf,choose_reports
from storebrand_sources import discover
from import_storebrand_reports import parse_norway,parse_group,integrate
from audit_financials import ROOT
DATA=ROOT/"data/financial_observations.json"
def run():
 original=json.loads(DATA.read_text())
 sources={}
 for row in json.loads((ROOT/"data/golden_replay_sources.json").read_text())["storebrand"]:
  sources[(row["year"],row["quarter"],row["scope"])]=row["source_url"]
 imported=[]
 for q in (1,2):
  for scope,parser in (("norway",parse_norway),("group",parse_group)):
   url=(choose_reports(discover(year=2026)["reports"],2026,q)[scope]["document_url"] if scope=="group" else sources[(2026,q,scope)])
   target=ROOT/"data"/f"historical_storebrand_{scope}_q{q}.pdf"
   try:
    download_pdf(url,target)
    imported.extend(parser(target,url,2026,q))
   finally:
    target.unlink(missing_ok=True)
 result,added,updated=integrate(original,imported)
 DATA.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
 print(json.dumps({"replayed":len(imported),"added":added,"updated":updated}))
if __name__=="__main__":run()
