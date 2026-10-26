#!/usr/bin/env python3
"""Import official Storebrand ASA Insurance segment Q4 independently of Norway.

There is no standalone Storebrand Forsikring AS Q4 report. An unavailable
Norway Q4 document must not suppress a verified Storebrand ASA Q4 group series.
Explicitly labelled Q4 quarter columns are mandatory; never subtract YTD.
"""
import json
import tempfile
from datetime import date
from pathlib import Path

from audit_financials import ROOT, audit
from build_verified_feed import build
from storebrand_sources import discover
from storebrand_automation_check import download_pdf
from import_storebrand_reports import parse_group, integrate
from publish_geographic_workbooks import atomic_write

DATA = ROOT / 'data/financial_observations.json'
FEED = ROOT / 'data/verified_financial_feed.json'
# Historical issuer PDF independently used in the live Storebrand Q4 golden test.
Q4_2025 = 'https://www.storebrand.no/en/investor-relations/quarterly-reporting/storebrand-asa/2025/_/attachment/inline/a54538ec-e317-4386-adfa-38c2849bcbb2:a00900f3b30486ee15cba89559dbecbf1def35f5/2025-4q-interim-report-storebrand-asa.pdf'

def find_group_q4(year, discoverer=discover):
    try:
        options=[x['document_url'] for x in discoverer(year=year)['reports']
                 if x.get('year')==year and x.get('quarter')==4
                 and x.get('scope')=='group' and x.get('entity')=='Storebrand ASA']
    except Exception:
        if year != 2025:
            raise
        options=[]
    options=list(dict.fromkeys(options))
    if len(options)>1:
        raise ValueError('Ambiguous official Storebrand ASA Q4 PDFs')
    return options[0] if options else (Q4_2025 if year==2025 else None)

def run(today=None, data=DATA, feed=FEED, discoverer=discover, downloader=download_pdf):
    today=today or date.today()
    existing=json.loads(Path(data).read_text(encoding='utf-8'))
    if not audit(existing)['ok']:
        raise ValueError('Storebrand baseline failed financial audit')
    imported={}
    for year in range(2025,today.year+1):
        # A Q4 annual/quarterly report is normally published after year-end.
        if year>=today.year:
            continue
        url=find_group_q4(year,discoverer)
        if url is None:
            continue  # No new Q4 report: no guessed values.
        with tempfile.TemporaryDirectory(prefix='storebrand-q4-') as td:
            path=Path(td)/'group.pdf'
            downloader(url,path)
            source=parse_group(path,url,year,4)
        # Only the isolated Q4 group rows and their explicitly reported YTD
        # comparatives: do not overwrite previously audited Q1-Q3.
        incoming=[r for r in source if r['scope']=='group' and r['quarter']==4
                  and r['year'] in (year,year-1)]
        mandatory={'combined_ratio','loss_ratio','expense_ratio','insurance_revenue'}
        found={r['metric'] for r in incoming
               if r['year']==year and r['period_type']=='quarter'}
        if not mandatory.issubset(found):
            raise ValueError(f'Official Storebrand Q4 {year} missing {mandatory-found}')
        existing,added,updated=integrate(existing,incoming)
        imported[year]={'source':url,'verified_rows':len(incoming),'added':added,'updated':updated}
    if any(x['added'] or x['updated'] for x in imported.values()):
        atomic_write(data,existing)
        atomic_write(feed,build(existing))
    print(json.dumps({'storebrand_q4':imported},ensure_ascii=False))
    return imported

if __name__=='__main__':run()
