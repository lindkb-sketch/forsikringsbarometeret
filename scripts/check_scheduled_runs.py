#!/usr/bin/env python3
"""Verify the scheduled publication checker actually runs, not just that cron exists."""
import json,os,sys,urllib.request
from datetime import datetime,timezone
REPO=os.environ.get("GITHUB_REPOSITORY","lindkb-sketch/forsikringsbarometeret")
API=f"https://api.github.com/repos/{REPO}/actions/workflows/update.yml/runs?per_page=20&event=schedule"
req=urllib.request.Request(API,headers={"Accept":"application/vnd.github+json","User-Agent":"Forsikringsbarometeret-schedule-watch","Authorization":"Bearer "+os.environ["GITHUB_TOKEN"]})
with urllib.request.urlopen(req,timeout=25) as response:
    history=json.load(response)["workflow_runs"]
scheduled=[x for x in history if x.get("event")=="schedule"]
now=datetime.now(timezone.utc)
latest=max((datetime.fromisoformat(x["created_at"].replace("Z","+00:00")) for x in scheduled),default=None)
minutes=(now-latest).total_seconds()/60 if latest else None
print(json.dumps({"scheduled_runs_in_recent_history":len(scheduled),
                  "last_scheduled_run":latest.isoformat() if latest else None,
                  "minutes_since_last":round(minutes,1) if minutes is not None else None}))
if latest is None or minutes>95:
    # GitHub may delay scheduled workflows. Recover a missed run, but never
    # launch a duplicate when an update workflow is already active.
    api=f"https://api.github.com/repos/{REPO}/actions/workflows/update.yml/runs?per_page=10"
    active_req=urllib.request.Request(api,headers={"Accept":"application/vnd.github+json","User-Agent":"Forsikringsbarometeret-schedule-watch","Authorization":"Bearer "+os.environ["GITHUB_TOKEN"]})
    with urllib.request.urlopen(active_req,timeout=25) as response:
        active=json.load(response)["workflow_runs"]
    underway=[x for x in active if x.get("status") in ("queued","pending","waiting","in_progress","requested")]
    if underway:
        print("::warning::Scheduled importer is delayed, but an update is already active; no duplicate dispatched.")
    else:
        request=urllib.request.Request(f"https://api.github.com/repos/{REPO}/actions/workflows/update.yml/dispatches",
           data=json.dumps({"ref":"main"}).encode("utf-8"),method="POST",
           headers={"Accept":"application/vnd.github+json","Content-Type":"application/json",
                    "User-Agent":"Forsikringsbarometeret-schedule-watch",
                    "Authorization":"Bearer "+os.environ["GITHUB_TOKEN"]})
        with urllib.request.urlopen(request,timeout=25):
            pass
        print("::warning::Missed half-hour run; requested a fresh publication workflow.")
    sys.exit(1)
