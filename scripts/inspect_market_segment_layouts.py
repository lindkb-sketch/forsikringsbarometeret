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
            if c=='Gjensidige' and page in (11,15):
                print('SEGMENT_LAYOUT_PAGE',c,page,repr(t[:12000]),flush=True)
                continue
            if not re.search(patterns[c],t,re.I):continue
            if c=='Fremtind' and not re.search(r'forsikringstjenester|forsikringsinntekter|erstatningskostnader|forsikringskostnader',t,re.I):continue
            if c!='Fremtind' and not re.search(r'Insurance revenue|Combined ratio|Claims ratio|Loss ratio|Cost ratio',t,re.I):continue
            print('SEGMENT_LAYOUT_PAGE',c,page,repr(t[:7500]),flush=True)
    # Print all historical note and component candidates needed for
    # current and prior-year isolated Q3 calculations, including exact dates.
    candidates=json.loads((ROOT/'data/frende_fremtind_candidates.json').read_text())['candidates']
    source_rows=[r for r in feed['observations'] if r['company']=='Fremtind' and r['scope']=='group' and r['metric']=='insurance_revenue' and r['period_type']=='quarter']
    latest=max((r['year'],r['quarter']) for r in source_rows);y,q=latest
    urls={r['source_url'] for r in source_rows if (r['year'],r['quarter']) in ((y,q),(y,q-1))}
    urls.update(x['document_url'] for x in candidates if x.get('company')=='Fremtind' and x.get('source_entity')=='Fremtind Holding' and x.get('year')==y-1)
    for url in sorted(urls):
        try:
            blob=download(url);pages=read_pages(blob)
            print('FREMTIND_NOTE_SOURCE',url,hashlib.sha256(blob).hexdigest(),repr(' '.join(pages[0][1].split())[:200]),flush=True)
            for page,t in pages:
                if re.search(r'(?:Note\s*\d+[a-z]?\s*)?Segmentopplysninger',t,re.I) and re.search(r'\bPM\b',t) and re.search(r'\bBM\b',t) and re.search(r'Inntekter fra forsikringstjenester',t,re.I):
                    print('FREMTIND_NOTE_PAGE',page,repr(t[:10000]),flush=True)
                elif re.search(r'\bPM\b',t) and re.search(r'\bBM\b',t) and re.search(r'Erstatningskostnader|Driftskostnader|Provisjonskostnader',t,re.I):
                    print('FREMTIND_COMPONENT_PAGE',page,repr(t[:10000]),flush=True)
        except Exception as exc:print('FREMTIND_NOTE_UNAVAILABLE',url,type(exc).__name__,str(exc)[:200],flush=True)
if __name__=='__main__':main()
