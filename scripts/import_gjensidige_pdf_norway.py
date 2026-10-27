#!/usr/bin/env python3
"""Import Gjensidige Norway PM/BM directly from its official quarterly PDF.

Only explicitly labelled Private Norway and Commercial Norway tables are used.
Missing/ambiguous cells fail closed; no financial amounts are embedded in code.
"""
import hashlib
import json
import re
from datetime import date
from pathlib import Path
from audit_financials import DATA, audit
from build_verified_feed import publish
from ingest_official_pdf import download, read_pdf
from publish_geographic_workbooks import atomic_write

METRICS={
    'insurance_revenue':r'Insurance revenue',
    'insurance_service_result':r'Insurance service result',
    'loss_ratio':r'Loss ratio, net of reinsurance',
    'expense_ratio':r'Cost ratio',
    'combined_ratio':r'Combined ratio',
}
SEGMENTS=('Private Norway','Commercial Norway')
KEYS=('company','year','quarter','scope','segment','period_type','metric')
def key(r):return tuple(r.get(k) for k in KEYS)

def parse(pages,year,quarter,url,digest):
    rows=[]
    for segment in SEGMENTS:
        title='General Insurance '+segment
        # The printed segment KPI table has a full heading and five dated columns.
        matches=[(page,txt) for page,txt in pages
                 if re.search(re.escape(title),txt,re.I)
                 and re.search(r'Q\s*'+str(quarter)+r'\s*'+str(year),txt,re.I)
                 and 'Insurance revenue' in txt and 'Combined ratio' in txt]
        if len(matches)!=1:
            raise ValueError('Missing or ambiguous official Norway segment table: '+title)
        page,txt=matches[0]
        for metric,pattern in METRICS.items():
            lines=[line for line in txt.splitlines() if re.match(r'^\s*'+pattern+r'(?:[¹²³⁴⁵⁶⁷⁸⁹⁰* ]+)?\s+[-\d]',line,re.I)]
            if len(lines)!=1:
                raise ValueError('Missing or ambiguous '+metric+' in '+title)
            values=re.findall(r'-?\d[\d,]*\.\d+',lines[0][len(re.match(r'^\s*'+pattern,lines[0],re.I).group(0)):])
            if len(values)<2:raise ValueError('Missing comparative columns: '+title+' '+metric)
            for yr,idx in ((year,0),(year-1,1)):
                value=float(values[idx].replace(',',''))
                rows.append(dict(company='Gjensidige',year=yr,quarter=quarter,
                    scope='reported_segment',segment=segment,period_type='quarter',
                    metric=metric,value=value,unit='percent' if 'ratio' in metric else 'MNOK',
                    status='reported',source_type='official_quarterly_report',
                    source_url=url,source_page=page,source_sha256=digest,
                    source_section=title))
    return rows

def prepare(data,fetcher=download,reader=read_pdf):
    observations=data['observations']
    sources={(r['year'],r['quarter'],r['source_url']) for r in observations
        if r.get('company')=='Gjensidige' and r.get('scope')=='group'
        and r.get('period_type')=='quarter' and r.get('metric')=='combined_ratio'
        and r['year']>=2026}
    existing={key(r):r for r in observations}
    additions=[]
    for year,quarter,url in sorted(sources):
        if all(('Gjensidige',year,quarter,'reported_segment',seg,'quarter','combined_ratio') in existing
               for seg in SEGMENTS):continue
        blob=fetcher(url)
        if not blob.startswith(b'%PDF-'):raise ValueError('Not official PDF')
        batch=parse(reader(blob),year,quarter,url,hashlib.sha256(blob).hexdigest())
        for r in batch:
            k=key(r)
            if k in existing:
                if abs(existing[k]['value']-r['value'])>0.15:
                    raise ValueError('Conflicting verified segment value '+str(k))
            elif k not in {key(x) for x in additions}:additions.append(r)
        # Norway totals must be derived from two independently identified
        # country segments; never substitute group or Nordic figures.
        for yr in (year,year-1):
            segrows=[r for r in batch if r['year']==yr]
            revenue={s:next(r['value'] for r in segrows if r['segment']==s and r['metric']=='insurance_revenue') for s in SEGMENTS}
            for metric in METRICS:
                vals={s:next(r['value'] for r in segrows if r['segment']==s and r['metric']==metric) for s in SEGMENTS}
                if metric in ('insurance_revenue','insurance_service_result'):
                    value=sum(vals.values())
                else:
                    value=sum(vals[s]*revenue[s] for s in SEGMENTS)/sum(revenue.values())
                k=('Gjensidige',yr,quarter,'norway',None,'quarter',metric)
                if k in existing:
                    if abs(existing[k]['value']-value)>(0.3 if 'ratio' in metric else 0.25):
                        raise ValueError('Norway total does not reconcile: '+str(k))
                    continue
                additions.append(dict(company='Gjensidige',year=yr,quarter=quarter,
                    scope='norway',period_type='quarter',metric=metric,value=value,
                    unit='percent' if 'ratio' in metric else 'MNOK',status='calculated',
                    calculation='revenue_weighted_official_norway_segments' if 'ratio' in metric else 'sum_official_norway_segments',
                    source_type='official_quarterly_report',source_url=url,
                    source_page=segrows[0]['source_page'],source_sha256=segrows[0]['source_sha256'],
                    source_section='General Insurance Private Norway + Commercial Norway'))
    merged={**data,'observations':observations+additions}
    result=audit(merged)
    if not result['ok']:raise ValueError('Norway PDF audit failed: '+repr(result['errors']))
    return merged,len(additions)

def run():
    data=json.loads(DATA.read_text(encoding='utf-8'))
    merged,count=prepare(data)
    if count:atomic_write(DATA,merged)
    publish()
    print('Gjensidige official PDF Norway rows added:',count)

if __name__=='__main__':run()
