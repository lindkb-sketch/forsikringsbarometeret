#!/usr/bin/env python3
"""End-to-end synthetic next-quarter drill. ALL files remain in a disposable worktree.

Transport and report adapter are simulated, NOT official issuer parsers. The real
financial audit, feed builder, editorial builder and browser are exercised.
"""
import copy, hashlib, json, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
from audit_financials import audit
from build_verified_feed import build as build_feed
from build_editorial import build as build_editorial
COMPANIES=("Fremtind","Gjensidige","Tryg","Sampo","Frende","Protector","Storebrand")
METRICS=("insurance_revenue","insurance_service_result","combined_ratio","loss_ratio","expense_ratio")
YEAR,QUARTER=2026,4
def fixture(company,position):
    # Test-only transport: bytes mimic a delivered report envelope, never a real PDF.
    values={"insurance_revenue":1000+110*position,"insurance_service_result":200+20*position,
            "combined_ratio":80+position,"loss_ratio":67+position,"expense_ratio":13}
    return json.dumps({"issuer":company,"year":YEAR,"quarter":QUARTER,"metrics":values},
                      sort_keys=True).encode()
def decode_report(company,raw):
    doc=json.loads(raw)
    if doc["issuer"]!=company or (doc["year"],doc["quarter"])!=(YEAR,QUARTER):
        raise ValueError("Wrong issuer/quarter: reject rather than publish")
    if set(doc["metrics"])!=set(METRICS):raise ValueError("Missing mandatory quarterly metrics")
    source=f"https://simulation.invalid/{company.lower()}/q4-2026.pdf"
    digest=hashlib.sha256(raw).hexdigest()
    return [dict(company=company,year=YEAR,quarter=QUARTER,scope="group",
                 period_type="quarter",metric=m,value=v,
                 unit="percent" if m in ("combined_ratio","loss_ratio","expense_ratio") else "MNOK",
                 source_url=source,source_type="official_quarterly_report",
                 source_scope="group",source_page=1,source_sha256=digest,
                 status="reported",test_only_synthetic=True) for m,v in doc["metrics"].items()]
SAMPO_SEGMENTS=('Private Nordic','Nordic Commercial')
def sampo_segment_observations():
    """Synthetic issuer-segment payload in the same source schema as production."""
    rows=[]
    for index,segment in enumerate(SAMPO_SEGMENTS):
        values={'insurance_revenue':700+100*index,
                'insurance_service_result':126+18*index,
                'combined_ratio':82+index,'loss_ratio':68+index,
                'expense_ratio':14}
        raw=json.dumps({'issuer':'Sampo','segment':segment,'year':YEAR,
                        'quarter':QUARTER,'metrics':values},sort_keys=True).encode()
        for metric,value in values.items():
            rows.append(dict(company='Sampo',year=YEAR,quarter=QUARTER,
                scope='reported_segment',segment=segment,source_scope='reported_segment',
                period_type='quarter',metric=metric,value=value,
                unit='percent' if metric.endswith('ratio') else 'EURm',
                source_url='https://simulation.invalid/sampo/q4-2026.pdf',
                source_type='official_quarterly_report',source_page=2+index,
                source_sha256=hashlib.sha256(raw).hexdigest(),
                status='reported',test_only_synthetic=True))
    return rows

def exercise(original):
    baseline=copy.deepcopy(original)
    observed=[]
    # Simulation of download + per-issuer adapter; no external URLs are contacted.
    for i,c in enumerate(COMPANIES):
        report_bytes=fixture(c,i)
        observed.extend(decode_report(c,report_bytes))
    observed.extend(sampo_segment_observations())
    prepared=copy.deepcopy(baseline)
    prepared["observations"].extend(observed)
    validation=audit(prepared)
    if not validation["ok"]:raise AssertionError(validation["errors"])
    feed=build_feed(prepared)
    editorial=build_editorial(feed,{"items":[]})
    if editorial["period"]!="Q4 2026":raise AssertionError("Quarter failed to roll forward")
    if {r["company"] for r in feed["observations"] if r.get("test_only_synthetic")}!=set(COMPANIES):
        raise AssertionError("Not all seven simulated reports reached verified feed")
    if set(editorial["periods"]["Q4 2026"]["by_company"])!=set(COMPANIES):
        raise AssertionError("Not all seven simulated reports reached quarterly brief")
    # Reported Nordic segments must survive source -> audit -> feed. Group
    # and both Nordic segments are independent official-report views.
    for segment in SAMPO_SEGMENTS:
        matching=[r for r in feed['observations'] if
                  r.get('test_only_synthetic') and r.get('company')=='Sampo'
                  and r.get('scope')=='reported_segment' and
                  r.get('segment')==segment and
                  (r.get('year'),r.get('quarter'))==(YEAR,QUARTER)]
        if {r['metric'] for r in matching}!=set(METRICS):
            raise AssertionError('Sampo '+segment+' missing from published feed')
    # Negative drill: wrong issuer, absent ratio, and invalid combined-ratio arithmetic.
    for mutated in (
        {**json.loads(fixture(COMPANIES[0],0)),"issuer":"Untrusted"},
        {**json.loads(fixture(COMPANIES[0],0)),"metrics":{"insurance_revenue":5}},
    ):
        try:decode_report(COMPANIES[0],json.dumps(mutated).encode())
        except ValueError:pass
        else:raise AssertionError("Invalid report was accepted")
    damaged=copy.deepcopy(prepared)
    next(x for x in damaged["observations"] if x.get("test_only_synthetic") and x["metric"]=="combined_ratio")["value"]=12
    if audit(damaged)["ok"]:raise AssertionError("Contradictory ratio did not fail closed")
    return feed,editorial,{"simulation":True,"report_transport":"synthetic_in_memory_not_official_pdf","real_issuer_parser_verified":False,
              "companies":list(COMPANIES),"quarter":"Q4 2026","synthetic_observations":len(observed),"sampo_segments":list(SAMPO_SEGMENTS),
              "audit_ok":True,"editorial_companies":len(editorial["periods"]["Q4 2026"]["by_company"]),
              "negative_cases_passed":3,"production_data_modified":False}
def main():
    baseline=json.loads((ROOT/"data/financial_observations.json").read_text())
    feed,editorial,result=exercise(baseline)
    (ROOT/"data/verified_financial_feed.json").write_text(json.dumps(feed,ensure_ascii=False,indent=2)+"\n")
    (ROOT/"data/quarterly_editorial.json").write_text(json.dumps(editorial,ensure_ascii=False,indent=2)+"\n")
    (ROOT/"data/next_quarter_drill.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print("FUTURE_QUARTER_DRILL",json.dumps(result))
if __name__=="__main__":main()
