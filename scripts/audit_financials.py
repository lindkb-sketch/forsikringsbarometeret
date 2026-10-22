#!/usr/bin/env python3
"""Validate report-only observations; derive revenue growth; write machine-readable audit.
Never replace last published data with incomplete or invalid updates.
"""
import json, math, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/"data"/"financial_observations.json"
OUT=ROOT/"data"/"financial_audit.json"
COMPANIES={"Fremtind","Gjensidige","Tryg","Sampo","Frende","Protector","Storebrand"}
METRICS={"insurance_revenue","insurance_revenue_growth","insurance_service_result","combined_ratio","loss_ratio","expense_ratio","return_on_equity","solvency_ratio"}
def audit(data):
    errors=[]; warnings=[]; records=data.get("observations",[])
    seen={}; calculated=[]
    for i,r in enumerate(records):
        label=f"observation {i+1}"
        for field in ("company","year","quarter","scope","period_type","metric","value","source_url","source_type"):
            if r.get(field) is None or r.get(field)=="": errors.append(f"{label}: missing {field}")
        if r.get("company") not in COMPANIES:errors.append(f"{label}: unknown company")
        if r.get('company')=='Storebrand' and r.get('scope')=='norway' and r.get('quarter')==4:
            errors.append(f'{label}: Storebrand Forsikring AS has no standalone Q4 report; Q4 must remain blank')
        if r.get("metric") not in METRICS:errors.append(f"{label}: unknown metric")
        if r.get("source_type")=="official_investor_tables":
            if r.get("company") not in ("Tryg","Gjensidige") or r.get("scope")!="norway":
                errors.append(f"{label}: investor tables permitted only for Tryg/Gjensidige Norway")
            if not str(r.get("source_url","")).lower().split("?")[0].endswith(".xlsx"):
                errors.append(f"{label}: investor tables must be XLSX")
            if not r.get("source_sheet") or not r.get("source_cell") or not r.get("source_document_url"):
                errors.append(f"{label}: Excel provenance requires sheet, cell and corresponding PDF")
        elif r.get("source_type")!="official_quarterly_report":errors.append(f"{label}: source is not official quarterly report")
        url=str(r.get("source_url","")).lower()
        if any(term in url for term in ("press-release","pressemelding","analyst-presentation","investor-presentation")):
            errors.append(f"{label}: prohibited non-quarterly-report document URL")
        if r.get("status","reported")=="calculated" and not r.get("calculation"):
            errors.append(f"{label}: calculated value missing calculation provenance")
        if not str(r.get("source_url","")).startswith("https://"):errors.append(f"{label}: source URL must be HTTPS")
        if r.get("source_type")=="official_quarterly_report" and (type(r.get("source_page")) is not int or r["source_page"]<1):errors.append(f"{label}: invalid source page")
        if type(r.get("quarter")) is not int or r["quarter"] not in (1,2,3,4):errors.append(f"{label}: invalid quarter")
        if type(r.get("year")) is not int or r["year"]<2020:errors.append(f"{label}: invalid year")
        if r.get("status","reported") not in ("reported","calculated","provisional"):errors.append(f"{label}: invalid status")
        if r.get("scope")=="norway" and r.get("source_scope")=="group":errors.append(f"{label}: group value mislabeled Norway")
        if r.get("scope") not in ("norway","group","reported_segment"):errors.append(f"{label}: unknown scope")
        if r.get("company")=="Sampo" and r.get("scope")=="reported_segment" and r.get("segment") not in ("Private Nordic","Nordic Commercial"):
            errors.append(f"{label}: unrecognized Sampo segment")
        if r.get("period_type") not in ("quarter","ytd"):errors.append(f"{label}: unknown period type")
        if type(r.get("value")) not in (int,float) or not math.isfinite(r["value"]):errors.append(f"{label}: nonfinite value")
        key=tuple(r.get(k) for k in ("company","year","quarter","scope","period_type","metric"))+(r.get("segment") if r.get("scope")=="reported_segment" else None,)
        if key in seen:errors.append(f"{label}: duplicate {key}")
        seen[key]=r
    for key,r in seen.items():
        company,year,quarter,scope,period,metric,segment=key
        if metric=="combined_ratio":
            loss=seen.get((company,year,quarter,scope,period,"loss_ratio",segment))
            expense=seen.get((company,year,quarter,scope,period,"expense_ratio",segment))
            if loss and expense:
                # Storebrand Group insurance segment publishes rounded whole-percent
                # ratios. Three independently rounded figures can differ by 1.5 pp.
                # Other entities and more precise ratios keep the strict tolerance.
                vals = (r["value"], loss["value"], expense["value"])
                rounded_group = (company == "Storebrand" and scope == "group"
                                 and all(type(v) in (int, float) and float(v).is_integer() for v in vals))
                tolerance = 1.5 if rounded_group else 0.25
                if abs(vals[0] - vals[1] - vals[2]) > tolerance + 1e-9:
                    errors.append(f"{company} {year} Q{quarter} {scope} {period}: combined ratio mismatch")
        if metric=="insurance_revenue":
            prior=seen.get((company,year-1,quarter,scope,period,metric,segment)) if type(year)==int else None
            if prior and prior["value"]>0:
                value=(r["value"]/prior["value"]-1)*100
                reported=seen.get((company,year,quarter,scope,period,"insurance_revenue_growth",segment))
                if reported and abs(reported["value"]-value)>0.15:
                    warnings.append(f"{company} {year} Q{quarter} {scope} {period}: reported growth differs from computed growth")
                calculated.append({"company":company,"year":year,"quarter":quarter,"scope":scope,"period_type":period,"metric":"insurance_revenue_growth","value":value,"calculation":"(current/prior-1)*100","inputs":[r["source_url"],prior["source_url"]],"status":"calculated_from_quarterly_reports"})
    # A single ROE observation must never count as full coverage of a company.
    expected_metrics=("insurance_revenue","insurance_service_result","combined_ratio","loss_ratio","expense_ratio","return_on_equity","solvency_ratio")
    coverage={}
    for company in sorted(COMPANIES):
        coverage[company]={}
        for scope in ("norway","group"):
            coverage[company][scope]={}
            for period in ("quarter","ytd"):
                coverage[company][scope][period]={}
                for metric in expected_metrics:
                    matched=[r for r in records if r.get("company")==company and r.get("scope")==scope and r.get("period_type")==period and r.get("metric")==metric and r.get("year")==2026 and r.get("quarter")==2]
                    coverage[company][scope][period][metric]="reported" if matched else "missing_or_not_applicable"
    complete=all(coverage[c][scope][period][metric]=="reported" for c in COMPANIES for scope in ("norway","group") for period in ("quarter","ytd") for metric in expected_metrics)
    for company in sorted(COMPANIES):
        if not any(r.get("company")==company for r in records):
            warnings.append(f"{company}: no observations in unified model")
    missing_cells=[
        {"company":c,"scope":scope,"period_type":period,"metric":metric,"year":2026,"quarter":2}
        for c in sorted(COMPANIES)
        for scope in ("norway","group")
        for period in ("quarter","ytd")
        for metric in expected_metrics
        if coverage[c][scope][period][metric]!="reported"
    ]
    return {"missing_cells":missing_cells,"ok":not errors,"release_ready":not errors and complete,"observation_count":len(records),"derived_growth":calculated,"errors":errors,"warnings":warnings,"coverage_complete":complete,"coverage_matrix":coverage,"coverage_definition":"All seven metrics for Q2 2026, both Norway and group, quarter and YTD; not-applicable must be explicitly modelled before release"}
def main():
    result=audit(json.loads(DATA.read_text()))
    OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({"ok":result["ok"],"coverage_complete":result["coverage_complete"],"observation_count":result["observation_count"],"errors":result["errors"],"warnings":result["warnings"]},ensure_ascii=False,indent=2))
    if not result["ok"]:sys.exit(1)
    # In strict mode, incomplete coverage blocks investor-grade release.
    if "--require-coverage" in sys.argv and not result["coverage_complete"]:sys.exit(2)
if __name__=="__main__":main()
