#!/usr/bin/env python3
"""Ensure a due Sampo report reaches the actual public GitHub Pages feed."""
import datetime
import json
import urllib.request
from pathlib import Path
from zoneinfo import ZoneInfo

root=Path(__file__).resolve().parents[1]
cal=json.loads((root/'data/calendar.json').read_text())
now=datetime.datetime.now(ZoneInfo('Europe/Oslo'))
for event in cal.get('Sampo / If',{}).get('events',[]):
 try:
  q,y=event['period'].split()
  deadline=datetime.datetime.combine(datetime.date.fromisoformat(event['date']),datetime.time(9,30),ZoneInfo('Europe/Oslo'))
  if now<deadline:continue
  year,quarter=int(y),int(q[1:])
 except (ValueError,KeyError):
  continue
 with urllib.request.urlopen('https://lindkb-sketch.github.io/forsikringsbarometeret/data/verified_financial_feed.json?nocache='+str(int(now.timestamp())),timeout=30) as response:
  rows=json.load(response)['observations']
 required={'insurance_revenue','insurance_service_result','combined_ratio','loss_ratio','expense_ratio'}
 for scope,segment in [('group',None),('reported_segment','Private Nordic'),('reported_segment','Nordic Commercial')]:
  found={r.get('metric') for r in rows if r.get('company')=='Sampo' and r.get('year')==year and r.get('quarter')==quarter and r.get('period_type')=='quarter' and r.get('scope')==scope and r.get('segment')==segment and r.get('status')=='reported' and r.get('source_url') and r.get('source_page')}
  if required-found:
   raise SystemExit('Public Sampo '+event['period']+' '+str(segment or 'group')+' missing: '+str(sorted(required-found)))
print('Public Sampo report coverage OK or not yet due')
