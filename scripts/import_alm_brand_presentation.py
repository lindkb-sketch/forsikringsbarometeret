#!/usr/bin/env python3
"""Admit Alm. Brand Q3 solvency only after verifying the actual official presentation PDF."""
import hashlib
import io
import json
import re
import urllib.request
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'data/extended_insurer_financials.json'
PRESENTATION='https://s29.q4cdn.com/228553818/files/content_files/Investor-presentation-Q3-2026.pdf'
EXPECTED={'solvency_ratio':238.0,'own_funds':4685,'solvency_capital_requirement':1970}
EXISTING={'insurance_revenue':3054,'insurance_service_result':755,
          'combined_ratio':75.3,'loss_ratio':59.2,'expense_ratio':16.1,
          'insurance_revenue_growth':1.6}

def verify_pdf(raw, url=PRESENTATION):
    if url!=PRESENTATION or not isinstance(raw,bytes) or len(raw)>25_000_000 or not raw.startswith(b'%PDF-'):
        raise ValueError('Unapproved or invalid Alm. Brand official presentation')
    import pdfplumber
    with pdfplumber.open(io.BytesIO(raw)) as pdf:
        pages=[p.extract_text() or '' for p in pdf.pages]
    if len(pages)<19:raise ValueError('Official Q3 presentation lacks slide 19')
    cover=' '.join(pages[:3]).lower()
    if not ('2026' in cover and 'q3' in cover and 'insurance' in cover):
        raise ValueError('Wrong issuer or period in presentation')
    text=pages[18]
    compact=' '.join(text.split())
    print('ALM_BRAND_SLIDE_19_EXTRACTION',repr(compact[:2000]),flush=True)
    if not ('Total capital' in text and 'Q3 2026' in text and 'Q2 2026' in text
            and 'Solvency capital requirement' in text):
        raise ValueError('Missing Group capital table on presentation slide 19')
    if not re.search(r'SCR ratio increasing to\s*238%',compact,re.I):
        raise ValueError('Missing issuer solvency headline')
    if not re.search(r'(?:Total capital ratio|SCR ratio)[^\n]{0,110}\b238\s*%',text,re.I|re.S):
        raise ValueError('Missing table corroboration of 238% SCR ratio')
    if not ('Total capital' in compact and 'solvency coverage purposes' in compact and re.search(r'\b4[, ]?685\b',compact)):
        raise ValueError('Own funds 4,685 missing or ambiguous')
    if not ('Solvency capital requirement' in text and re.search(r'\b1,970\b',text)):
        raise ValueError('SCR 1,970 missing or ambiguous')
    if round(4685/1970*100)!=238:raise ValueError('Solvency arithmetic mismatch')
    return {'source_type':'official_results_presentation','source_url':url,
            'source_sha256':hashlib.sha256(raw).hexdigest(),'source_page':19,
            'year':2026,'quarter':3,'scope':'group','currency':'DKK',
            'metrics':EXPECTED}

def reconcile(existing,evidence):
    if existing.get('company')!='Alm. Brand' or (existing.get('year'),existing.get('quarter'))!=(2026,3):
        raise ValueError('Wrong issuer or period')
    if existing.get('status') not in ('verified_issuer_announcement','verified_official_presentation_reconciled'):
        raise ValueError('Unsupported preexisting evidence')
    if existing.get('scope')!='group' or existing.get('currency')!='DKK':
        raise ValueError('Wrong scope or currency')
    if any(existing.get('metrics',{}).get(k)!=v for k,v in EXISTING.items()):
        raise ValueError('Presentation cannot override existing verified financial metrics')
    if existing.get('metrics',{}).get('solvency_ratio') not in (None,238.0):
        raise ValueError('Conflicting solvency evidence')
    result=dict(existing)
    result['metrics']=dict(existing['metrics'],solvency_ratio=238.0)
    result['presentation_evidence']=evidence
    result['status']='verified_official_presentation_reconciled'
    result['note']='Issuer announcement financial metrics; Q3 Group solvency from official presentation slide 19, SHA256 verified.'
    return result

def run(out=DATA,raw=None):
    existing=json.loads(out.read_text(encoding='utf-8'))['insurers']['Alm. Brand']
    if existing.get('status')=='verified_official_pdf_reconciled' or (existing.get('year',0),existing.get('quarter',0))>(2026,3):
        print('ALM_LEGACY_PRESENTATION_SKIPPED rolling snapshot retained',flush=True)
        return
    if raw is None:
        req=urllib.request.Request(PRESENTATION,headers={'User-Agent':'Mozilla/5.0 Forsikringsbarometeret'})
        with urllib.request.urlopen(req,timeout=40) as response:
            if response.geturl()!=PRESENTATION:raise ValueError('Presentation redirected outside approved source')
            raw=response.read(25_000_001)
    evidence=verify_pdf(raw)
    data=json.loads(out.read_text(encoding='utf-8'))
    data['insurers']['Alm. Brand']=reconcile(data['insurers']['Alm. Brand'],evidence)
    out.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('ALM_BRAND_OFFICIAL_PRESENTATION_RECONCILED',evidence['source_sha256'],'slide',evidence['source_page'])

if __name__=='__main__':run()
