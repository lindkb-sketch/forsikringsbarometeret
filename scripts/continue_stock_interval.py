#!/usr/bin/env python3
"""Run a guarded next quote attempt when the prior stock job is 15min old.

The stock job explicitly sends repository_dispatch with its run ID. This waiter
is outside the shared Pages lock. A newer event cancels the old waiter, while
the existing guarded dispatcher avoids duplicates and closed exchanges.
GitHub delays are still possible: this is not a hard 15-minute SLA.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import time
import urllib.request

from check_stock_schedule import check as guarded_dispatch
from stock_market_window import should_poll

UTC = dt.timezone.utc
INTERVAL = dt.timedelta(minutes=15)
MAX_WAIT_SECONDS = 16 * 60
STOCK_WORKFLOW = 'Oppdater forsinkede aksjekurser (egen pipeline)'


def parse_start(value: str) -> dt.datetime:
    if not isinstance(value, str) or not value.strip():
        raise ValueError('Missing previous stock workflow created_at')
    try:
        stamp = dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError as exc:
        raise ValueError('Invalid previous stock workflow created_at') from exc
    if stamp.tzinfo is None:
        raise ValueError('Stock workflow timestamp has no timezone')
    return stamp.astimezone(UTC)


def fetch_stock_created_at(run_id: str, repo: str, token: str, *, opener=urllib.request.urlopen) -> str:
    if not re.fullmatch(r'[1-9][0-9]*', str(run_id)):
        raise ValueError('Invalid source stock run ID')
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repo):
        raise ValueError('Invalid repository')
    if not token:
        raise ValueError('Missing repository token')
    url = f'https://api.github.com/repos/{repo}/actions/runs/{run_id}'
    req = urllib.request.Request(url, headers={
        'Accept': 'application/vnd.github+json',
        'X-GitHub-Api-Version': '2022-11-28',
        'User-Agent': 'Forsikringsbarometeret-stock-timer',
        'Authorization': 'Bearer ' + token})
    with opener(req, timeout=25) as response:
        payload = json.load(response)
    if not isinstance(payload, dict) or payload.get('id') != int(run_id):
        raise ValueError('Stock source run ID mismatch')
    if (payload.get('name') != STOCK_WORKFLOW or
            payload.get('head_branch') != 'main' or
            payload.get('repository', {}).get('full_name') != repo):
        raise ValueError('Stock source is not the expected main-branch workflow')
    value = payload.get('created_at')
    parse_start(value)
    return value


def continue_interval(previous_created_at: str, *, clock=None, sleeper=time.sleep,
                      dispatcher=guarded_dispatch) -> str:
    clock = clock or (lambda: dt.datetime.now(UTC))
    last = parse_start(previous_created_at)
    due = last + INTERVAL
    now = clock()
    if now.tzinfo is None:
        raise ValueError('Current time must be timezone-aware')
    if not should_poll(due) and now < due:
        print('STOCK_INTERVAL next slot outside Nordic market window; stopping')
        return 'closed'
    remaining = max(0, (due - now).total_seconds())
    if remaining > MAX_WAIT_SECONDS:
        raise ValueError('Stock run timestamp is unreasonably far in the future')
    if remaining:
        print(f'STOCK_INTERVAL wait {remaining:.1f}s until {due.isoformat()}', flush=True)
        sleeper(remaining)
    current = clock()
    if not should_poll(current):
        print('STOCK_INTERVAL outside Nordic market hours; stopping')
        return 'closed'
    return dispatcher(now=current)


if __name__ == '__main__':
    source = fetch_stock_created_at(
        os.environ['SOURCE_STOCK_RUN_ID'], os.environ['GITHUB_REPOSITORY'],
        os.environ['GITHUB_TOKEN'])
    continue_interval(source)
