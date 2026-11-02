#!/usr/bin/env python3
"""Official Frende Skade standalone-quarter importer (not Holding group)."""
import hashlib,io,json,re,urllib.request,urllib.parse
from pathlib import Path
import pdfplumber
from audit_financials import DATA,audit
from publish_geographic_workbooks import atomic_write
from discover_frende_skade import INDEX,discover
from import_frende_holding import TableReader,number

METRICS={
 'Premieinntekter for egen regning':'insurance_revenue',
 'Resultat av teknisk regnskap i skadeforsikring':'insurance_service_result',
 'Kostnadsandel %':'expense_ratio',
 'Skade % E/R':'loss_ratio',
 'Combined Ratio':'combined_ratio'}
ENTITY='Frende Skadeforsikring AS'

def parse_table(markup,year,quarter,url,source_hash):
    """Read individual HTML table cells, never flattened whitespace."""
    t=TableReader();t.feed(markup)
    headers=[row for row in t.rows if row and row[0]=='Resultatregnskap']
    if len(headers)!=1:raise ValueError('Missing/duplicate report header')
    h=' '.join(headers[0]).replace(' ','').lower()
    if not all(str(quarter)+'.kv.'+str(y) in h for y in (year,year-1)):
        raise ValueError('Wrong quarter comparison')
    values={}
    for label in METRICS:
        matches=[r for r in t.rows if r and r[0]==label]
        if len(matches)!=1 or len(matches[0])<3:raise ValueError('Ambiguous KPI '+label)
        values[label]=matches[0][1:3]
    return observations(values,year,quarter,url,source_hash)

def observations(values,year,quarter,url,digest):
    rows=[]
    for label,metric in METRICS.items():
        pair=values[label]
        for y,raw in zip((year,year-1),pair):
            raw=str(raw).replace(' ','').replace('%','').replace(',','.')
            if not re.fullmatch(r'-?\\d+(?:\\.\\d+)?',raw):
                raise ValueError('Invalid amount '+label)
            value=float(raw)
            ratio=metric in ('expense_ratio','loss_ratio','combined_ratio')
            rows.append(dict(company='Frende',scope='norway',source_scope='legal_entity',
                source_entity=ENTITY,year=y,quarter=quarter,period_type='quarter',
                metric=metric,value=round(value if ratio else value/1000,3),
                unit='percent' if ratio else 'NOKm',status='reported',
                source_type='official_quarterly_report',source_url=url,
                source_page=1,source_sha256=digest,source_document_period=f'Q{quarter} {year}',
                source_definition=label))
    by={(r['year'],r['metric']):r['value'] for r in rows}
    for y in (year,year-1):
        if abs(by[y,'combined_ratio']-by[y,'loss_ratio']-by[y,'expense_ratio'])>0.4:
            raise ValueError('Combined ratio mismatch')
    return rows

def fetch(url):
 p=urllib.parse.urlparse(url)
 if p.scheme!='https' or p.hostname not in ('frende.wrep.it','www.frende.no','frende.no'):
  raise ValueError('Untrusted Frende report host')
 req=urllib.request.Request(url,headers={'User-Agent':'Forsikringsbarometeret/1.0'})
 with urllib.request.urlopen(req,timeout=45) as response:
  final=urllib.parse.urlparse(response.geturl())
  if final.scheme!='https' or final.hostname not in ('frende.wrep.it','www.frende.no','frende.no'):
   raise ValueError('Untrusted redirect')
  blob=response.read(30_000_001)
 if len(blob)>30_000_000:raise ValueError('Oversized report')
 return blob

def parse(blob,year,quarter,url):
 digest=hashlib.sha256(blob).hexdigest()
 if blob.startswith(b'%PDF-'):
  from frende_skade_pdf_cells import extract_cells
  with pdfplumber.open(io.BytesIO(blob)) as pdf:
   if not pdf.pages:raise ValueError('Empty PDF')
   values=extract_cells(pdf.pages[0],METRICS,year,quarter)
  return observations(values,year,quarter,url,digest)
 return parse_table(blob.decode('utf-8'),year,quarter,url,digest)

def run():
 page=fetch(INDEX).decode('utf-8','replace')
 candidates=discover(page)
 if not candidates:raise ValueError('No subsidiary quarterly reports on official Frende index')
 data=json.loads(DATA.read_text(encoding='utf-8'))
 existing=data['observations']
 new=[]
 latest_year=candidates[0]['year']
 for item in (x for x in candidates if x['year']>=latest_year-1):
  try:
   url=item['url'];blob=fetch(url)
   new.extend(parse(blob,item['year'],item['quarter'],url))
  except Exception as exc:
   print('::warning::FRENDE_SKADE_UNVERIFIED',item['year'],item['quarter'],str(exc)[:180],flush=True)
 keys={(r['company'],r['scope'],r['year'],r['quarter'],r['period_type'],r['metric']) for r in existing}
 added=[r for r in new if (r['company'],r['scope'],r['year'],r['quarter'],r['period_type'],r['metric']) not in keys]
 if added:
  merged={**data,'observations':existing+added}
  if not audit(merged)['ok']:raise ValueError('Frende subsidiary audit failed')
  atomic_write(DATA,merged)
 print('FRENDE_SKADE_VERIFIED_ADDED',len(added),flush=True)
if __name__=='__main__':run()
