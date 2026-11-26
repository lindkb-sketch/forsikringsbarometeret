#!/usr/bin/env python3
"""Derived ranking FX only; failure never changes issuer financial observations."""
import calendar
import csv
import datetime as dt
import io
import json
import math
import statistics
import urllib.parse
import urllib.request
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
TARGET=ROOT/'data/market_overview_fx.json'
CURRENCIES=('EUR','DKK','SEK')

def bounds(year,quarter,mode='quarter'):
    return (dt.date(year,1 if mode=='ytd' else 3*quarter-2,1),dt.date(year,3*quarter,calendar.monthrange(year,3*quarter)[1]))

def url_for(currency,year,quarter,mode='quarter'):
    if currency not in CURRENCIES:raise ValueError('Unsupported currency')
    start,end=bounds(year,quarter,mode)
    return 'https://data.norges-bank.no/api/data/EXR/B.'+currency+'.NOK.SP?'+urllib.parse.urlencode({
        'format':'csvfile','startPeriod':start.isoformat(),'endPeriod':end.isoformat(),'locale':'en'})

def average(raw,currency,year,quarter,mode='quarter'):
    start,end=bounds(year,quarter,mode)
    records=csv.DictReader(io.StringIO(raw.lstrip('\ufeff')))
    values={}
    for r in records:
        if (r['BASE_CUR'],r['QUOTE_CUR'],r['FREQ'],r['TENOR'])!=(currency,'NOK','B','SP'):
            raise ValueError('Unexpected Norges Bank series')
        day=dt.date.fromisoformat(r['TIME_PERIOD'])
        if not start<=day<=end or day in values or day.weekday()>4:raise ValueError('Invalid or duplicate rate date')
        multiplier=int(r['UNIT_MULT'])
        if multiplier not in (0,1,2,3):raise ValueError('Unexpected unit multiplier')
        value=float(r['OBS_VALUE'])/(10**multiplier)
        lower,upper={'EUR':(5,30),'DKK':(.5,5),'SEK':(.3,4)}[currency]
        if not math.isfinite(value) or not lower<value<upper:raise ValueError('Unexpected currency unit or rate')
        values[day]=value
    if len(values)<45*(quarter if mode=='ytd' else 1) or min(values)>start+dt.timedelta(days=7) or max(values)<end-dt.timedelta(days=7):
        raise ValueError('Incomplete daily quarter currency series')
    return {'rate':statistics.mean(values.values()),'observations':len(values),'first_date':min(values).isoformat(),'last_date':max(values).isoformat(),'source_url':url_for(currency,year,quarter,mode)}

def fetch(url):
    req=urllib.request.Request(url,headers={'User-Agent':'Forsikringsbarometeret/1.0'})
    with urllib.request.urlopen(req,timeout=20) as response:
        if urllib.parse.urlsplit(response.geturl()).hostname!='data.norges-bank.no':raise ValueError('Unexpected FX redirect')
        raw=response.read(250001)
        if len(raw)>250000:raise ValueError('FX response too large')
    return raw.decode('utf-8-sig')

def build(feed,comparison,existing,fetcher=fetch,today=None):
    today=today or dt.date.today()
    dates={(r['year'],r['quarter']) for r in feed.get('observations',[]) if r.get('scope')=='group' and r.get('metric')=='insurance_revenue' and r.get('period_type')=='quarter' and r.get('status') in ('reported','calculated')}
    import re
    for c in comparison.get('companies',[]):
        m=re.fullmatch(r'Q([1-4]) (\d{4})',c.get('period') or '')
        if m and c.get('status')=='verified_official_pdf_reconciled':dates.add((int(m[2]),int(m[1])))
    result={'schema_version':1,'source':'Norges Bank','method':'Mean of daily NOK mid-rates per single unit of currency, completed reporting quarter or year-to-date period','periods':dict(existing.get('periods',{}))}
    if not dates:return result
    for year,quarter in [max(dates)]:
        label=f'Q{quarter} {year}'
        if bounds(year,quarter)[1]>=today:continue
        old=result['periods'].get(label,{})
        period={}
        for mode,ratekey,evkey in (('quarter','rates','evidence'),('ytd','ytd_rates','ytd_evidence')):
            entries=dict(old.get(evkey,{}))
            for currency in CURRENCIES:
                item=entries.get(currency,{})
                url=url_for(currency,year,quarter,mode)
                minimum=45*(quarter if mode=='ytd' else 1)
                if item.get('source_url')==url and item.get('observations',0)>=minimum and isinstance(item.get('rate'),(int,float)) and math.isfinite(item['rate']) and item['rate']>0:continue
                try:
                    if mode=='ytd' and quarter==1 and currency in period['evidence']:
                        entries[currency]=period['evidence'][currency]
                    else:
                        entries[currency]=average(fetcher(url),currency,year,quarter,mode)
                except Exception as exc:
                    print('::warning::Market overview FX unavailable '+label+' '+mode+' '+currency+' '+type(exc).__name__,flush=True)
                    entries.pop(currency,None)
            period[ratekey]={k:v['rate'] for k,v in entries.items()}
            period[evkey]=entries
        result['periods'][label]=period
    return result

def main():
    load=lambda name:json.loads((ROOT/'data'/name).read_text(encoding='utf-8'))
    previous=json.loads(TARGET.read_text(encoding='utf-8')) if TARGET.exists() else {}
    result=build(load('verified_financial_feed.json'),load('nine_insurer_comparison.json'),previous)
    from publish_geographic_workbooks import atomic_write
    atomic_write(TARGET,result)
    print('MARKET_OVERVIEW_FX',json.dumps(result,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
