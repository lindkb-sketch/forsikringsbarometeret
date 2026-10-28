#!/usr/bin/env python3
"""Auto-import official Gjensidige Norway PM/BM from quarterly XLSX files."""
import hashlib,json,tempfile
from datetime import date
from pathlib import Path
from audit_financials import DATA,audit
from build_verified_feed import publish
from discover_gjensidige_excel import discover
from gjensidige_segments import extract
from publish_geographic_workbooks import download,atomic_write

METRICS=('insurance_revenue','insurance_service_result','loss_ratio','expense_ratio','combined_ratio')
SEGMENTS=('Private Norway','Commercial Norway')
KEYS=('company','year','quarter','scope','segment','period_type','metric')
def key(r):return tuple(r.get(k) for k in KEYS)

def prepare(data,year,quarter,discoverer=discover,fetcher=download):
    urls=discoverer(year,quarter)
    if not urls:raise ValueError(f'Official Gjensidige Q{quarter} {year} Excel workbook not discovered; refusing silent skip')
    if len(urls)!=1:raise ValueError('Ambiguous official Gjensidige XLSX sources: '+repr(urls))
    url=urls[0]
    group=[r for r in data['observations'] if r.get('company')=='Gjensidige'
           and r.get('year')==year and r.get('quarter')==quarter
           and r.get('scope')=='group' and r.get('metric')=='insurance_revenue'
           and r.get('period_type')=='quarter']
    if len(group)!=1:raise ValueError('Cannot bind XLSX to verified official group report')
    pdf=group[0]['source_url']
    blob=fetcher(url)
    with tempfile.TemporaryDirectory() as folder:
        path=Path(folder)/'official.xlsx';path.write_bytes(blob)
        segments=extract(path,year,quarter,url,pdf)
    digest=hashlib.sha256(blob).hexdigest()
    for row in segments:row['source_sha256']=digest;row['source_scope']='reported_segment'
    additions=list(segments)
    for metric in METRICS:
        pm=next(r for r in segments if r['segment']==SEGMENTS[0] and r['metric']==metric)
        bm=next(r for r in segments if r['segment']==SEGMENTS[1] and r['metric']==metric)
        if metric in ('insurance_revenue','insurance_service_result'):
            value=pm['value']+bm['value']
        else:
            revpm=next(r['value'] for r in segments if r['segment']==SEGMENTS[0] and r['metric']=='insurance_revenue')
            revbm=next(r['value'] for r in segments if r['segment']==SEGMENTS[1] and r['metric']=='insurance_revenue')
            if min(revpm,revbm)<=0:raise ValueError('Invalid Norway revenue weights')
            value=(pm['value']*revpm+bm['value']*revbm)/(revpm+revbm)
        additions.append(dict(company='Gjensidige',year=year,quarter=quarter,
            scope='norway',period_type='quarter',metric=metric,value=value,
            unit=pm['unit'],status='calculated',
            calculation='sum_official_norway_segments' if metric in ('insurance_revenue','insurance_service_result') else 'revenue_weighted_official_norway_segments',
            source_type='official_investor_tables',source_url=url,source_document_url=pdf,
            source_sha256=digest,source_scope='norway'))
    old={key(r):r for r in data['observations']}
    staged=[]
    for row in additions:
        k=key(row)
        if k in old:
            if abs(old[k]['value']-row['value'])>(0.3 if row['unit']=='percent' else 0.25):
                raise ValueError('Official Excel conflicts with verified observation: '+str(k))
        else:staged.append(row)
    merged={**data,'observations':data['observations']+staged}
    check=audit(merged)
    if not check['ok']:raise ValueError('Gjensidige Excel audit failed: '+repr(check['errors']))
    return merged,len(staged)

def run():
    data=json.loads(DATA.read_text(encoding='utf-8'))
    today=date.today();count=0
    periods=sorted({(r['year'],r['quarter']) for r in data['observations']
        if r.get('company')=='Gjensidige' and r.get('scope')=='group'
        and r.get('period_type')=='quarter' and r.get('year',0)>=2026})
    for year,quarter in periods:
        if all(any(r.get('company')=='Gjensidige' and r.get('year')==year and
                   r.get('quarter')==quarter and r.get('scope')=='reported_segment'
                   and r.get('segment')==segment and r.get('metric')=='combined_ratio'
                   for r in data['observations']) for segment in SEGMENTS):continue
        data,added=prepare(data,year,quarter)
        count+=added
    if count:atomic_write(DATA,data)
    publish()
    print('Gjensidige official Excel Norway observations imported:',count)

if __name__=='__main__':run()
