#!/usr/bin/env python3
"""Confirm stock-only Pages deployment reflects the exact committed price JSON."""
import json
import time
import urllib.request
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
LOCAL=ROOT/'data/stock_prices.json'
PUBLIC='https://lindkb-sketch.github.io/forsikringsbarometeret/data/stock_prices.json'

def verify(attempts=12):
    expected=json.loads(LOCAL.read_text(encoding='utf-8'))
    for attempt in range(attempts):
        try:
            req=urllib.request.Request(PUBLIC+'?verify='+str(time.time_ns()),
                headers={'Cache-Control':'no-cache','User-Agent':'Forsikringsbarometeret-Stock-Check/1.0'})
            with urllib.request.urlopen(req,timeout=25) as resp:
                if resp.status!=200:raise ValueError('Public stock JSON is not HTTP 200')
                actual=json.load(resp)
            if actual!=expected:
                raise ValueError('Public stock prices differ from committed source')
            print('PUBLIC_STOCK_FEED_VALID',expected.get('updated_at'),
                  len(expected.get('prices',{})))
            return True
        except Exception as exc:
            if attempt==attempts-1:raise
            print('Awaiting Pages stock feed',attempt+1,type(exc).__name__,str(exc)[:140],flush=True)
            time.sleep(8)
    raise AssertionError('Unreachable')
if __name__=='__main__':verify()
