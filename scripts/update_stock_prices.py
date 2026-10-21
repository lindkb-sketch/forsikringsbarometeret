#!/usr/bin/env python3
"""Best-effort delayed Yahoo Finance chart snapshots. Never fabricate a quote.

No API key required; provider may throttle/block. Historical close, not real-time.
"""
import datetime as dt,json,os,tempfile,urllib.parse,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data'/'stock_prices.json'
SYMBOLS={'Gjensidige':'GJF.OL','Protector':'PROT.OL','Storebrand':'STB.OL','Tryg':'TRYG.CO','Sampo / If':'SAMPO.HE'}
UNLISTED=['Fremtind','Frende']
def fetch(symbol):
    url='https://query1.finance.yahoo.com/v8/finance/chart/'+urllib.parse.quote(symbol,safe='.')+'?interval=1d&range=10d'
    req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 (compatible; Forsikringsbarometeret/1.0)'})
    with urllib.request.urlopen(req,timeout=18) as response:
        if urllib.parse.urlparse(response.geturl()).scheme!='https':raise ValueError('Insecure quote response')
        data=json.load(response)
    result=data['chart']['result'][0]; timestamps=result['timestamp']; closes=result['indicators']['quote'][0]['close']
    valid=[(t,v) for t,v in zip(timestamps,closes) if isinstance(v,(int,float)) and v>0]
    if not valid:raise ValueError('No daily closing prices')
    t,v=valid[-1]; currency=result['meta'].get('currency')
    if currency not in ('NOK','DKK','EUR'):raise ValueError('Unexpected currency')
    return {'symbol':symbol,'close':round(v,4),'currency':currency,'trading_date':dt.datetime.fromtimestamp(t,dt.timezone.utc).date().isoformat(),'source_url':url,'price_type':'delayed_daily_close'}
def update(fetcher=fetch,out=OUT):
    old=json.loads(out.read_text()) if out.exists() else {}
    prices=dict(old.get('prices',{})); errors={}
    for company,symbol in SYMBOLS.items():
        try:prices[company]=fetcher(symbol)
        except Exception as exc:errors[company]=str(exc)[:180]
    payload={'updated_at':dt.datetime.now(dt.timezone.utc).isoformat(),'prices':prices,'unlisted':UNLISTED,'errors':errors,'source':'Yahoo Finance public chart endpoint; best-effort delayed daily closing prices; stale records retain their trading_date'}
    out.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix='.stocks-',dir=out.parent)
    try:
        with os.fdopen(fd,'w') as f:json.dump(payload,f,ensure_ascii=False,indent=2);f.write('\n')
        os.replace(tmp,out)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)
    return payload
if __name__=='__main__':
    result=update();print('Stock prices:',len(result['prices']),'errors:',len(result['errors']))
