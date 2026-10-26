#!/usr/bin/env python3
"""Live proof: official issuer Q3 2025 PDF supplies Q3/YTD 2024 comparatives.

This test never writes production data. It fails if PDF is inaccessible, changes
schema, source is wrong, or old 2025 reference observations disagree.
"""
import json,tempfile
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from import_gjensidige_latest import import_period

def run():
 baseline=json.loads((ROOT/'data/financial_observations.json').read_text(encoding='utf-8'))
 with tempfile.TemporaryDirectory() as temp:
  target=Path(temp)/'financial_observations.json'
  target.write_text(json.dumps(baseline),encoding='utf-8')
  result=import_period(2025,3,target=target)
  if result['status']!='verified':
   raise AssertionError('Official issuer Q3 2025 source did not verify: '+repr(result))
  rows=json.loads(target.read_text(encoding='utf-8'))['observations']
  for kind in ('quarter','ytd'):
   for year in (2024,2025):
    matches=[x for x in rows if x.get('company')=='Gjensidige' and x.get('scope')=='group'
             and x.get('period_type')==kind and x.get('year')==year
             and x.get('quarter')==3 and x.get('metric')=='insurance_revenue'
             and x.get('source_type')=='official_quarterly_report'
             and x.get('source_sha256') and x.get('source_page')]
    if len(matches)!=1:raise AssertionError(f'Missing verified issuer {kind} Q3 {year}: '+repr(matches))
    print('VERIFIED_OFFICIAL_Q3_COMPARATOR',year,kind,matches[0]['value'],
          matches[0]['source_url'],matches[0]['source_sha256'])
 return True

if __name__=='__main__':run()
