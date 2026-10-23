#!/usr/bin/env python3
"""Historical end-to-end evidence matrix for all seven insurers.

Real issuer regression tests are executed independently. A green regression
suite is NOT equivalent to a successful new-report discovery-to-publication.
No production source/feed files are written or altered.
"""
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUTPUT=ROOT/"data"/"full_import_replay_evidence.json"

# These capabilities deliberately describe only exercised code paths.
CHECKS={
 "Fremtind":{"suite":["test_fremtind_import","test_fremtind_archive_rows","test_frende_fremtind_discovery"],
   "source":"PDF layout samples, issuer archive unit tests","real_document":"not_proven","live_discovery":"not_proven"},
 "Gjensidige":{"suite":["test_import_gjensidige_latest","test_gjensidige_report_check","test_gjensidige_publish","test_gjensidige_norway_excel","test_publish_geographic_workbooks"],
   "source":"PDF report parser and Norway XLSX workbook fixtures","real_document":"not_proven","live_discovery":"not_proven"},
 "Tryg":{"suite":["test_discover_tryg","test_tryg_q3_official","test_geographic_excel","test_tryg_ytd_ratios","test_publish_geographic_workbooks"],
   "source":"Group PDF parsing and Norway XLSX workbook regressions","real_document":"not_proven","live_discovery":"not_proven"},
 "Sampo":{"suite":["test_sampo_real_q4","test_sampo_future"],
   "source":"Real issuer Q4 2025 PDF, downloaded and compared with golden values","real_document":"real_pdf","live_discovery":"not_proven"},
 "Frende":{"suite":["test_frende_import_gate","test_frende_fremtind_discovery"],
   "source":"Official publisher HTML table patterns; synthetic fixture assertions","real_document":"not_proven","live_discovery":"not_proven"},
 "Protector":{"suite":["test_protector_quarters"],
   "source":"Quarterly public KPI HTML pattern fixture","real_document":"not_proven","live_discovery":"not_proven"},
 "Storebrand":{"suite":["test_storebrand_automation","test_storebrand_pdf_parser"],
   "source":"Real issuer Q3 2026 group and Norway PDF fixtures, isolated merge and golden values","real_document":"real_pdf_fixture","live_discovery":"not_proven"}
}

def run():
    results=[]
    for company,plan in CHECKS.items():
        command=[sys.executable,"-m","unittest",*[f"tests/{name}.py" for name in plan["suite"]],"-v"]
        try:
            process=subprocess.run(command,cwd=ROOT,capture_output=True,text=True,timeout=240)
            passed=process.returncode==0
            error=(process.stdout+"\n"+process.stderr)[-1800:] if not passed else ""
        except subprocess.TimeoutExpired:
            passed=False
            error="Replay suite timed out"
        result={
            "company":company,"regression_suite_passed":passed,
            "source_evidence":plan["source"],
            "real_historical_document":plan["real_document"],
            "live_issuer_discovery_verified":False,
            "isolated_new_document_download_to_import_verified":False,
            "golden_financial_comparison_verified":passed and plan["real_document"]!="not_proven",
            "norway_excel_parser_tested":passed and company in ("Gjensidige","Tryg"),
            "norway_excel_live_download_verified":False,
            "automatic_publication_verified_from_this_replay":False,
            "full_e2e_certified":False,
            "tests":plan["suite"],"error":error}
        results.append(result)
        print("ISSUER_E2E",company,"PASS" if passed else "FAIL","FULL_E2E_NOT_PROVEN",flush=True)
    result={
      "checked_at_utc":datetime.now(timezone.utc).isoformat(),
      "isolation":"Read-only regression; no production data or synthetic observations published",
      "definition_of_full_e2e":"Live issuer index discovery -> download original official PDF/XLSX -> isolated parser/import -> provenance audit -> golden comparison -> staged browser verification",
      "reporting_rule":"Never infer full end-to-end success from green unit or historical PDF parser tests",
      "all_regressions_passed":all(r["regression_suite_passed"] for r in results),
      "all_seven_full_e2e_certified":all(r["full_e2e_certified"] for r in results),
      "companies":results}
    OUTPUT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("CERTIFIED",sum(r["full_e2e_certified"] for r in results),"/7")
    return result["all_regressions_passed"]

if __name__=="__main__":
    sys.exit(0 if run() else 1)
