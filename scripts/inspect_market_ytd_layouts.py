#!/usr/bin/env python3
"""Inspect exact original-report cumulative segment layouts, bounded diagnostic."""
import hashlib,json,re
from pathlib import Path
from build_market_overview_segments import anchors,download,read_pages
from ingest_official_pdf import download as get
ROOT=Path(__file__).resolve().parents[1]
def main():
    feed=json.loads((ROOT/'data/verified_financial_feed.json').read_text())
    comp=json.loads((ROOT/'data/nine_insurer_comparison.json').read_text())
    rows=list(anchors(feed,comp))
    prot=[r for r in feed['observations'] if r['company']=='Protector' and r['scope']=='group' and r['period_type']=='quarter' and r['metric']=='insurance_revenue' and r.get('source_type')=='official_quarterly_report']
    rows.append(max(prot,key=lambda r:(r['year'],r['quarter'])))
    for a in rows:
        c=a['company']; raw=get(a['source_url']) if c=='Protector' else download(a)
        if hashlib.sha256(raw).hexdigest()!=a['source_sha256']:raise ValueError(c+' report changed')
        print('MARKET_LAYOUT_SOURCE',c,a['year'],a['quarter'],a['source_url'],flush=True)
        for page,t in read_pages(raw):
            keep=(
              c=='Alm. Brand' and re.search(r'Personal Lines|Commercial Lines',t,re.I) and re.search(r'Insurance revenue|Combined ratio|Claims ratio',t,re.I)
              or c=='Tryg' and re.search(r'Quarterly outline|Private|Commercial|Norwegian general insurance',t,re.I) and re.search(r'Insurance revenue|Combined ratio|Claims ratio',t,re.I)
              or c=='Protector' and re.search(r'Segment information',t,re.I)
              or c=='Gjensidige' and re.search(r'General Insurance (?:Private|Commercial)|NOK millions Q[1-4]',t,re.I) and page<22
              or c=='Fremtind' and re.search(r'Segmentresultater|Resultatutvikling hittil i år|Combined ratio, netto etter',t,re.I) and page<12)
            if keep:print('MARKET_LAYOUT_PAGE',c,page,repr(t[:10500]),flush=True)
if __name__=='__main__':main()
