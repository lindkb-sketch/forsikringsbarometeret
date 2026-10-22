#!/usr/bin/env python3
"""Verify the actual public Pages deployment, not only generated local files."""
import json, time, urllib.request
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
BASE='https://lindkb-sketch.github.io/forsikringsbarometeret/data/'
FILES=['verified_financial_feed.json','stock_prices.json','official_news.json','quarterly_editorial.json']
def load_public(name):
    req=urllib.request.Request(BASE+name+'?check='+str(int(time.time())),headers={'Cache-Control':'no-cache'})
    with urllib.request.urlopen(req,timeout=25) as response:
        if response.status!=200:raise ValueError(f'{name}: HTTP {response.status}')
        return json.load(response)
def check():
    local={n:json.loads((ROOT/'data'/n).read_text(encoding='utf-8')) for n in FILES}
    for attempt in range(15):
        try:
            public={n:load_public(n) for n in FILES}
            for n in FILES:
                if public[n]!=local[n]:raise ValueError(f'{n}: public copy differs from committed artifact')
            feed=public['verified_financial_feed.json']
            rows=[r for r in feed['observations'] if r.get('company')=='Protector']
            if not rows:print('WARNING: Protector has no PDF-verified published financial observations')
            stock=public['stock_prices.json']['prices'].get('Protector')
            if not stock or stock.get('symbol')!='PROT.OL' or not stock.get('trading_date'):
                raise ValueError('Protector delayed stock quote missing')
            editorial=public['quarterly_editorial.json']
            if not isinstance(editorial.get('brief'),list) or not isinstance(editorial.get('news'),list):
                raise ValueError('Editorial schema missing')
            if not isinstance(public['official_news.json'].get('items'),list):
                raise ValueError('News schema missing')
            print('LIVE PAGES VERIFIED: financial feed, delayed Protector stock quote, news, quarterly editorial')
            print('Protector PDF-verified financial observations:',len(rows))
            return
        except Exception as exc:
            print(f'Attempt {attempt+1}/15: {exc}',flush=True)
            if attempt==14:raise
            time.sleep(12)
if __name__=='__main__':check()
