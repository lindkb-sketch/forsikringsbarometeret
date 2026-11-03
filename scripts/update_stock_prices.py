#!/usr/bin/env python3
"""Best-effort, delayed market snapshots; never label them live or invent prices.

Daily bars may contain the *ongoing* exchange session. Keep their timestamp,
quality and history so the dashboard does not present provisional data as closes.
Public Yahoo endpoints have availability and redistribution restrictions; a
licensed market-data provider is required before investment-grade deployment.
"""
import datetime as dt
import json
import math
import os
import tempfile
import urllib.parse
import urllib.request
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data'/'stock_prices.json'
SYMBOLS={'Gjensidige':'GJF.OL','Protector':'PROT.OL',
         'Storebrand':'STB.OL','Tryg':'TRYG.CO','Sampo / If':'SAMPO.HE'}
MARKETS={'.OL':('Oslo Børs','Europe/Oslo','NOK'),
         '.CO':('Nasdaq Copenhagen','Europe/Copenhagen','DKK'),
         '.HE':('Nasdaq Helsinki','Europe/Helsinki','EUR')}
UNLISTED=['Fremtind','Frende']
MAX_HISTORY=280

def normalize(symbol,data):
    results=data.get('chart',{}).get('result') or []
    if len(results)!=1:raise ValueError('No unique market instrument returned')
    result=results[0]
    meta=result['meta']
    suffix=next((s for s in MARKETS if symbol.endswith(s)),None)
    if not suffix:raise ValueError('Unknown exchange suffix')
    exchange,tz,currency=MARKETS[suffix]
    if meta.get('currency')!=currency:raise ValueError('Unexpected exchange currency')
    if meta.get('symbol','').upper()!=symbol.upper():
        raise ValueError('Ticker mismatch in market response')
    quote=result['indicators']['quote'][0]
    ts=result.get('timestamp') or []
    closes=quote.get('close') or []
    if len(ts)!=len(closes):raise ValueError('Timestamp/price length mismatch')
    zone=ZoneInfo(tz)
    history={}
    for timestamp,value in zip(ts,closes):
        if not isinstance(value,(int,float)) or not math.isfinite(value) or value<=0:
            continue
        day=dt.datetime.fromtimestamp(timestamp,zone).date().isoformat()
        history[day]=round(value,4)
    series=[{'date':day,'price':value} for day,value in sorted(history.items())]
    if len(series)<2:raise ValueError('Insufficient daily price history')
    series=series[-MAX_HISTORY:]
    asof=meta.get('regularMarketTime')
    if not isinstance(asof,(int,float)) or asof<=0:
        asof=ts[-1]
    observation_time=dt.datetime.fromtimestamp(asof,dt.timezone.utc)
    latest=series[-1]
    # Daily chart bars are not guaranteed final until the exchange closes.
    last_session_date=dt.datetime.fromtimestamp(asof,zone).date().isoformat()
    market_period=meta.get('currentTradingPeriod',{}).get('regular',{})
    session_end=market_period.get('end')
    provisional=latest['date']==last_session_date and (
        not isinstance(session_end,(int,float)) or asof < session_end)
    previous=series[-2]
    return {
       'symbol':symbol,'exchange':exchange,'currency':currency,
       'close':latest['price'],'trading_date':latest['date'],
       'observed_at':observation_time.isoformat(),
       'price_type':'delayed_daily_observation' if provisional else 'delayed_daily_close',
       'provisional':provisional,'previous_close':previous['price'],
       'previous_close_date':previous['date'],
       'history':series,
       'source_url':'https://finance.yahoo.com/quote/'+urllib.parse.quote(symbol,safe='.'),
       'data_delay':'provider-dependent; NOT guaranteed real-time',
    }

def fetch(symbol):
    url='https://query1.finance.yahoo.com/v8/finance/chart/'+urllib.parse.quote(symbol,safe='.')+'?interval=1d&range=1y'
    req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 (compatible; Forsikringsbarometeret/1.0)'})
    with urllib.request.urlopen(req,timeout=18) as response:
        if urllib.parse.urlparse(response.geturl()).scheme!='https':
            raise ValueError('Insecure quote response')
        data=json.load(response)
    return normalize(symbol,data)

def update(fetcher=fetch,out=OUT,now=None):
    now=now or dt.datetime.now(dt.timezone.utc)
    old=json.loads(out.read_text(encoding='utf-8')) if out.exists() else {}
    prices={}
    errors={}
    for company,symbol in SYMBOLS.items():
        try:
            entry=fetcher(symbol)
            if entry['symbol']!=symbol:raise ValueError('Wrong ticker')
            if entry['currency']!=MARKETS[next(s for s in MARKETS if symbol.endswith(s))][2]:
                raise ValueError('Wrong currency')
            observed=dt.datetime.fromisoformat(entry['observed_at'].replace('Z','+00:00'))
            if observed.tzinfo is None or observed>now+dt.timedelta(minutes=5):
                raise ValueError('Invalid quote timestamp')
            if now-observed>dt.timedelta(days=5):raise ValueError('Quote too old')
            prices[company]=entry
        except Exception as exc:
            errors[company]=str(exc)[:180]
            # Keep last known quote only when explicitly marked unavailable/stale.
            prior=old.get('prices',{}).get(company)
            if prior and prior.get('symbol')==symbol:
                prices[company]={**prior,'availability':'stale','stale_reason':errors[company]}
    for company,entry in prices.items():
        if company not in errors:
            entry['availability']='available'
            entry.pop('stale_reason',None)
    payload={'updated_at':now.isoformat(),'prices':prices,
       'unlisted':UNLISTED,'errors':errors,
       'source':'Best-effort Yahoo Finance daily chart; delayed, non-licensed demonstration feed. Not real-time or certified for investment use.'}
    # Do not create a new repository commit when the provider returned the
    # exact same observations or the same already-reported error state.
    # A monitoring poll is not itself a quote update.
    prior_content={k:old.get(k) for k in ('prices','unlisted','errors','source')}
    new_content={k:payload.get(k) for k in ('prices','unlisted','errors','source')}
    if prior_content==new_content and old.get('updated_at'):
        payload['updated_at']=old['updated_at']
        return payload
    out.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix='.stocks-',dir=out.parent)
    try:
        with os.fdopen(fd,'w',encoding='utf-8') as file:
            json.dump(payload,file,ensure_ascii=False,indent=2)
            file.write('\n')
        os.replace(tmp,out)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)
    return payload

if __name__=='__main__':
    result=update()
    print('Stock prices available:',len(result['prices'])-len(result['errors']),
          'stale/unavailable:',len(result['errors']))
