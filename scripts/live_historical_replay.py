#!/usr/bin/env python3
"""Run real issuer import programs in temporary, isolated repository copies."""
import json,shutil,subprocess,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
PLANS={
"Fremtind":["discover_frende_fremtind.py","import_fremtind_holding.py"],
"Gjensidige":["import_gjensidige_latest.py","gjensidige_norway_excel.py"],
"Tryg":["discover_tryg.py","import_tryg.py","replay_tryg_historical.py"],
"Sampo":["sampo_publish.py"],
"Frende":["discover_frende_fremtind.py","import_frende_holding.py"],
"Protector":["protector_publish.py","import_protector_norway_historical_pdf.py"],
"Storebrand":["storebrand_publish_q3.py","replay_storebrand_early.py","replay_storebrand_roe_diagnostics.py"]}
def run():
 results=[]
 restored=[]
 for company,steps in PLANS.items():
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder)
   shutil.copytree(ROOT/"scripts",root/"scripts")
   shutil.copytree(ROOT/"data",root/"data")
   dataset=root/"data/financial_observations.json"
   snapshot=json.loads(dataset.read_text())
   (root/"data/golden_observations.json").write_text(json.dumps(snapshot,ensure_ascii=False))
   stripped=[x for x in snapshot["observations"] if x.get("company")!=company]
   snapshot["observations"]=stripped
   dataset.write_text(json.dumps(snapshot,ensure_ascii=False)+"\n")
   evidence=[]
   for name in steps:
    try:
     p=subprocess.run([sys.executable,str(root/"scripts"/name)],cwd=root,capture_output=True,text=True,timeout=150)
     evidence.append({"step":name,"code":p.returncode,"log":(p.stdout+"\n"+p.stderr)[-1000:]})
    except subprocess.TimeoutExpired:
     evidence.append({"step":name,"code":124,"log":"Timed out"})
    if evidence[-1]["code"]:break
   before=json.loads((ROOT/"data/financial_observations.json").read_text())["observations"]
   after=json.loads((root/"data/financial_observations.json").read_text())["observations"]
   key=lambda row:(row.get("company"),row.get("year"),row.get("quarter"),row.get("scope"),row.get("period_type"),row.get("metric"),row.get("segment"))
   old={key(row):row for row in before if row.get("company")==company}
   new={key(row):row for row in after if row.get("company")==company}
   mismatches=[str(k) for k,row in new.items() if k in old and isinstance(row.get("value"),(int,float)) and isinstance(old[k].get("value"),(int,float)) and abs(row["value"]-old[k]["value"])>max(.15,abs(old[k]["value"])*.00025)]
   # Build an isolated publishable feed from newly imported records, then
   # verify each restored reported observation survives unchanged.
   feed_ok=False
   feed_error=""
   try:
    sys.path.insert(0,str(ROOT/"scripts"))
    from build_verified_feed import build
    staged=build(json.loads((root/"data/financial_observations.json").read_text()))
    actual={key(row):row for row in staged["observations"] if row.get("company")==company}
    feed_ok=all(k in actual and actual[k]==row for k,row in new.items()
                if row.get("status") in ("reported","calculated"))
   except Exception as exc:
    feed_error=type(exc).__name__+": "+str(exc)[:220]
   restored.extend(new.values())
   missing_keys=[k for k in old if k not in new]
   missing_by_scope={}
   for k in missing_keys:
    label=f"{k[3]}/{k[4]}/Q{k[2]}-{k[1]}"
    missing_by_scope[label]=missing_by_scope.get(label,0)+1
   recovered=sum(k in new for k in old)
   missing=sum(k not in new for k in old)
   added=sum(k not in old for k in new)
   latest=max(((r["year"],r["quarter"]) for r in old.values()
               if r.get("scope")=="group" and r.get("period_type")=="quarter"),default=None)
   latest_keys=[k for k in old if latest and k[1:3]==latest and k[3]=="group" and k[4]=="quarter"]
   latest_recovered=sum(k in new for k in latest_keys)
   latest_golden_matches=sum(k in new and
       (not isinstance(new[k].get("value"),(int,float)) or
        not isinstance(old[k].get("value"),(int,float)) or
        abs(new[k]["value"]-old[k]["value"])<=max(.15,abs(old[k]["value"])*.00025))
       for k in latest_keys)
   discovery_steps=[e for e in evidence if e["step"].startswith("discover_")]
   live_discovery_step_passed=bool(discovery_steps) and all(e["code"]==0 for e in discovery_steps)
   discovery_proven=live_discovery_step_passed and latest_recovered==len(latest_keys) and bool(latest_keys)
   reconstructed_latest=bool(latest_keys) and latest_recovered==len(latest_keys) and latest_golden_matches==len(latest_keys) and feed_ok
   results.append({"company":company,"steps":evidence,"import_commands_passed":len(evidence)==len(steps) and all(e["code"]==0 for e in evidence),"new_imported_rows":added,"historical_rows_expected":len(old),"historical_rows_recovered":recovered,"historical_rows_missing":missing,"missing_by_scope_period":missing_by_scope,"missing_keys":[list(k) for k in missing_keys],"golden_value_mismatches":mismatches[:15],"staged_feed_parity":feed_ok,"staged_feed_error":feed_error,"latest_group_quarter":latest,"latest_group_rows_expected":len(latest_keys),"latest_group_rows_recovered":latest_recovered,"latest_group_golden_values_match":latest_golden_matches,"latest_group_replay_verified":reconstructed_latest,"explicit_live_discovery_step_passed":live_discovery_step_passed,"live_discovery_to_latest_import_proven":discovery_proven,"clean_replay_certified":len(evidence)==len(steps) and all(e["code"]==0 for e in evidence) and missing==0 and not mismatches and feed_ok and len(old)>0,"full_website_e2e_certified":False})
   print("REPLAY",company,"PASS" if results[-1]["clean_replay_certified"] else "INCOMPLETE","recovered",recovered,"expected",len(old),"feed",feed_ok,flush=True)
 stage_error=''
 stage_path=ROOT/'data/replay_only_verified_feed.json'
 try:
  sys.path.insert(0,str(ROOT/'scripts'))
  from build_verified_feed import build
  staged=build({'schema_version':1,'observations':restored})
  stage_path.write_text(json.dumps(staged,ensure_ascii=False,indent=2)+'\n')
 except Exception as exc:
  stage_error=type(exc).__name__+': '+str(exc)[:350]
 report={"staged_feed_generated":stage_path.exists(),"staged_feed_error":stage_error,"results":results,"production_data_modified":False,"full_seven_certified":all(r["clean_replay_certified"] for r in results),"replay_mode":"company historical rows removed from disposable baseline"}
 (ROOT/"data/live_historical_replay.json").write_text(json.dumps(report,indent=2)+"\n")
 print("REPLAY_CERTIFICATION",sum(x["historical_rows_recovered"] for x in results),"/",sum(x["historical_rows_expected"] for x in results),"full_seven",report["full_seven_certified"],flush=True)
if __name__=="__main__":run()
