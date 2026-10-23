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
    print("::error::Scheduled 30-minute importer may have stopped; inspect update.yml and GitHub Actions")
    sys.exit(1)
