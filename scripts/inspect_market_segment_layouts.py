#!/usr/bin/env python3
"""Diagnostic only: print bounded exact report table excerpts for new parsers."""
import hashlib
import json
import re
from pathlib import Path
from build_market_overview_segments import read_pages
from ingest_official_pdf import download
from alm_brand_live_pdf import download_report
ROOT=Path(__file__).resolve().parents[1]
def main():
    feed=json.loads((ROOT/'data/verified_financial_feed.json').read_text())
    comp=json.loads((ROOT/'data/nine_insurer_comparison.json').read_text())
    for c in ('Gjensidige','Fremtind','Alm. Brand'):
        if c=='Alm. Brand':
            company=next(x for x in comp['companies'] if x['company']==c)
            a=company['metric_sources']['insurance_revenue'];url=a['source_url'];sha=a['source_sha256']
            blob=download_report(url)
        else:
            a=max((r for r in feed['observations'] if r['company']==c and r['scope']=='group' and r['metric']=='insurance_revenue' and r['period_type']=='quarter'),key=lambda r:(r['year'],r['quarter']))
            url=a['source_url'];sha=a['source_sha256'];blob=download(url)
        if hashlib.sha256(blob).hexdigest()!=sha:raise ValueError(c+' original report fingerprint mismatch')
        patterns={
          'Gjensidige':r'General Insurance (?:Private|Commercial)|(?:Private|Commercial) Norway|Segment information',
          'Fremtind':r'segmentopplysninger|segmentinformasjon|privatmarked|bedriftsmarked|næringsliv',
          'Alm. Brand':r'Personal Lines|Commercial Lines'
        }
        pages=read_pages(blob)
        print('SEGMENT_LAYOUT_SOURCE',c,url,sha,'pages',len(pages),flush=True)
        for page,t in pages:
            if not re.search(patterns[c],t,re.I):continue
            if c=='Fremtind' and not re.search(r'forsikringstjenester|forsikringsinntekter|erstatningskostnader|forsikringskostnader',t,re.I):continue
            if c!='Fremtind' and not re.search(r'Insurance revenue|Combined ratio|Claims ratio|Loss ratio|Cost ratio',t,re.I):continue
            print('SEGMENT_LAYOUT_PAGE',c,page,repr(t[:7500]),flush=True)
if __name__=='__main__':main()
