#!/usr/bin/env python3
"""Continue intraday stock refreshes if GitHub silently drops cron events.

After a completed quote workflow, this independent keeper waits until roughly
15 minutes after that run's start, then invokes the existing duplicate-safe
GitHub dispatcher. It never holds the Pages publication lock and does not
change price data itself. This is best-effort, not a hard timing guarantee.
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
    # Do not retain an idle runner into the weekend or past the last
    # Nordic market's broad weekday quote window.
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
    # A newer scheduled or manually triggered stock workflow makes this a
    # no-op. The API guard refuses duplicates and fails closed on errors.
    return dispatcher(now=current)


if __name__ == '__main__':
    continue_interval(os.environ['LAST_STOCK_RUN_CREATED_AT'])
