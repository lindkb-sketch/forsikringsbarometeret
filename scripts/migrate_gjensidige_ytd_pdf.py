#!/usr/bin/env python3
"""Replace legacy Gjensidige Q2 2026 Norway YTD workbook rows using official PDF.

Reads independently labelled YTD 2026 values from Private Norway and
Commercial Norway tables; never maps Q2-only columns to YTD.
"""
import hashlib
import json
import re
from audit_financials import DATA,audit
from ingest_official_pdf import download,read_pdf
from publish_geographic_workbooks import atomic_write

PDF='https://mb.cision.com/Public/1122/4373892/b3fb98691b4814f0.pdf'
LABELS={'insurance_revenue':'Insurance revenue',
        'insurance_service_result':'Insurance service result',
        'loss_ratio':'Loss ratio, net of reinsurance',
        'expense_ratio':'Cost ratio','combined_ratio':'Combined ratio'}
SEGMENTS=('Private Norway','Commercial Norway')
NUMBER=r'-?\\d[\\d,]*\\.\\d+'
def source_values(pages):
    result={}
    pages_by_segment={}
    for segment in SEGMENTS:
        name='General Insurance '+segment
        found=[(num,text) for num,text in pages
               if name in text and 'YTD 2026' in text and 'YTD 2025' in text
               and 'Insurance revenue' in text and 'Combined ratio' in text]
        if len(found)!=1:raise ValueError('Ambiguous official YTD table: '+name)
        page,txt=found[0]
        pages_by_segment[segment]=page
        result[segment]={}
        for metric,label in LABELS.items():
            matching=[line for line in txt.splitlines()
                      if re.match(r'^\\s*'+re.escape(label)+r'(?:[¹²³⁴⁵⁶⁷⁸⁹⁰* ]+)?\\s+[-\\d]',line,re.I)]
            if len(matching)!=1:raise ValueError('Ambiguous source row: '+segment+' '+metric)
            tail=re.sub(r'^\\s*'+re.escape(label), '',matching[0],flags=re.I)
            nums=re.findall(NUMBER,tail)
            # Q2 2026, Q2 2025, YTD 2026, YTD 2025, FY 2025
            if len(nums)<5:raise ValueError('Missing distinct YTD column: '+segment+' '+metric)
            result[segment][metric]=float(nums[2].replace(',',''))
    return result,pages_by_segment

def replace(data,values,pages,digest):
    old=data['observations']
    legacy=[r for r in old if r.get('source_type')=='official_investor_tables']
    if not legacy:return data,0
    if len(legacy)!=5 or any(r.get('company')!='Gjensidige' or
      (r.get('year'),r.get('quarter'),r.get('period_type'),r.get('scope'))!=(2026,2,'ytd','norway')
      for r in legacy):
        raise ValueError('Unrecognized workbook data remain; refusing partial migration')
    reven={s:values[s]['insurance_revenue'] for s in SEGMENTS}
    total=sum(reven.values())
    replacements={}
    for r in legacy:
        metric=r['metric']
        if metric not in LABELS:raise ValueError('Unexpected legacy metric '+metric)
        if metric in ('insurance_revenue','insurance_service_result'):
            val=sum(values[s][metric] for s in SEGMENTS)
            calculation='sum_official_norway_segments'
        else:
            val=sum(values[s][metric]*reven[s] for s in SEGMENTS)/total
            calculation='revenue_weighted_official_norway_segments'
        if abs(val-r['value'])> (0.4 if metric in ('insurance_revenue','insurance_service_result') else 0.3):
            raise ValueError('PDF and legacy YTD diverge; explicit review required: '+metric+
                             ' PDF='+str(val)+' old='+str(r['value']))
        history=list(r.get('source_revision_history',[]))
        history.append({field:r.get(field) for field in ('value','source_url','source_type','source_sheet','source_cell','source_sha256')})
        new={k:v for k,v in r.items() if k not in ('source_sheet','source_cell','source_document_url')}
        new.update(value=val,unit='percent' if metric in ('loss_ratio','expense_ratio','combined_ratio') else 'MNOK',
            status='calculated',calculation=calculation,source_type='official_quarterly_report',
            source_url=PDF,source_page=pages['Private Norway'],source_sha256=digest,
            source_section='General Insurance Private Norway + Commercial Norway',
            source_document_period='Q2 2026',source_revision_history=history)
        replacements[id(r)]=new
    result={**data,'observations':[replacements.get(id(r),r) for r in old]}
    if not audit(result)['ok']:raise ValueError('Official PDF migration failed financial audit')
    return result,len(legacy)

def run():
    data=json.loads(DATA.read_text(encoding='utf-8'))
    if not any(r.get('source_type')=='official_investor_tables' for r in data['observations']):
        print('PDF_YTD_MIGRATION_ALREADY_COMPLETE');return
    blob=download(PDF)
    values,pages=source_values(read_pdf(blob))
    updated,n=replace(data,values,pages,hashlib.sha256(blob).hexdigest())
    if n:atomic_write(DATA,updated)
    print('OFFICIAL_PDF_YTD_EXCEL_ROWS_REPLACED',n,'PAGES',pages,flush=True)
if __name__=='__main__':run()
