#!/usr/bin/env python3
"""Report coverage of quarterly PDF-sourced issuer return KPIs.

This checks the latest issuer-specific published quarter, not calendar Q4
before that issuer has reported. Never creates missing figures.
"""
import json
from pathlib import Path
from audit_financials import DATA

TARGETS={
 "Fremtind":"Eika",
 "Tryg":"ROOF",
 "Gjensidige":"ROE",
 "Protector":"ROE",
}
def coverage(rows):
    result={}
    for company,expected in TARGETS.items():
        base=[r for r in rows if r.get("company")==company and
              r.get("scope")=="group" and r.get("period_type")=="quarter" and
              r.get("metric")=="insurance_revenue" and
              r.get("status") in ("reported","calculated")]
        if not base:
            result[company]={"state":"no_verified_quarter"}
            continue
        year,quarter=max((r["year"],r["quarter"]) for r in base)
        matches=[r for r in rows if r.get("company")==company and
                 r.get("year")==year and r.get("quarter")==quarter and
                 r.get("scope")=="group" and r.get("period_type")=="quarter" and
                 r.get("metric")=="return_on_equity" and
                 r.get("status")=="reported" and
                 r.get("source_type")=="official_quarterly_report" and
                 r.get("source_url","").startswith("https://") and
                 expected.lower() in r.get("source_definition","").lower()]
        result[company]={"period":f"Q{quarter} {year}",
                         "metric":expected,
                         "state":"verified" if len(matches)==1 else
                                 "missing_or_ambiguous",
                         "source_url":matches[0]["source_url"] if len(matches)==1 else None}
    return result

def run():
    rows=json.loads(DATA.read_text(encoding="utf-8"))["observations"]
    result=coverage(rows)
    dest=DATA.parent/"reported_returns_coverage.json"
    dest.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    for company,row in result.items():
        if row["state"]!="verified":
            print("::warning::RETURN_KPI_COVERAGE",company,row,flush=True)
        else:
            print("RETURN_KPI_VERIFIED",company,row["period"],flush=True)

if __name__=="__main__":run()
