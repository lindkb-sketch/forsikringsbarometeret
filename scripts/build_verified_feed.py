#!/usr/bin/env python3
"""Publish only validated, report-sourced observations as a stable static feed."""
import json,os,tempfile,sys
from pathlib import Path
from audit_financials import audit,DATA,ROOT
OUT=ROOT/"data"/"verified_financial_feed.json"
def build(data):
    result=audit(data)
    if not result["ok"]:raise ValueError("Financial source validation failed: "+"; ".join(result["errors"]))
    observations=[r for r in data["observations"] if r.get("status","reported") in ("reported","calculated") and not (r.get("scope")=="norway" and r.get("period_type")!="quarter")]
    observations.sort(key=lambda r:(r["company"],r["year"],r["quarter"],r["scope"],r["period_type"],r["metric"]))
    return {"schema_version":1,"observations":observations,"coverage_complete":result["coverage_complete"],"observation_count":len(observations),"note":"Only reported, source-validated official quarterly reports and approved geographical workbooks; missing observations are not zero"}
def publish(out=OUT,data_path=DATA):
    data=json.loads(Path(data_path).read_text(encoding="utf-8"))
    result=build(data)
    out=Path(out);out.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix=".verified-",suffix=".json",dir=out.parent)
    try:
        with os.fdopen(fd,"w",encoding="utf-8") as f:json.dump(result,f,ensure_ascii=False,indent=2);f.write("\n")
        os.replace(tmp,out)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)
    return result
if __name__=="__main__":
    result=publish()
    print(f"Published {result['observation_count']} source-validated observations; complete={result['coverage_complete']}")
