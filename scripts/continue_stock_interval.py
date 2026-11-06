#!/usr/bin/env python3
"""Continue intraday stock refreshes when GitHub silently drops cron events.

Each *completed* quote workflow triggers this independent, unlocked keeper
through ``workflow_run``. It waits until 15 minutes after that run was created,
then invokes the existing guarded dispatcher. A newer run cancels the old
keeper, while the dispatch guard refuses duplicate or out-of-hours jobs.

This increases reliability without an external scheduler. It cannot create a
hard real-time SLA: GitHub may also delay or cancel workflow_run jobs.
"""
from __future__ import annotations

import datetime as dt
import os
import time

from check_stock_schedule import check as guarded_dispatch
from stock_market_window import should_poll

UTC = dt.timezone.utc
INTERVAL = dt.timedelta(minutes=15)
MAX_WAIT_SECONDS = 16 * 60


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


def continue_interval(previous_created_at: str, *, clock=None, sleeper=time.sleep,
                      dispatcher=guarded_dispatch) -> str:
    clock = clock or (lambda: dt.datetime.now(UTC))
    last = parse_start(previous_created_at)
    due = last + INTERVAL
    now = clock()
    if now.tzinfo is None:
        raise ValueError('Current time must be timezone-aware')
    # Avoid holding a runner into the weekend or past the market close.
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
    # The existing watchdog checks *all* recent/active runs via GitHub API.
    # When a normal scheduled run arrived during sleep this is a no-op.
    return dispatcher(now=current)


if __name__ == '__main__':
    continue_interval(os.environ['LAST_STOCK_RUN_CREATED_AT'])
