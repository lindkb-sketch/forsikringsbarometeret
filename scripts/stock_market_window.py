#!/usr/bin/env python3
"""Trading-window guard for the independent, delayed stock-data refresh.

This is a scheduler guard only, not an exchange holiday calendar or proof
that a market is currently trading. The quote feed supplies the timestamps.
"""
import datetime as dt
import os
from zoneinfo import ZoneInfo

# Broad market windows include publication just after the last trade.
# Holidays and actual observed prices are handled by the source and quality gate.
WINDOWS=(
    ('Europe/Oslo',dt.time(8,45),dt.time(16,45)),
    ('Europe/Copenhagen',dt.time(8,45),dt.time(17,20)),
    ('Europe/Helsinki',dt.time(9,45),dt.time(18,45)),
)

def should_poll(now=None):
    now=now or dt.datetime.now(dt.timezone.utc)
    if now.tzinfo is None:raise ValueError('Datetime must be timezone-aware')
    for timezone,start,end in WINDOWS:
        local=now.astimezone(ZoneInfo(timezone))
        if local.weekday()<5 and start<=local.time().replace(tzinfo=None)<=end:
            return True
    return False

if __name__=='__main__':
    active=should_poll()
    output=os.environ.get('GITHUB_OUTPUT')
    if output:
        with open(output,'a',encoding='utf-8') as f:
            f.write('active='+str(active).lower()+'\n')
    print('MARKET_POLL_WINDOW',str(active).lower(),
          'scheduled poll is not a claim of exchange trading or real-time quotes')
