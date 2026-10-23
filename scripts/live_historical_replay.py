#!/usr/bin/env python3
"""Run real issuer import programs in temporary, isolated repository copies."""
import json,shutil,subprocess,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
PLANS={
"Fremtind":["discover_frende_fremtind.py","import_fremtind_holding.py"],
"Gjensidige":["import_gjensidige_latest.py"],
"Tryg":["discover_tryg.py","import_tryg.py"],
"Sampo":["sampo_publish.py"],
"Frende":["discover_frende_fremtind.py","import_frende_holding.py"],
"Protector":["protector_publish.py"],
"Storebrand":["storebrand_automation_check.py"]}
def run():
 results=[]
 for company,steps in PLANS.items():
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder)
   shutil.copytree(ROOT/"scripts",root/"scripts")
   shutil.copytree(ROOT/"data",root/"data")
   evidence=[]
   for name in steps:
    try:
     p=subprocess.run([sys.executable,str(root/"scripts"/name)],cwd=root,capture_output=True,text=True,timeout=150)
     evidence.append({"step":name,"code":p.returncode,"log":(p.stdout+"\n"+p.stderr)[-1000:]})
    except subprocess.TimeoutExpired:
     evidence.append({"step":name,"code":124,"log":"Timed out"})
    if evidence[-1]["code"]:break
   results.append({"company":company,"steps":evidence,"import_commands_passed":len(evidence)==len(steps) and all(e["code"]==0 for e in evidence),"full_website_e2e_certified":False})
   print("REPLAY",company,"PASS" if results[-1]["import_commands_passed"] else "BLOCKED",flush=True)
 report={"results":results,"production_data_modified":False,"full_seven_certified":False}
 (ROOT/"data/live_historical_replay.json").write_text(json.dumps(report,indent=2)+"\n")
if __name__=="__main__":run()
