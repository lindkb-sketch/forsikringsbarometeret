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
 "Storebrand":"Cash return on equity",
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

def quarterly_coverage(rows, start_year=2025, start_quarter=3):
    """All published issuer quarters from Q3 2025 onward, including future quarters."""
    result={}
    for company,expected in TARGETS.items():
        periods=sorted({(r["year"],r["quarter"]) for r in rows
            if r.get("company")==company and r.get("scope")=="group"
            and r.get("period_type")=="quarter" and
            r.get("metric")=="insurance_revenue"
            and r.get("status") in ("reported","calculated")
            and (r.get("year",0),r.get("quarter",0))>=(start_year,start_quarter)})
        for year,quarter in periods:
            matches=[r for r in rows if r.get("company")==company
                and (r.get("year"),r.get("quarter"))==(year,quarter)
                and r.get("scope")=="group" and r.get("period_type")=="quarter"
                and r.get("metric")=="return_on_equity"
                and r.get("status")=="reported"
                and r.get("source_type")=="official_quarterly_report"
                and r.get("source_url","").startswith("https://")
                and expected.lower() in r.get("source_definition","").lower()]
            key=f"{company} Q{quarter} {year}"
            result[key]={"state":"verified" if len(matches)==1 else "missing_or_ambiguous",
                         "source_url":matches[0]["source_url"] if len(matches)==1 else None}
    return result

def run():
    rows=json.loads(DATA.read_text(encoding="utf-8"))["observations"]
    result=coverage(rows)
    history=quarterly_coverage(rows)
    dest=DATA.parent/"reported_returns_coverage.json"
    dest.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("RETURN_KPI_QUARTERLY_COVERAGE",json.dumps(history,ensure_ascii=False),flush=True)
    for key,row in history.items():
        if row["state"]!="verified":print("::warning::RETURN_KPI_QUARTER_MISSING",key,flush=True)
    # Required five rolling slots on the published profitability charts.
    # Future periods remain data-driven; never fabricate unavailable values.
    required=[f"{company} Q{q} {y}"
              for company in TARGETS
              for y,q in ((2025,3),(2025,4),(2026,1),(2026,2),(2026,3))]
    absent=[key for key in required
            if history.get(key,{}).get("state")!="verified"]
    if absent:
        raise SystemExit("RETURN_KPI_REQUIRED_FIVE_QUARTERS_MISSING "+", ".join(absent))
    print("RETURN_KPI_ALL_FIVE_QUARTERS_VERIFIED",len(required),flush=True)
    for company,row in result.items():
        if row["state"]!="verified":
            print("::warning::RETURN_KPI_COVERAGE",company,row,flush=True)
        else:
            print("RETURN_KPI_VERIFIED",company,row["period"],flush=True)

if __name__=="__main__":run()
