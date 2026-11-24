#!/usr/bin/env python3
"""Fail-closed document-byte verification for nine issuers; never publishes financial values.

The issuer registry is the trust root. A discovered candidate is not evidence until
the actual PDF is downloaded, checked for issuer/period, and hashed.
"""
import hashlib
import io
import json
import re
import urllib.parse
import urllib.request
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SOURCES=ROOT/'data/report_sources.json'
CANDIDATES=ROOT/'data/report_candidates.json'
OUTPUT=ROOT/'data/dual_document_verification.json'
MAX_BYTES=25_000_000
COMPANIES=('Fremtind','Gjensidige','Tryg','Sampo','Frende',
           'Protector','Storebrand','KLP Skadeforsikring','Alm. Brand')
# Explicitly approved delivery hosts; never derive a trusted host from an arbitrary link.
DELIVERY={
 'Fremtind':('www.fremtind.no','fremtind.no','cdn.sanity.io'),
 'Gjensidige':('www.gjensidige.com','gjensidige.com','mb.cision.com'),
 'Tryg':('tryg.com','www.tryg.com'),
 'Sampo':('www.sampo.com','sampo.com'),
 'Frende':('www.frende.no','frende.no','frende.wrep.it','newsweb.oslobors.no','live.euronext.com'),
 'Protector':('investor.protectorforsikring.no','www.protectorforsikring.no','protectorforsikring.no','storage.mfn.se'),
 'Storebrand':('www.storebrand.no','www.storebrand.com','storebrand.com','storebrand.no'),
 'KLP Skadeforsikring':('www.klp.no','klp.no'),
 'Alm. Brand':('investorrelations.almbrand.dk','almbrand.dk','s29.q4cdn.com'),
}
ISSUER_TEXT={
 'Fremtind':r'fremtind',
 'Gjensidige':r'gjensidige',
 'Tryg':r'\btryg\b',
 'Sampo':r'\bsampo\b|\bif p&c\b',
 'Frende':r'frende',
 'Protector':r'protector',
 'Storebrand':r'storebrand',
 'KLP Skadeforsikring':r'klp.{0,35}skadeforsikring',
 'Alm. Brand':r'alm\.?\s*brand',
}
PERIOD=re.compile(r'\bQ([1-4])\s*[-/ ]?\s*(20\d{2})\b|\b([1-4])\.?\s*kvartal\s*(20\d{2})\b|\b(20\d{2})\s*[-/ ]?\s*Q([1-4])\b',re.I)

def approved(company,url):
    if company not in DELIVERY:return False
    p=urllib.parse.urlsplit(url)
    return (p.scheme=='https' and p.hostname in DELIVERY[company]
            and not p.username and not p.password and p.port in (None,443)
            and not p.fragment and (p.path.lower().endswith('.pdf')
            or (company=='Alm. Brand' and p.hostname=='s29.q4cdn.com' and p.path.lower().endswith('.pdf'))))

def period_matches(text,year,quarter):
    if re.search(r'\b'+str(quarter)+r'(?:rd|th|st|nd)?\s+quarter\s+(?:of\s+)?'+str(year)+r'\b',text,re.I):return True
    if re.search(r'\b'+str(quarter)+r'\.\s*kvartal\s*'+str(year)+r'\b',text,re.I):return True
    # Nordic Q1-Q3 reports identify the cumulative period, not only Q3.
    if re.search(r'\bQ1\s*[-–]\s*Q'+str(quarter)+r'\s*'+str(year)+r'\b',text,re.I):return True
    if re.search(r'\b'+str(quarter)+r'\.?\s*kvartal\s*'+str(year)+r'\b',text,re.I):return True
    for m in PERIOD.finditer(text):
        q,y=(m.group(1),m.group(2)) if m.group(1) else (
            (m.group(3),m.group(4)) if m.group(3) else (m.group(6),m.group(5)))
        if int(q)==quarter and int(y)==year:return True
    return False

def verify_pdf(raw,company,url,year,quarter):
    if not approved(company,url):raise ValueError('Unapproved document delivery host or URL')
    if not isinstance(raw,bytes) or not raw.startswith(b'%PDF-') or len(raw)>MAX_BYTES:
        raise ValueError('Missing, oversized or invalid PDF bytes')
    import pdfplumber
    with pdfplumber.open(io.BytesIO(raw)) as pdf:
        if len(pdf.pages)<1:raise ValueError('Empty PDF')
        texts=[(p.extract_text() or '') for p in pdf.pages[:min(12,len(pdf.pages))]]
    opening='\n'.join(texts)
    if not re.search(ISSUER_TEXT[company],opening,re.I):
        raise ValueError('Issuer identity not confirmed in PDF text')
    if not period_matches(opening,year,quarter):
        raise ValueError('Quarter/year not confirmed in PDF text')
    return {'company':company,'document_url':url,'year':year,'quarter':quarter,
            'source_sha256':hashlib.sha256(raw).hexdigest(),
            'issuer_verified':True,'period_verified':True,
            'source_pages_examined':len(texts),'status':'verified_document_bytes_only'}

def download(company,url,opener=None):
    if not approved(company,url):raise ValueError('Unapproved URL')
    opener=opener or urllib.request.urlopen
    req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 Forsikringsbarometeret'})
    with opener(req,timeout=30) as resp:
        final=resp.geturl()
        if not approved(company,final):raise ValueError('Unapproved PDF redirect')
        raw=resp.read(MAX_BYTES+1)
    if len(raw)>MAX_BYTES:raise ValueError('PDF exceeds size limit')
    return raw,final

def run(year=2026,quarter=3,max_per_company=5):
    candidates=json.loads(CANDIDATES.read_text(encoding='utf-8'))
    output={'schema_version':1,'year':year,'quarter':quarter,
            'document_verification_only':True,'metrics_published':False,'companies':[]}
    for company in COMPANIES:
        records=[]
        seen=set()
        options=[c for c in candidates.get('candidates',[]) if c.get('company')==company
                 and c.get('document_type') in ('quarterly_report','results_presentation')]
        options=sorted(options,key=lambda c:(c['document_type']!='results_presentation',c['document_url']))
        for candidate in options:
            url=candidate['document_url']
            if url in seen:continue
            seen.add(url)
            # Avoid downloading historical PDFs: filename or link must explicitly mention period.
            label=(candidate.get('link_text','')+' '+urllib.parse.unquote(url))
            if not period_matches(label,year,quarter):continue
            if len(records)>=max_per_company:break
            kind=candidate['document_type']
            try:
                raw,final=download(company,url)
                evidence=verify_pdf(raw,company,final,year,quarter)
                records.append(dict(evidence,document_type=kind))
            except Exception as exc:
                records.append({'document_url':url,'document_type':kind,
                                'status':'unverified','reason':type(exc).__name__+': '+str(exc)[:180]})
        verified={x['document_type'] for x in records if x['status']=='verified_document_bytes_only'}
        output['companies'].append({'company':company,'documents':records,
          'report_verified':'quarterly_report' in verified,
          'presentation_verified':'results_presentation' in verified,
          'both_documents_verified':{'quarterly_report','results_presentation'}.issubset(verified),
          'metric_extraction_status':'not_implemented_in_document_verifier'})
    OUTPUT.write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('DUAL_DOCUMENT_BYTE_AUDIT',json.dumps({
        c['company']:{'report':c['report_verified'],'presentation':c['presentation_verified']}
        for c in output['companies']},ensure_ascii=False))
    return output

if __name__=='__main__':run()
