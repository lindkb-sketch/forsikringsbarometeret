#!/usr/bin/env python3
"""Verify the actual public Pages deployment, not only generated local files."""
import json, os, time, urllib.request
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
BASE='https://lindkb-sketch.github.io/forsikringsbarometeret/data/'
FILES=['verified_financial_feed.json','stock_prices.json','official_news.json','quarterly_editorial.json']
COMPANIES={'Fremtind','Gjensidige','Tryg','Sampo','Frende','Protector','Storebrand'}
PAGE='https://lindkb-sketch.github.io/forsikringsbarometeret/'

def check_seven(feed,html):
    rows=feed.get('observations',[])
    if not isinstance(rows,list):raise ValueError('Public financial observations must be a list')
    for company in sorted(COMPANIES):
        verified=[r for r in rows if r.get('company')==company and
                  r.get('scope')=='group' and r.get('period_type')=='quarter' and
                  r.get('status','reported') in ('reported','calculated')]
        if not verified:raise ValueError(company+': no published group-quarter observations')
        if company not in html:raise ValueError(company+': not found in published HTML')
        latest=max((r['year'],r['quarter']) for r in verified)
        print('PUBLIC_COMPANY_VERIFIED',company,'latest',latest,'observations',len(verified),flush=True)
    if 'data/verified_financial_feed.json' not in html:
        raise ValueError('Published dashboard does not load the verified financial feed')
    return True

def load_html():
    req=urllib.request.Request(PAGE+'?check='+str(time.time_ns()),headers={'Cache-Control':'no-cache'})
    with urllib.request.urlopen(req,timeout=25) as response:
        if response.status!=200:raise ValueError('Dashboard HTTP '+str(response.status))
        return response.read(2_000_000).decode('utf-8')
def load_public(name):
    req=urllib.request.Request(BASE+name+'?check='+str(int(time.time())),headers={'Cache-Control':'no-cache'})
    with urllib.request.urlopen(req,timeout=25) as response:
        if response.status!=200:raise ValueError(f'{name}: HTTP {response.status}')
        return json.load(response)
def check():
    local={n:json.loads((ROOT/'data'/n).read_text(encoding='utf-8')) for n in FILES}
    attempts=int(os.environ.get('PAGES_VERIFY_ATTEMPTS','15'))
    for attempt in range(attempts):
        try:
            public={n:load_public(n) for n in FILES}
            for n in FILES:
                if public[n]!=local[n]:raise ValueError(f'{n}: public copy differs from committed artifact')
            html=load_html()
            local_html=(ROOT/'index.html').read_text(encoding='utf-8')
            if html!=local_html:raise ValueError('Published dashboard HTML differs from deployed artifact')
            feed=public['verified_financial_feed.json']
            check_seven(feed,html)
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
            print('LIVE PAGES VERIFIED: all seven insurer group quarters, published HTML, financial feed, stock, news, editorial')
            print('Protector PDF-verified financial observations:',len(rows))
            return
        except Exception as exc:
            print(f'Attempt {attempt+1}/{attempts}: {exc}',flush=True)
            if attempt==attempts-1:raise
            time.sleep(12)
if __name__=='__main__':check()
