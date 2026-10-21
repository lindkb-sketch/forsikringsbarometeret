#!/usr/bin/env python3
"""Import a batch of observations from official quarterly reports.
Atomic writes: a failed validation never changes the production dataset.
Usage: python scripts/import_quarterly_report.py incoming.json
"""
import json,sys,os,tempfile
from pathlib import Path
from audit_financials import audit,ROOT,DATA
KEYS=("company","year","quarter","scope","period_type","metric")
def import_batch(path,commit=True):
    existing=json.loads(DATA.read_text(encoding="utf-8"))
    incoming=json.loads(Path(path).read_text(encoding="utf-8"))
    if incoming.get("source_policy") not in ("official_quarterly_report_only","official_reports_and_geographic_workbooks"):
        raise ValueError("Import must declare official_quarterly_report_only")
    new=incoming.get("observations")
    if not isinstance(new,list) or not new:
        raise ValueError("Import must contain at least one observation")
    # Reject batch errors before merging, and refuse to silently overwrite
    # previously published figures. Corrections require explicit review.
    batch=audit({"observations":new})
    if not batch["ok"]:raise ValueError("Invalid batch: "+"; ".join(batch["errors"]))
    keys={tuple(r.get(k) for k in KEYS) for r in existing["observations"]}
    collisions=[tuple(r.get(k) for k in KEYS) for r in new if tuple(r.get(k) for k in KEYS) in keys]
    if collisions:raise ValueError(f"Existing observations require manual correction review: {collisions}")
    merged={**existing,"observations":existing["observations"]+new}
    result=audit(merged)
    if not result["ok"]:raise ValueError("Merged data failed audit: "+"; ".join(result["errors"]))
    if commit:
        fd,tmp=tempfile.mkstemp(prefix=".financial-",suffix=".json",dir=DATA.parent)
        try:
            with os.fdopen(fd,"w",encoding="utf-8") as f:
                json.dump(merged,f,ensure_ascii=False,indent=2);f.write("\\n")
            os.replace(tmp,DATA)
        finally:
            if os.path.exists(tmp):os.unlink(tmp)
    return result
if __name__=="__main__":
    if len(sys.argv)!=2:
        sys.exit("Usage: python scripts/import_quarterly_report.py incoming.json")
    try:
        r=import_batch(sys.argv[1])
    except (ValueError,KeyError,json.JSONDecodeError) as e:
        print(f"IMPORT BLOCKED: {e}",file=sys.stderr);sys.exit(1)
    print(f"Imported; now {r['observation_count']} observations. Coverage complete: {r['coverage_complete']}")
