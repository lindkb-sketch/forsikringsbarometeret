#!/usr/bin/env python3
"""GitHub-only backup for scheduled stock refreshes, without duplicate runs.

GitHub's stock workflow owns quote validation and Pages deployment. This
watchdog only dispatches it when a Nordic market is active and a recent run
is missing. Scheduled triggers are best-effort, not a guaranteed 15-minute SLA.
"""
import json
import os
import urllib.request
from datetime import datetime,timezone
from stock_market_window import should_poll

ACTIVE={'queued','pending','waiting','in_progress','requested'}
MAX_RECENT_MINUTES=14

def github_request(url,token,data=None):
    headers={'Accept':'application/vnd.github+json',
             'X-GitHub-Api-Version':'2022-11-28',
             'User-Agent':'Forsikringsbarometeret-stock-watchdog',
             'Authorization':'Bearer '+token}
    if data is not None:headers['Content-Type']='application/json'
    request=urllib.request.Request(url,headers=headers,
        data=json.dumps(data).encode('utf-8') if data is not None else None,
        method='POST' if data is not None else 'GET')
    with urllib.request.urlopen(request,timeout=25) as response:
        return None if data is not None else json.load(response)

def check(now=None,fetch=github_request,token=None,repo=None):
    now=now or datetime.now(timezone.utc)
    if now.tzinfo is None:raise ValueError('Clock must be timezone-aware')
    if not should_poll(now):
        print('STOCK_WATCHDOG outside Nordic weekday market windows; skipped')
        return 'closed'
    repo=repo or os.environ.get('GITHUB_REPOSITORY','lindkb-sketch/forsikringsbarometeret')
    token=token or os.environ['GITHUB_TOKEN']
    api='https://api.github.com/repos/'+repo+'/actions/workflows/stock-prices.yml'
    # Fail closed on API errors; never dispatch without trustworthy run history.
    payload=fetch(api+'/runs?per_page=30',token)
    runs=payload.get('workflow_runs') if isinstance(payload,dict) else None
    if not isinstance(runs,list):raise ValueError('Invalid GitHub workflow-run response')
    for run in runs:
        if not isinstance(run,dict):raise ValueError('Invalid GitHub run entry')
        if run.get('status') in ACTIVE:
            print('STOCK_WATCHDOG stock refresh already active; no duplicate')
            return 'active'
        created=run.get('created_at')
        if not isinstance(created,str):continue
        try:instant=datetime.fromisoformat(created.replace('Z','+00:00'))
        except ValueError:continue
        if instant.tzinfo is None:continue
        age=(now-instant).total_seconds()/60
        if -2<=age<MAX_RECENT_MINUTES:
            print(f'STOCK_WATCHDOG recent stock attempt ({age:.1f} min); no duplicate')
            return 'recent'
    fetch(api+'/dispatches',token,{'ref':'main'})
    print('::warning::STOCK_WATCHDOG no recent stock run; dispatched stock-prices.yml')
    return 'dispatched'

if __name__=='__main__':check()
