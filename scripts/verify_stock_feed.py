#!/usr/bin/env python3
"""Validate price-feed integrity, not its suitability for trading."""
import datetime as dt
import json
import math
from pathlib import Path
from update_stock_prices import SYMBOLS,MARKETS,OUT

def validate(payload):
    errors=[]
    prices=payload.get('prices',{})
    if not isinstance(prices,dict):raise ValueError('prices must be a dictionary')
    if set(prices)-set(SYMBOLS):errors.append('Unexpected company in market feed')
    if payload.get('unlisted')!=['Fremtind','Frende']:
        errors.append('Non-listed company metadata changed')
    active=0
    for company,symbol in SYMBOLS.items():
        row=prices.get(company)
        if not row:continue
        if row.get('symbol')!=symbol:errors.append(company+' incorrect symbol')
        currency=next(v[2] for suffix,v in MARKETS.items() if symbol.endswith(suffix))
        if row.get('currency')!=currency:errors.append(company+' incorrect currency')
        if row.get('availability')=='stale':
            if not payload.get('errors',{}).get(company):
                errors.append(company+' stale quote missing failure provenance')
            continue
        if row.get('availability')!='available':
            errors.append(company+' quote has no quality status')
            continue
        active+=1
        history=row.get('history')
        if not isinstance(history,list) or len(history)<2:
            errors.append(company+' missing complete timestamped history')
            continue
        if any(not isinstance(p,dict) or not isinstance(p.get('date'),str)
               or not isinstance(p.get('price'),(int,float))
               or not math.isfinite(p['price']) or p['price']<=0 for p in history):
            errors.append(company+' malformed dated price observation')
            continue
        dates=[p['date'] for p in history]
        if dates!=sorted(set(dates)):errors.append(company+' history not sorted and unique')
        if history[-1]['price']!=row.get('close') or history[-1]['date']!=row.get('trading_date'):
            errors.append(company+' latest quote does not match chart')
        if history[-2]['price']!=row.get('previous_close'):
            errors.append(company+' previous close differs from history')
        try:
            timestamp=dt.datetime.fromisoformat(row['observed_at'].replace('Z','+00:00'))
            if timestamp.tzinfo is None:raise ValueError('timestamp without timezone')
        except (KeyError,TypeError,ValueError):
            errors.append(company+' missing timestamp')
    if active==0:errors.append('No fresh valid stock snapshots; do not publish stale-only feed')
    if errors:raise ValueError('Stock feed rejected: '+'; '.join(errors))
    return {'active_quotes':active,'tracked':len(SYMBOLS),
            'provider_errors':len(payload.get('errors',{}))}

if __name__=='__main__':
    print('MARKET_FEED_VALID',validate(json.loads(OUT.read_text(encoding='utf-8'))))
