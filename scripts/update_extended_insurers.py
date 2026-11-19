#!/usr/bin/env python3
"""Source-verified Alm. Brand group results, isolated from the seven-company feed.

Never invent missing values or silently carry a stale quarter into a new one.
A new quarter requires an issuer-specific extraction and explicit validation.
"""
import datetime as dt
import html
import json
import re
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data/extended_insurer_financials.json'
SOURCE='https://investorrelations.almbrand.dk/English/press-release-details/2026/Alm--Brand-AS---Interim-report-for-Q3/default.aspx'
ARCHIVE='https://investorrelations.almbrand.dk/English/financials/default.aspx#section=reports'

class Text(HTMLParser):
    def __init__(self):
        super().__init__();self.parts=[]
    def handle_data(self,data):
        self.parts.append(data)

def extract(document):
    parser=Text();parser.feed(document)
    body=' '.join(html.unescape(' '.join(parser.parts)).split())
    if not re.search(r'Interim report for Q3',body,re.I) or not re.search(r'28 October 2026',body,re.I):
        raise ValueError('Unexpected issuer reporting period')
    patterns={
        'insurance_revenue':r'Insurance revenue grew by 1[.,]6% to DKK 3,054 million',
        'insurance_service_result':r'insurance service result was DKK 755 million',
        'combined_ratio':r'combined ratio of 75[.,]3',
        'loss_ratio':r'claims ratio of 59[.,]2',
        'expense_ratio':r'expense ratio increased by 0[.,]3 of a percentage point to 16[.,]1',
    }
    for metric,pattern in patterns.items():
        if not re.search(pattern,body,re.I):
            raise ValueError('Missing official evidence for '+metric)
    return {'company':'Alm. Brand','year':2026,'quarter':3,'currency':'DKK',
            'scope':'group','source_type':'official_issuer_interim_announcement',
            'source_url':SOURCE,'report_archive':ARCHIVE,
            'metrics':{'insurance_revenue':3054,'insurance_service_result':755,
                       'combined_ratio':75.3,'loss_ratio':59.2,'expense_ratio':16.1,
                       'insurance_revenue_growth':1.6},
            'unit':'DKK million for financial amounts; percent for ratios',
            'status':'verified_issuer_announcement',
            'note':'Quarterly values; reported same-quarter insurance revenue growth 1.6%; not a PDF page-level audited import'}

def fetch(url=SOURCE):
    request=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 Forsikringsbarometeret'})
    with urllib.request.urlopen(request,timeout=25) as response:
        if not response.geturl().startswith('https://investorrelations.almbrand.dk/'):
            raise ValueError('Unexpected redirect')
        return response.read(3_000_000).decode('utf-8','replace')

def update(document=None,out=OUT):
    row=extract(fetch() if document is None else document)
    old=json.loads(out.read_text(encoding='utf-8')) if out.exists() else {}
    klp=old.get('insurers',{}).get('KLP Skadeforsikring',{
        'company':'KLP Skadeforsikring','status':'awaiting_source_verified_metrics',
        'metrics':{},'report_archive':'https://www.klp.no/om-klp/finans-og-ir/rapporter-og-presentasjoner'})
    # Preserve independently verified official presentation solvency evidence.\n    previous=old.get('insurers',{}).get('Alm. Brand',{})\n    if previous.get('status')=='verified_official_presentation_reconciled':\n        from import_alm_brand_presentation import reconcile\n        row=reconcile(row,previous['presentation_evidence'])\n    # Never erase a validated KLP PDF snapshot when refreshing Alm Brand.
    payload={'insurers':{'Alm. Brand':row,'KLP Skadeforsikring':klp}}
    if old==payload:return False
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return True

if __name__=='__main__':
    print('EXTENDED_INSURER_UPDATE',update())
