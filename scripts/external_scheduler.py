#!/usr/bin/env python3
"""One bounded tick for a scheduler outside GitHub Actions.

Read workflow history, request a missing finance/stock run, and exit.
No credentials in source, no financial edits and no investor certification.
"""
import datetime as dt
import json
import os
import re
import time
import urllib.error

from check_stock_schedule import ACTIVE, check as check_stock, github_request

UTC = dt.timezone.utc
REPO = "lindkb-sketch/forsikringsbarometeret"
FINANCE_INTERVAL = 30
RECOVERY_INTERVAL = 10
STALE_ACTIVE = 60

def age(now, row):
    stamp = dt.datetime.fromisoformat(row["created_at"].replace("Z", "+00:00"))
    if stamp.tzinfo is None or stamp > now + dt.timedelta(minutes=2):
        raise ValueError("Invalid workflow timestamp")
    return (now - stamp).total_seconds()/60

def finance_check(now, token, *, fetch=github_request, sleeper=time.sleep,
                  retries=3, dry_run=False):
    api = "https://api.github.com/repos/"+REPO+"/actions/workflows/update.yml"
    payload = fetch(api+"/runs?branch=main&per_page=30", token)
    rows = payload.get("workflow_runs") if isinstance(payload,dict) else None
    if not isinstance(rows,list):
        raise ValueError("Invalid finance workflow response")
    if any(not isinstance(r,dict) or r.get("head_branch")!="main"
           or not isinstance(r.get("status"),str) for r in rows):
        raise ValueError("Invalid or non-main workflow run")
    active = [r for r in rows if r["status"] in ACTIVE]
    if active:
        if any(age(now,r)>STALE_ACTIVE for r in active):
            raise RuntimeError("Finance workflow active for over 60 minutes; inspect queue/job")
        return "active"
    recent = sorted(rows,key=lambda r:age(now,r))
    if recent:
        last = recent[0]
        last_age = age(now,last)
        # An accepted recovery or push can stand in for a scheduled attempt,
        # but a failed attempt must not be mistaken for a success.
        limit = RECOVERY_INTERVAL if last.get("conclusion") not in ("success",None) else FINANCE_INTERVAL
        if last_age < limit:
            return "recent"
    if dry_run:
        return "would_dispatch"
    try:
        fetch(api+"/dispatches",token,{"ref":"main"})
    except urllib.error.HTTPError as exc:
        if exc.code not in (500,502,503,504) or retries<=1:
            raise
        # POST may have been accepted before the 5xx was returned. Re-read
        # history before attempting another POST. Never blindly repeat.
        sleeper(15)
        return finance_check(now+dt.timedelta(seconds=15),token,fetch=fetch,
                             sleeper=sleeper,retries=retries-1,dry_run=dry_run)
    return "dispatched"

def tick(now,token,*,fetch=github_request,sleeper=time.sleep,dry_run=False):
    if now.tzinfo is None:
        raise ValueError("Timezone-aware clock required")
    if not token:
        raise ValueError("Missing repository-scoped scheduler credential")
    results={}
    try:
        results["finance"]=finance_check(now,token,fetch=fetch,sleeper=sleeper,dry_run=dry_run)
    except Exception as exc:
        # Do not log raw HTTP bodies or headers that might include credentials.
        results["finance"]="error:"+type(exc).__name__
    try:
        def stock_fetch(url,auth,data=None):
            if dry_run and data is not None:
                return None
            return fetch(url,auth,data)
        result=check_stock(now,fetch=stock_fetch,token=token,repo=REPO,sleeper=sleeper)
        results["stock"]="would_dispatch" if dry_run and result=="dispatched" else result
    except Exception as exc:
        results["stock"]="error:"+type(exc).__name__
    return results

def main():
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument("--dry-run",action="store_true")
    args=parser.parse_args()
    result=tick(dt.datetime.now(UTC),os.environ.get("GITHUB_TOKEN"),dry_run=args.dry_run)
    print(json.dumps({"scheduler":"external","dry_run":args.dry_run,"results":result}),flush=True)
    if any(v.startswith("error:") for v in result.values()):
        raise SystemExit(1)

if __name__=="__main__":
    main()
