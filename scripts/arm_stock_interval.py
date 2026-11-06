#!/usr/bin/env python3
"""Explicitly arm a stock follow-up via repository_dispatch, never workflow_run.

GitHub's GITHUB_TOKEN-created workflow_dispatch runs do not reliably generate
workflow_run events. repository_dispatch *does* create a new workflow run.
This action happens at the end of the stock job and takes no Pages lock time
beyond its short API call; the separate waiter has no Pages lock.
"""
from __future__ import annotations

import json
import os
import re
import urllib.request

EVENT = 'stock_next_check'


def arm(repo: str, run_id: str, token: str, *, opener=urllib.request.urlopen) -> dict:
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repo):
        raise ValueError('Invalid repository')
    if not re.fullmatch(r'[1-9][0-9]*', str(run_id)):
        raise ValueError('Invalid stock run ID')
    if not token:
        raise ValueError('Missing repository token')
    payload = {'event_type': EVENT, 'client_payload': {'source_run_id': str(run_id)}}
    req = urllib.request.Request(
        f'https://api.github.com/repos/{repo}/dispatches',
        data=json.dumps(payload).encode('utf-8'),
        method='POST',
        headers={'Accept': 'application/vnd.github+json',
                 'X-GitHub-Api-Version': '2022-11-28',
                 'Content-Type': 'application/json',
                 'User-Agent': 'Forsikringsbarometeret-stock-requeue',
                 'Authorization': 'Bearer ' + token})
    with opener(req, timeout=25) as response:
        if response.status != 204:
            raise ValueError('Unexpected repository_dispatch HTTP status')
    print('STOCK_INTERVAL_ARMED repository_dispatch for run ' + str(run_id), flush=True)
    return payload


if __name__ == '__main__':
    arm(os.environ['GITHUB_REPOSITORY'], os.environ['GITHUB_RUN_ID'], os.environ['GITHUB_TOKEN'])
