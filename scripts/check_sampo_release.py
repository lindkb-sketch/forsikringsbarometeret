#!/usr/bin/env python3
import datetime,json
from pathlib import Path
from zoneinfo import ZoneInfo
root=Path(__file__).resolve().parents[1]
cal=json.loads((root/'data/calendar.json').read_text())
rows=json.loads((root/'data/verified_financial_feed.json').read_text())['observations']
now=datetime.datetime.now(ZoneInfo('Europe/Oslo'))
required={'insurance_revenue','insurance_service_result','combined_ratio','loss_ratio','expense_ratio'}
for event in cal.get('Sampo / If',{}).get('events',[]):
 p=event['period'].split()
 if len(p)!=2 or not p[0].startswith('Q'):continue
 y,q=int(p[1]),int(p[0][1:])
 deadline=datetime.datetime.combine(datetime.date.fromisoformat(event['date']),datetime.time(9,30),ZoneInfo('Europe/Oslo'))
 if now<deadline:continue
 for scope,segment in [('group',None),('reported_segment','Private Nordic'),('reported_segment','Nordic Commercial')]:
  have={r.get('metric') for r in rows if r.get('company')=='Sampo' and r.get('year')==y and r.get('quarter')==q and r.get('scope')==scope and r.get('segment')==segment and r.get('period_type')=='quarter' and r.get('status')=='reported' and r.get('source_type')=='official_quarterly_report' and str(r.get('source_url','')).startswith('https://') and r.get('source_sha256') and r.get('source_page')}
  missing=required-have
  if missing:raise SystemExit(f'Sampo {event["period"]} {segment or "group"} missing: {sorted(missing)}')
print('Sampo published quarter coverage OK or not yet due')
