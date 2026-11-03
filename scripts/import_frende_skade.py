#!/usr/bin/env python3
"""Independent PDF-only Frende Skadeforsikring AS quarterly financial importer.

Never use Frende Holding figures or publisher HTML for numerical observations.
Every published observation is attributed to its exact downloaded official PDF,
SHA256 digest, physical PDF page, legal entity and reporting period.
"""
import hashlib
import io
import json
import os
import re
import tempfile
import urllib.parse
import urllib.request
from pathlib import Path
import pdfplumber

ROOT=Path(__file__).resolve().parents[1]
REPORTS=ROOT/'data/frende_skade_reports.json'
OUTPUT=ROOT/'data/frende_skade_financials.json'
ENTITY='Frende Skadeforsikring AS'
REQUIRED=('insurance_revenue','insurance_service_result','combined_ratio','loss_ratio','expense_ratio')
PDF_HOSTS={'live.euronext.com','www.frende.no','frende.no'}
LABELS={
 'insurance_revenue':'Premieinntekter for egen regning',
 'insurance_service_result':'Resultat av teknisk regnskap i skadeforsikring',
 'loss_ratio':'Skade % E/R',
 'expense_ratio':'Kostnadsandel %',
 'combined_ratio':'Combined Ratio',
}
def parse_pdf_numbers(tail, count, percent=False):
    """Recover uniquely grouped PDF columns; never infer ambiguous amounts."""
    if percent:
        values=re.findall(r'-?\d+(?:,\d+)?\s*%',tail)
        if len(values)!=count:raise ValueError('PDF ratio column mismatch')
        return [number(v) for v in values]
    tokens=re.findall(r'-?\d+',tail)
    from functools import lru_cache
    @lru_cache(None)
    def split(index,remaining):
        if remaining==0:return [()] if index==len(tokens) else []
        solutions=[]
        for size in (1,2,3):
            group=tokens[index:index+size]
            if len(group)!=size:continue
            if size==1 and len(group[0].lstrip('-'))<4:continue
            if size>1 and (not 1<=len(group[0].lstrip('-'))<=3 or
                            any(len(t)!=3 for t in group[1:])):continue
            value=int(''.join(group))
            if not 1000<=abs(value)<=20_000_000:continue
            for rest in split(index+size,remaining-1):
                solutions.append((value,)+rest)
        return solutions[:2]
    matches=split(0,count)
    if len(matches)!=1:raise ValueError('Ambiguous or invalid PDF numeric column boundaries')
    return list(matches[0])


def number(value):
    return float(value.strip().rstrip('%').replace(' ','').replace('\u00a0','').replace(',','.'))

def download_pdf(url):
    parsed=urllib.parse.urlparse(url)
    if parsed.scheme!='https' or parsed.hostname not in PDF_HOSTS or not parsed.path.lower().endswith('.pdf'):
        raise ValueError('Official issuer/exchange PDF URL required')
    req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'})
    with urllib.request.urlopen(req,timeout=45) as response:
        actual=urllib.parse.urlparse(response.geturl())
        if actual.scheme!='https' or actual.hostname not in PDF_HOSTS:
            raise ValueError('PDF redirect to untrusted host')
        blob=response.read(30_000_001)
    if len(blob)>30_000_000 or not blob.startswith(b'%PDF-'):
        raise ValueError('Missing or invalid official PDF bytes')
    return blob

def parse_page(text,year,quarter,pdf_url,pdf_sha,page):
    if ('Teknisk regnskap for skadeforsikring' not in text or
        'Premieinntekter for egen regning' not in text or
        'Nøkkelinformasjon' not in text):
        raise ValueError('No standalone non-life income/KPI table on PDF page')
    lines=text.splitlines()
    period=f'{quarter}.kv.{year}'
    if not any(re.search(rf'\b{quarter}\.\s*kv\.?\s*{year}\b',line,re.I) for line in lines[:5]):
        raise ValueError('PDF income table year/quarter mismatch')
    data={}
    for metric,label in LABELS.items():
        candidates=[line for line in lines if line.startswith(label+' ') or line==label]
        if len(candidates)!=1:raise ValueError('Missing/ambiguous PDF row '+label)
        tail=candidates[0][len(label):].strip()
        expected=3 if quarter==1 else 5
        values=parse_pdf_numbers(tail,expected,metric.endswith('ratio'))
        data[metric]=values
    claims=[line for line in lines if line.startswith('Erstatningskostnader for egen regning ')]
    expenses=[line for line in lines if line.startswith('Forskringsrelaterte driftskostnader ')]
    if len(claims)!=1 or len(expenses)!=1:raise ValueError('Missing PDF technical cost lines')
    claims_vals=parse_pdf_numbers(claims[0].split('Erstatningskostnader for egen regning ',1)[1],3 if quarter==1 else 5)
    expenses_vals=parse_pdf_numbers(expenses[0].split('Forskringsrelaterte driftskostnader ',1)[1],3 if quarter==1 else 5)
    if len(claims_vals)!=len(data['insurance_revenue']) or len(expenses_vals)!=len(claims_vals):
        raise ValueError('PDF costs and revenue columns differ')
    # The audited PDF explicitly identifies two independent same-quarter
    # columns (current year and prior year), plus two YTD columns from Q2 on.
    # Import ALL of them: a newly released quarter automatically supplies
    # the comparison data for the following year's display.
    columns=[(year,'quarter',0),(year-1,'quarter',1)]
    if quarter==1:
        columns.extend([(year,'ytd',0),(year-1,'ytd',1)])
    else:
        columns.extend([(year,'ytd',2),(year-1,'ytd',3)])
    rows=[]
    for observed_year,period_type,idx in columns:
        revenue=data['insurance_revenue'][idx]
        technical=data['insurance_service_result'][idx]
        if revenue<=0 or abs(revenue-claims_vals[idx]-expenses_vals[idx]-technical)>3:
            raise ValueError('PDF technical result does not reconcile: '
                             +str((observed_year,period_type)))
        if abs(data['loss_ratio'][idx]+data['expense_ratio'][idx]-data['combined_ratio'][idx])>0.16:
            raise ValueError('PDF combined ratio does not reconcile: '
                             +str((observed_year,period_type)))
        for metric in REQUIRED:
            value=data[metric][idx]
            unit='percent' if metric.endswith('ratio') else 'NOKm'
            if unit=='NOKm':value=round(value/1000,3)
            rows.append(dict(company='Frende',source_entity=ENTITY,scope='subsidiary',
                year=observed_year,quarter=quarter,period_type=period_type,metric=metric,
                value=value,unit=unit,status='reported',source_type='official_quarterly_report',
                source_url=pdf_url,source_page=page,source_sha256=pdf_sha,
                source_section='Frende Skadeforsikring AS – Resultat / Nøkkelinformasjon',
                source_document_period=f'Q{quarter} {year}',
                source_definition=(LABELS[metric]+
                    (' (sammenlignbar fjorårskolonne)' if observed_year!=year else ''))))

    return rows

def verify_pdf(blob,url,year,quarter):
    digest=hashlib.sha256(blob).hexdigest()
    with pdfplumber.open(io.BytesIO(blob)) as pdf:
        texts=[p.extract_text(layout=False) or '' for p in pdf.pages]
        full='\n'.join(texts)
        if ENTITY not in full:
            raise ValueError('Frende Skadeforsikring legal entity not found in official PDF')
        matches=[]
        for page,text in enumerate(texts,1):
            if ('Teknisk regnskap for skadeforsikring' in text and
                'Premieinntekter for egen regning' in text and 'Nøkkelinformasjon' in text):
                matches.append(parse_page(text,year,quarter,url,digest,page))
    if len(matches)!=1:
        raise ValueError('Ambiguous or missing standalone Frende Skade PDF financial page')
    return matches[0]

def build(report_index,previous=None,downloader=download_pdf):
    observations={(r['year'],r['quarter'],r['period_type'],r['metric']):r
                  for r in (previous or {}).get('observations',[])}
    failures=[]
    for item in report_index.get('reports',[]):
        year,quarter=item['year'],item['quarter']
        # Include original 2024 issuer PDFs to calculate 2025 year-on-year
        # growth percentages (2025/2024), rather than showing 2025 premiums.
        if year<2024 or (year==2024 and quarter==4):continue
        pdf=item.get('pdf_url')
        if not pdf:
            failures.append({'year':year,'quarter':quarter,'reason':'No original PDF attachment verified'})
            continue
        try:
            rows=verify_pdf(downloader(pdf),pdf,year,quarter)
            for row in rows:
                key=row['year'],row['quarter'],row['period_type'],row['metric']
                if key in observations and abs(observations[key]['value']-row['value'])>0.000001:
                    raise ValueError('Previously verified subsidiary value conflicts: '+str(key))
            for row in rows:
                observations[(row['year'],row['quarter'],row['period_type'],row['metric'])]=row
        except (OSError,ValueError,IndexError,KeyError) as exc:
            failures.append({'year':year,'quarter':quarter,'reason':str(exc)[:200]})
    result={'entity':ENTITY,'source_policy':'official PDFs only; independent non-life subsidiary',
        'observations':sorted(observations.values(),key=lambda r:(r['year'],r['quarter'],r['period_type'],r['metric'])),
        'diagnostics':failures}
    return result

def run():
    index=json.loads(REPORTS.read_text(encoding='utf-8'))
    old=json.loads(OUTPUT.read_text(encoding='utf-8')) if OUTPUT.exists() else None
    result=build(index,old)
    # Once 2026 Q1–Q3 are available, never silently lose a verified period.
    for q in (1,2,3):
        metrics={r['metric'] for r in result['observations']
                 if (r['year'],r['quarter'],r['period_type'])==(2026,q,'quarter')}
        if set(REQUIRED)-metrics:
            raise ValueError(f'Frende Skade Q{q} 2026 PDF import incomplete: {sorted(set(REQUIRED)-metrics)}; '
                             +str(result['diagnostics'][:5]))
    # Any newly linked official PDF must be fully parsed before publication.
    # Do not silently retain an old quarter when its original report changes.
    for item in index['reports']:
        if item['year']<2026 or not item.get('pdf_url'):continue
        key=(item['year'],item['quarter'])
        metrics={r['metric'] for r in result['observations'] if
                 (r['year'],r['quarter'],r['period_type'])==(key[0],key[1],'quarter')}
        errors=[e['reason'] for e in result['diagnostics'] if
                (e['year'],e['quarter'])==key]
        if set(REQUIRED)-metrics or errors:
            raise ValueError('Frende Skade original PDF import blocked for '
                             +str(key)+': '+str(errors or sorted(set(REQUIRED)-metrics)))
    fd,tmp=tempfile.mkstemp(prefix='.frende-skade-',suffix='.json',dir=OUTPUT.parent)
    try:
        with os.fdopen(fd,'w',encoding='utf-8') as out:
            json.dump(result,out,ensure_ascii=False,indent=2);out.write('\n')
        os.replace(tmp,OUTPUT)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)
    print('FRENDE_SKADE_PDF_VERIFIED',len(result['observations']),'diagnostics',len(result['diagnostics']))
if __name__=='__main__':run()
