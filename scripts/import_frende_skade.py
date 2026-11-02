#!/usr/bin/env python3
"""Independent, fail-closed Frende Skadeforsikring AS quarterly financial importer.

Only issuer-hosted report sections containing an explicit subsidiary identity,
period headers and recognizable tables qualify. Missing evidence never creates
estimated values or reuses Frende Holding group observations.
"""
import hashlib
import json
import os
import re
import tempfile
import urllib.parse
import urllib.request
from pathlib import Path
from import_frende_holding import TableReader, number

ROOT=Path(__file__).resolve().parents[1]
REPORTS=ROOT/'data/frende_skade_reports.json'
OUTPUT=ROOT/'data/frende_skade_financials.json'
ENTITY='Frende Skadeforsikring AS'
FIELDS={'Kostnads %':'expense_ratio','Skadeprosent f.e.r':'loss_ratio',
        'Combined ratio':'combined_ratio'}
REQUIRED={'combined_ratio','loss_ratio','expense_ratio','insurance_revenue'}
HOST='frende.wrep.it'

def read_section(base, section):
    parsed=urllib.parse.urlparse(base)
    if parsed.scheme!='https' or parsed.hostname!=HOST or not re.fullmatch(
            r'/q[1-4]-20\d{2}-frende-skadeforsikring-as', parsed.path):
        raise ValueError('Not a trusted Frende Skade publisher report')
    req=urllib.request.Request(base+'/sec/'+str(section),
                               headers={'User-Agent':'Mozilla/5.0'})
    with urllib.request.urlopen(req,timeout=30) as resp:
        if urllib.parse.urlparse(resp.geturl()).hostname!=HOST:
            raise ValueError('Untrusted report redirect')
        blob=resp.read(1_000_001)
    if len(blob)>1_000_000:raise ValueError('Oversized publisher section')
    return blob.decode('utf-8')

def parse_kpis(html, url, year, quarter):
    if not re.search(r'Nøkkeltall',html,re.I):
        raise ValueError('Missing KPI heading')
    reader=TableReader();reader.feed(html)
    rows=[r for r in reader.rows if r]
    header=next((r for r in rows if len(r)>2 and r[0] in ('Tall i 1000','Nøkkeltall')
                 and r[1]==f'Q{quarter} {year}'),None)
    if header is None:raise ValueError('KPI heading does not match report quarter')
    mapping={r[0]:r for r in rows if r[0] in FIELDS}
    if not all(label in mapping for label in ('Skadeprosent f.e.r','Combined ratio')):
        raise ValueError('Missing official claims/combined ratio')
    digest=hashlib.sha256(html.encode()).hexdigest()
    result=[]
    cols=[('quarter',1)]
    if quarter==1:cols.append(('ytd',1))
    elif f'Pr Q{quarter} {year}' in header:cols.append(('ytd',header.index(f'Pr Q{quarter} {year}')))
    elif quarter==4 and str(year) in header:cols.append(('ytd',header.index(str(year))))
    for period,col in cols:
        vals={metric:number(mapping[label][col],True) for label,metric in FIELDS.items() if label in mapping}
        calculated='expense_ratio' not in vals
        if calculated: vals['expense_ratio']=round(vals['combined_ratio']-vals['loss_ratio'],3)
        if abs(vals['combined_ratio']-vals['loss_ratio']-vals['expense_ratio'])>0.25:
            raise ValueError('Subsidiary combined ratio does not reconcile')
        for label,metric in FIELDS.items():
            result.append(dict(year=year,quarter=quarter,period_type=period,
                metric=metric,value=vals[metric],unit='percent',
                status='calculated' if calculated and metric=='expense_ratio' else 'reported',
                source_definition=label,
                **({'calculation':'combined_ratio - loss_ratio'} if calculated and metric=='expense_ratio' else {}),
                source_url=url,source_sha256=digest,source_section='Nøkkeltall',
                source_entity=ENTITY,source_type='official_quarterly_report'))
    return result

def parse_income(html,url,year,quarter):
    reader=TableReader();reader.feed(html)
    rows=[r for r in reader.rows if r]
    head=next((r for r in rows if len(r)>1 and r[0]=='Resultatregnskap'
               and r[1]==f'{quarter}. kv {year}'),None)
    if head is None:raise ValueError('Subsidiary income table / period not verified')
    data={r[0]:r for r in rows}
    # Unlike Holding, do not call total operating revenue IFRS 17 insurance revenue.
    label=next((x for x in ('Sum driftsinntekter','Premieinntekter for egen regning')
                if x in data),None)
    if label is None:raise ValueError('No verified subsidiary revenue row')
    cols=[('quarter',1)]
    if quarter==1:cols.append(('ytd',1))
    else:
        date={2:'30.06.',3:'30.09.',4:'31.12.'}[quarter]+str(year)[2:]
        indexes=[i for i,h in enumerate(head) if h in (date,'01.01-'+date)]
        if len(indexes)>1:raise ValueError('Ambiguous YTD revenue column')
        if indexes:cols.append(('ytd',indexes[0]))
    digest=hashlib.sha256(html.encode()).hexdigest()
    out=[]
    for period,col in cols:
        value=number(data[label][col])/1000
        if value<=0:raise ValueError('Nonpositive reported revenue')
        out.append(dict(year=year,quarter=quarter,period_type=period,metric='insurance_revenue',
                        value=round(value,3),unit='NOKm',status='reported',
                        source_definition=label+' (Frende Skadeforsikring AS, NOKm; not group)',
                        source_url=url,source_sha256=digest,source_section='Resultatregnskap',
                        source_entity=ENTITY,source_type='official_quarterly_report'))
    return out

def verify_period(base,year,quarter,reader=read_section):
    m=re.fullmatch(r'https://frende\.wrep\.it/q([1-4])-(20\d{2})-frende-skadeforsikring-as',base)
    if not m or (int(m[2]),int(m[1]))!=(year,quarter):
        raise ValueError('Wrong subsidiary or quarter URL')
    kpis=reader(base,6)
    income=reader(base,7)
    # Require explicit legal entity in at least one report section.
    if 'Frende Skadeforsikring' not in kpis+' '+income:
        raise ValueError('Subsidiary legal entity absent from report')
    rows=parse_kpis(kpis,base+'/sec/6',year,quarter)
    rows+=parse_income(income,base+'/sec/7',year,quarter)
    metrics={r['metric'] for r in rows if r['period_type']=='quarter'}
    if not REQUIRED<=metrics:raise ValueError('Incomplete subsidiary KPI quarter')
    return rows

def build(report_index, previous=None, reader=read_section):
    observations={}
    for row in (previous or {}).get('observations',[]):
        observations[(row['year'],row['quarter'],row['period_type'],row['metric'])]=row
    problems=[]
    for record in report_index['reports']:
        year,quarter=record['year'],record['quarter']
        if year<2025:continue
        url=record['source_url']
        # Publisher HTML is useful for layout diagnostics but is NOT a PDF
        # source. Refuse numerical publication until the original issuer PDF
        # is separately downloaded, parsed and its values corroborated.
        if not str(record.get('pdf_url','')).lower().split('?')[0].endswith('.pdf'):
            problems.append({'year':year,'quarter':quarter,'reason':'Original issuer PDF not verified; Wrepit HTML cannot authorize figures'})
            continue
        if not url.startswith('https://frende.wrep.it/'):continue
        try:
            rows=verify_period(url,year,quarter,reader)
            for row in rows:
                key=(row['year'],row['quarter'],row['period_type'],row['metric'])
                if key in observations and observations[key]['value']!=row['value']:
                    raise ValueError('Verified subsidiary financial value changed: '+str(key))
            for row in rows:
                observations[(row['year'],row['quarter'],row['period_type'],row['metric'])]=row
        except (OSError,ValueError,IndexError,KeyError) as exc:
            problems.append({'year':year,'quarter':quarter,'reason':str(exc)[:180]})
    return {'entity':ENTITY,'source_policy':'issuer report only, never Excel',
            'observations':sorted(observations.values(),key=lambda r:(r['year'],r['quarter'],r['period_type'],r['metric'])),
            'diagnostics':problems}

def run():
    reports=json.loads(REPORTS.read_text(encoding='utf-8'))
    previous=json.loads(OUTPUT.read_text(encoding='utf-8')) if OUTPUT.exists() else None
    result=build(reports,previous)
    fd,tmp=tempfile.mkstemp(prefix='.frende-skade-',suffix='.json',dir=OUTPUT.parent)
    try:
        with os.fdopen(fd,'w',encoding='utf-8') as output:
            json.dump(result,output,ensure_ascii=False,indent=2);output.write('\n')
        os.replace(tmp,OUTPUT)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)
    print('FRENDE_SKADE_VERIFIED',len(result['observations']),'issues',len(result['diagnostics']))
if __name__=='__main__':run()
