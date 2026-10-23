#!/usr/bin/env python3
"""Read-only historical issuer replay evidence, explicitly grading each insurer.

Runs existing issuer regression tests against real reports where available.
Never writes production observations, live feed, HTML or publication files.
"""
import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"data"/"historical_replay_audit.json"
CASES={
 "Fremtind": {"tests":["test_fremtind_import","test_fremtind_archive_rows"],"evidence":"parser fixtures and issuer-archive matching","real_full_replay":False},
 "Gjensidige":{"tests":["test_import_gjensidige_latest","test_gjensidige_publish","test_gjensidige_report_check"],"evidence":"issuer discovery, source verification and importer unit tests","real_full_replay":False},
 "Tryg":{"tests":["test_discover_tryg","test_tryg_q3_official","test_tryg_ytd_ratios"],"evidence":"paired report discovery and official value regressions","real_full_replay":False},
 "Sampo":{"tests":["test_sampo_real_q4","test_sampo_future"],"evidence":"real issuer PDF download, Q4 2025 parse and golden values","real_full_replay":True},
 "Frende":{"tests":["test_frende_import_gate","test_frende_fremtind_discovery"],"evidence":"issuer table fixtures and discovery checks, not full live import","real_full_replay":False},
 "Protector":{"tests":["test_protector_quarters"],"evidence":"multi-quarter parser fixture, not historical live import","real_full_replay":False},
 "Storebrand":{"tests":["test_storebrand_automation","test_storebrand_pdf_parser"],"evidence":"real Q3 2026 PDF fixtures, isolated import and idempotency","real_full_replay":True},
}
def execute():
    report={"checked_at_utc":datetime.now(timezone.utc).isoformat(),
            "mode":"isolated historical regression; not a full seven-issuer download-to-Pages certification",
            "companies":[]}
    for name, spec in CASES.items():
        cases=["tests/"+x+".py" for x in spec["tests"]]
        cmd=[sys.executable,"-m","unittest",*cases,"-v"]
        result=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True,timeout=240)
        passed=result.returncode==0
        record={"company":name,
                "status":("real_pdf_parser_replay_passed" if spec["real_full_replay"] else "partial_replay_passed") if passed else "failed",
                "real_pdf_parser_replay":spec["real_full_replay"] and passed,
                "full_discovery_download_import_validation_browser_certified":False,
                "evidence":spec["evidence"],"tests":spec["tests"],
                "exit_code":result.returncode,
                "diagnostics":(result.stdout+"\n"+result.stderr)[-2000:] if not passed else ""}
        report["companies"].append(record)
        print("REPLAY",name,record["status"],flush=True)
    report["test_suite_passed"]=all(c["status"]!="failed" for c in report["companies"])
    report["fully_certified_companies"]=[]
    report["requires_full_replay"]=[c["company"] for c in report["companies"]]
    OUT.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("REPLAY_REPORT",OUT,"suite_passed",report["test_suite_passed"])
    return report

if __name__=="__main__":
    result=execute()
    sys.exit(0 if result["test_suite_passed"] else 1)
