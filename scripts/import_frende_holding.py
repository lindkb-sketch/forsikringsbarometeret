#!/usr/bin/env python3
"""Issuer-linked Frende Holding Wrepit report importer; strictly verified table columns."""
import hashlib
import json
import os
import re
import tempfile
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path
from audit_financials import DATA, audit

ROOT=Path(__file__).resolve().parents[1]
CANDIDATES=ROOT/'data/frende_fremtind_candidates.json'
FIELDS={'Kostnads %':'expense_ratio','Skadeprosent f.e.r':'loss_ratio','Combined ratio':'combined_ratio'}
HEADER=re.compile(r'^Q([1-4]) (20\d{2})$',re.I)

class TableReader(HTMLParser):
    def __init__(self):
        super().__init__();self.depth=0;self.cell=None;self.row=[];self.rows=[]
    def handle_starttag(self,tag,attrs):
        if tag=='table':self.depth+=1
        if self.depth and tag=='tr':self.row=[]
        if self.depth and tag in ('th','td'):self.cell=[]
    def handle_data(self,data):
        if self.cell is not None:self.cell.append(data)
    def handle_endtag(self,tag):
        if self.depth and tag in ('th','td') and self.cell is not None:
            self.row.append(' '.join(' '.join(self.cell).split()));self.cell=None
        if self.depth and tag=='tr' and self.row:self.rows.append(self.row)
        if tag=='table':self.depth=max(0,self.depth-1)

def number(raw,percent=False):
    value=raw.strip().replace('\u00a0',' ').replace(' ','')
    if percent:
        if not value.endswith('%'):raise ValueError('Expected percentage')
        value=value[:-1]
    if not re.fullmatch(r'-?\d+(?:,\d+)?',value):raise ValueError('Invalid financial number '+raw)
    return float(value.replace(',','.'))

def extract(section_html,url,year,quarter):
    if not re.search(r'Nøkkeltall konsern',section_html,re.I):
        raise ValueError('Not the official group KPI section')
    t=TableReader();t.feed(section_html)
    if not t.rows:raise ValueError('Missing KPI table')
    header=t.rows[0]
    if header[0]!='Tall i 1000' or len(header)<3 or header[1]!=f'Q{quarter} {year}':
        raise ValueError('Unexpected report KPI header')
    ytd_col=None
    if quarter>1:
        label=f'Pr Q{quarter} {year}'
        if label in header:ytd_col=header.index(label)
        elif quarter==4 and str(year) in header:ytd_col=header.index(str(year))
        elif quarter!=4:raise ValueError('Missing YTD column')
    records={row[0]:row for row in t.rows[1:] if row}
    missing=[label for label in FIELDS if label not in records]
    if missing and not (quarter==4 and missing==['Kostnads %']):
        raise ValueError('Missing required KPI rows: '+repr(missing))
    if 'Resultat før skatt' not in records:raise ValueError('Missing income KPI')
    digest=hashlib.sha256(section_html.encode('utf-8')).hexdigest()
    results=[]
    for period,col in [('quarter',1)]+([('ytd',ytd_col)] if ytd_col else ([('ytd',1)] if quarter==1 else [])):
        values={metric:number(records[label][col],True) for label,metric in FIELDS.items() if label in records}
        calculated_expense='expense_ratio' not in values
        if calculated_expense:
            values['expense_ratio']=round(values['combined_ratio']-values['loss_ratio'],3)
        if abs(values['combined_ratio']-values['loss_ratio']-values['expense_ratio'])>0.25:
            raise ValueError('Combined ratio does not reconcile')
        for label,metric in FIELDS.items():
            results.append({'company':'Frende','year':year,'quarter':quarter,'scope':'group',
                'period_type':period,'metric':metric,'value':values[metric],'unit':'percent',
                'status':'calculated' if calculated_expense and metric=='expense_ratio' else 'reported',
                **({'calculation':'combined_ratio - loss_ratio'} if calculated_expense and metric=='expense_ratio' else {}),
                'source_type':'official_quarterly_report','source_url':url,
                'source_page':6,'source_entity':'Frende Holding AS konsern',
                'source_document_period':f'Q{quarter} {year}','source_definition':label,
                'source_sha256':digest})
    return results

def extract_revenue(section_html,url,year,quarter):
    if not re.search(r'Resultatregnskap',section_html,re.I):raise ValueError('Missing group income statement')
    t=TableReader();t.feed(section_html)
    if not t.rows or t.rows[0][0]!='Resultatregnskap':raise ValueError('Invalid income statement header')
    header=t.rows[0]
    if header[1]!=f'{quarter}. kv {year}':raise ValueError('Wrong income statement quarter')
    rows={r[0]:r for r in t.rows[1:] if r}
    label='Sum driftsinntekter'
    if label not in rows:raise ValueError('Missing group operating revenue')
    values=[('quarter',1)]
    if quarter==1:values.append(('ytd',1))
    else:
        period={2:f'30.06.{str(year)[2:]}',3:f'30.09.{str(year)[2:]}',4:f'31.12.{str(year)[2:]}'}[quarter]
        variants=(period,f'01.01-{period}')
        match=next((header.index(v) for v in variants if v in header),None)
        if match is not None:values.append(('ytd',match))
        elif quarter!=4:raise ValueError('Missing income YTD header')
    digest=hashlib.sha256(section_html.encode('utf-8')).hexdigest()
    result=[]
    for period,col in values:
        amount=number(rows[label][col])/1000
        result.append({'company':'Frende','year':year,'quarter':quarter,'scope':'group',
            'period_type':period,'metric':'insurance_revenue','value':round(amount,3),'unit':'NOKm',
            'status':'reported','source_type':'official_quarterly_report','source_url':url,
            'source_page':7,'source_entity':'Frende Holding AS konsern',
            'source_document_period':f'Q{quarter} {year}',
            'source_definition':'Sum driftsinntekter (group operating revenue, not insurance-only revenue)',
            'source_sha256':digest})
    return result

def extract_historical_revenue(section_html,url,year,quarter):
    """Historical same-quarter/YTD comparisons from issuer-labelled columns.

    A Q3 2025 report is the official source for Q3 2024. Do not mistake
    annual YTD for isolated quarter, or premiums for group operating income.
    """
    t=TableReader()
    t.feed(section_html)
    if not t.rows or t.rows[0][0]!='Resultatregnskap':
        raise ValueError('Historical Frende income source not verified')
    header=t.rows[0]
    if f'{quarter}. kv {year}' not in header or f'{quarter}. kv {year-1}' not in header:
        return []
    records={r[0]:r for r in t.rows[1:] if r}
    if 'Sum driftsinntekter' not in records:
        raise ValueError('Historical Frende group operating revenue missing')
    values=[('quarter',header.index(f'{quarter}. kv {year-1}'))]
    if quarter>1:
        date={2:'30.06.',3:'30.09.',4:'31.12.'}[quarter]+str(year-1)[2:]
        matches=[i for i,h in enumerate(header) if h in (date,'01.01-'+date)]
        if len(matches)==1:
            values.append(('ytd',matches[0]))
        elif len(matches)>1:
            raise ValueError('Ambiguous historical Frende YTD source column')
    elif quarter==1:
        values.append(('ytd',values[0][1]))
    digest=hashlib.sha256(section_html.encode('utf-8')).hexdigest()
    result=[]
    for period,column in values:
        amount=number(records['Sum driftsinntekter'][column])/1000
        result.append({'company':'Frende','year':year-1,'quarter':quarter,
            'scope':'group','period_type':period,'metric':'insurance_revenue',
            'value':round(amount,3),'unit':'NOKm','status':'reported',
            'source_type':'official_quarterly_report','source_url':url,'source_page':7,
            'source_entity':'Frende Holding AS konsern',
            'source_document_period':f'Q{quarter} {year}',
            'source_definition':'Sum driftsinntekter (group operating revenue, not insurance-only revenue); prior-year comparative column',
            'source_sha256':digest})
    return result

def extract_insurance_result(section_html,url,year,quarter):
    t=TableReader();t.feed(section_html)
    if not t.rows or t.rows[0][0]!='Resultatregnskap':raise ValueError('Income statement missing')
    header=t.rows[0]; data={row[0]:row for row in t.rows[1:] if row}
    labels=('Sum driftsinntekter','Sum erstatningskostnader og endring forsikringstekniske avsetninger','Sum driftskostnader')
    if any(k not in data for k in labels):raise ValueError('Insurance subtotals missing')
    columns=[(year,'quarter',header.index(f'{quarter}. kv {year}'))]
    if f'{quarter}. kv {year-1}' in header:columns.append((year-1,'quarter',header.index(f'{quarter}. kv {year-1}')))
    for y in (year,year-1):
        date={1:'31.03.',2:'30.06.',3:'30.09.',4:'31.12.'}[quarter]+str(y)[2:]
        matches=[i for i,h in enumerate(header) if h in (date,'01.01-'+date)]
        if len(matches)>1:raise ValueError('Ambiguous YTD')
        if matches:columns.append((y,'ytd',matches[0]))
        elif quarter==1:columns += [(yy,'ytd',i) for yy,p,i in columns if yy==y and p=='quarter']
    result=[]
    for y,period,col in columns:
        a,c,e=[number(data[k][col]) for k in labels]
        if a<=0 or c>0 or e>0:raise ValueError('Unexpected cost signs')
        result.append(dict(company='Frende',year=y,quarter=quarter,scope='group',period_type=period,metric='insurance_service_result',value=round((a+c+e)/1000,3),unit='NOKm',status='calculated',source_type='official_quarterly_report',source_url=url,source_page=7,source_entity='Frende Holding AS konsern',source_document_period=f'Q{quarter} {year}',source_definition='Driftsresultat fra forsikring uten finansinntekter',calculation='operating revenue plus signed claims/reserve and operating expense subtotals',calculation_inputs={'revenue':a/1000,'claims_reserves':c/1000,'operating_costs':e/1000},source_sha256=hashlib.sha256(section_html.encode()).hexdigest()))
    return result

def read(url,section=6):
    parsed=urllib.parse.urlparse(url)
    if parsed.scheme!='https' or parsed.hostname!='frende.wrep.it' or not re.fullmatch(r'/q[1-4]-20\d{2}-frende-holding-as',parsed.path):
        raise ValueError('Untrusted Frende publisher URL')
    req=urllib.request.Request(url+f'/sec/{section}',headers={'User-Agent':'Mozilla/5.0'})
    with urllib.request.urlopen(req,timeout=25) as response:
        if urllib.parse.urlparse(response.geturl()).hostname!='frende.wrep.it':
            raise ValueError('Untrusted redirect')
        data=response.read(1_000_001)
    if len(data)>1_000_000:raise ValueError('Publisher response too large')
    return data.decode('utf-8')

def run():
    snapshot=json.loads(CANDIDATES.read_text())
    if not snapshot.get('complete'):raise ValueError('Issuer discovery incomplete')
    candidates=[r for r in snapshot.get('candidates',[]) if r.get('company')=='Frende'
                and r.get('year',0)>=2025 and r.get('source_format')=='publisher_html']
    existing=json.loads(DATA.read_text())
    seen={(r['year'],r['quarter'],r['period_type'],r['metric']) for r in existing['observations']
          if r['company']=='Frende' and r.get('scope')=='group'}
    imported=[];errors=[];verified=[]
    for item in candidates:
        url=item['document_url']
        try:
            match=re.fullmatch(r'https://frende\.wrep\.it/q([1-4])-(20\d{2})-frende-holding-as',url)
            if not match:continue
            quarter,year=map(int,match.groups())
            if (year,quarter)!=(item['year'],item['quarter']):raise ValueError('Discovery and publisher period mismatch')
            rows=extract(read(url),url+'/sec/6',year,quarter)
            income=read(url,7)
            rows+=extract_revenue(income,url+'/sec/7',year,quarter)
            rows+=extract_historical_revenue(income,url+'/sec/7',year,quarter)
            rows+=extract_insurance_result(income,url+'/sec/7',year,quarter)
            verified.append([year,quarter])
            for row in rows:
                key=(row['year'],row['quarter'],row['period_type'],row['metric'])
                if key not in seen:imported.append(row);seen.add(key)
        except Exception as exc:errors.append({'url':url,'reason':str(exc)})
    if not verified:raise ValueError('No verified Frende issuer tables: '+json.dumps(errors[:4]))
    # The newest issuer-listed quarter must never be silently skipped if its
    # layout changes. Older archives can have incompatible historical layouts.
    latest=max((r['year'],r['quarter']) for r in candidates)
    if list(latest) not in verified:
        raise ValueError('Latest Frende Holding quarter could not be verified: '+str(latest)+'; '+json.dumps(errors[:5]))
    # A newly indexed official PDF cannot be ignored merely because the
    # current validated parser supports the publisher HTML representation.
    all_periods=[(r['year'],r['quarter']) for r in snapshot.get('candidates',[])
                 if r.get('company')=='Frende' and r.get('year',0)>=2025
                 and isinstance(r.get('quarter'),int)]
    if all_periods and max(all_periods)>max(map(tuple,verified)):
        raise ValueError('Newer official Frende quarter discovered but not verified/imported: '+str(max(all_periods)))
    if imported:
        merged={**existing,'observations':existing['observations']+imported}
        check=audit(merged)
        if not check['ok']:raise ValueError('Financial audit failed: '+str(check['errors'][:8]))
        fd,path=tempfile.mkstemp(dir=DATA.parent,prefix='.frende-',suffix='.json')
        try:
            with os.fdopen(fd,'w') as out:json.dump(merged,out,ensure_ascii=False,indent=2);out.write('\n')
            os.replace(path,DATA)
        finally:
            if os.path.exists(path):os.unlink(path)
    print(json.dumps({'imported':len(imported),'verified_quarters':verified,'rejected':errors[:5]}))
    return len(imported)

if __name__=='__main__':run()
