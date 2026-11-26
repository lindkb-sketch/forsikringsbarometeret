#!/usr/bin/env python3
"""Bounded GitHub-hosted backup for a delayed finance schedule.

A completed production run requests one timer. It never holds the shared
Pages publication lock, and the same history guard as the independent
scheduler prevents overlapping finance imports.
"""
import datetime as dt
import os
import time
import re
from check_stock_schedule import github_request
from external_scheduler import finance_check,FINANCE_INTERVAL,REPO

UTC=dt.timezone.utc

def arm(run_id,token,fetch=github_request):
    if not re.fullmatch(r'[1-9]\d*',str(run_id)):raise ValueError('Invalid finance run ID')
    fetch('https://api.github.com/repos/'+REPO+'/dispatches',token,
          {'event_type':'finance_next_check','client_payload':{'source_run_id':str(run_id)}})
    print('FINANCE_NEXT_CHECK_ARMED',run_id,flush=True)

def wait_next(run_id,token,*,fetch=github_request,clock=lambda:dt.datetime.now(UTC),sleep=time.sleep):
    if not re.fullmatch(r'[1-9]\d*',str(run_id)):raise ValueError('Invalid finance run ID')
    source=fetch('https://api.github.com/repos/'+REPO+'/actions/runs/'+str(run_id),token)
    if str(source.get('id'))!=str(run_id) or source.get('head_branch')!='main' or source.get('path','').split('@')[0]!='.github/workflows/update.yml':
        raise ValueError('Finance timer source is not a main finance workflow')
    started=dt.datetime.fromisoformat(source['created_at'].replace('Z','+00:00'))
    now=clock()
    if started.tzinfo is None or started>now+dt.timedelta(minutes=2):raise ValueError('Invalid finance source timestamp')
    due=started+dt.timedelta(minutes=FINANCE_INTERVAL,seconds=5)
    seconds=max(0,(due-now).total_seconds())
    if seconds>32*60:raise ValueError('Unexpected finance timer duration')
    print('FINANCE_NEXT_CHECK_WAIT_SECONDS',int(seconds),flush=True)
    if seconds:sleep(seconds)
    # The source may still be finishing its final arm job. Check at most
    # three extra times, with short waits, rather than starting duplicates.
    for attempt in range(3):
        status=finance_check(clock(),token,fetch=fetch,sleeper=sleep)
        print('FINANCE_NEXT_CHECK',status,flush=True)
        if status!='active' or attempt==2:return status
        sleep(45)
    raise RuntimeError('Unreachable timer state')

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument('mode',choices=('arm','wait'))
    args=parser.parse_args()
    token=os.environ['GITHUB_TOKEN']
    if args.mode=='arm':arm(os.environ['GITHUB_RUN_ID'],token)
    else:wait_next(os.environ['SOURCE_FINANCE_RUN_ID'],token)
