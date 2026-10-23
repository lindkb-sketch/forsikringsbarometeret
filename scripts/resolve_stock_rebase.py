#!/usr/bin/env python3
"""Resolve ONLY data/stock_prices.json conflicts, preserving latest validated trading dates."""
import datetime as dt
import json,math,os,subprocess,tempfile
from pathlib import Path
from urllib.parse import urlparse
PATH='data/stock_prices.json'
SYMBOLS={'Gjensidige':('GJF.OL','NOK'),'Protector':('PROT.OL','NOK'),'Storebrand':('STB.OL','NOK'),'Tryg':('TRYG.CO','DKK'),'Sampo / If':('SAMPO.HE','EUR')}
def git(root,*args):return subprocess.check_output(['git','-C',str(root),*args],stderr=subprocess.PIPE)
def validate(snapshot):
    if not isinstance(snapshot,dict) or not isinstance(snapshot.get('prices'),dict):raise ValueError('Invalid stock payload')
    for company,row in snapshot['prices'].items():
        if company not in SYMBOLS or not isinstance(row,dict):raise ValueError('Unknown ticker')
        symbol,currency=SYMBOLS[company]
        if row.get('symbol')!=symbol or row.get('currency')!=currency:raise ValueError('Ticker or currency mismatch')
        close=row.get('close')
        if type(close) not in (int,float) or not math.isfinite(close) or close<=0:raise ValueError('Invalid close')
        date=dt.date.fromisoformat(row['trading_date'])
        if date>dt.datetime.now(dt.timezone.utc).date():raise ValueError('Future trading date')
        url=urlparse(row.get('source_url',''))
        if url.scheme!='https' or url.hostname!='query1.finance.yahoo.com' or url.path!='/v8/finance/chart/'+symbol:raise ValueError('Quote provenance mismatch')
        if row.get('price_type')!='delayed_daily_close':raise ValueError('Not a delayed daily close')
    return snapshot
def merge(upstream,replay):
    upstream,replay=validate(upstream),validate(replay)
    result=dict(upstream);prices={}
    for company in sorted(set(upstream['prices'])|set(replay['prices'])):
        a,b=upstream['prices'].get(company),replay['prices'].get(company)
        if a is None:chosen=b
        elif b is None:chosen=a
        else:
            da,db=dt.date.fromisoformat(a['trading_date']),dt.date.fromisoformat(b['trading_date'])
            if da==db and a!=b:raise ValueError('Conflicting closes/provenance on same trading date for '+company)
            chosen=a if da>=db else b
        prices[company]=chosen
    result['prices']=prices
    ta,tb=upstream.get('updated_at',''),replay.get('updated_at','')
    for t in (ta,tb):dt.datetime.fromisoformat(t.replace('Z','+00:00'))
    recent=upstream if ta>=tb else replay
    for key in ('updated_at','errors','source','unlisted'):
        if key in recent:result[key]=recent[key]
    return result
def resolve(root='.'):
    root=Path(root)
    conflicts=git(root,'diff','--name-only','--diff-filter=U','-z').decode().strip('\0').split('\0')
    if conflicts!=[PATH]:raise ValueError('Only data/stock_prices.json may be auto-resolved: '+repr(conflicts))
    upstream=json.loads(git(root,'show',':2:'+PATH));replay=json.loads(git(root,'show',':3:'+PATH))
    merged=merge(upstream,replay);output=root/PATH
    fd,tmp=tempfile.mkstemp(dir=output.parent,prefix='.stock-rebase-',suffix='.json')
    try:
        with os.fdopen(fd,'w',encoding='utf-8') as stream:json.dump(merged,stream,ensure_ascii=False,indent=2);stream.write('\n')
        os.replace(tmp,output)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)
    git(root,'add','--',PATH)
    return merged
if __name__=='__main__':
    import sys
    resolve(sys.argv[1] if len(sys.argv)>1 else '.')
