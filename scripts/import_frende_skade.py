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
 t=TableReader();t.feed(markup)
 tables=t.rows
 if not tables:raise ValueError('No report table')
 header=next((r for r in tables if r and r[0].startswith('Resultatregnskap')),None)
 if not header:raise ValueError('Missing subsidiary income statement')
 # The report must identify the isolated quarter and the prior-year column.
 current=f'{quarter}.kv.{year}'
 variants=(current,f'{quarter}. kv {year}',f'{quarter}. kv. {year}')
 h=' '.join(header).replace(' ','').lower()
 if not any(v.replace(' ','').lower() in h for v in variants):
  raise ValueError('Wrong reporting quarter')
 # HTML tables retain separate columns; first numeric cell is current quarter.
 rows={r[0].strip():r for r in tables if r and r[0].strip() in METRICS}
 if set(rows)!=set(METRICS):raise ValueError('Missing subsidiary KPI rows '+str(set(METRICS)-set(rows)))
 out=[]
 for label,metric in METRICS.items():
  row=rows[label]
  if len(row)<3:raise ValueError('Missing same-quarter comparison '+label)
  for y,col in ((year,1),(year-1,2)):
   value=number(row[col],metric in ('expense_ratio','loss_ratio','combined_ratio'))
   if metric in ('expense_ratio','loss_ratio','combined_ratio') and not 0<=value<=150:raise ValueError('Invalid ratio')
   out.append(dict(company='Frende',scope='norway',source_scope='legal_entity',
     source_entity=ENTITY,year=y,quarter=quarter,period_type='quarter',metric=metric,
     value=round(value if metric.endswith('ratio') else value/1000,3),
     unit='percent' if metric in ('expense_ratio','loss_ratio','combined_ratio') else 'NOKm',
     status='reported',source_type='official_quarterly_report',source_url=url,
     source_page=1,source_sha256=source_hash,source_document_period=f'Q{quarter} {year}',
     source_definition=label+(' (net earned premiums; not IFRS 17 revenue)' if metric=='insurance_revenue' else '')))
 by={(r['year'],r['metric']):r['value'] for r in out}
 for y in (year,year-1):
  if abs(by[y,'combined_ratio']-by[y,'loss_ratio']-by[y,'expense_ratio'])>0.35:
   raise ValueError('Ratios do not reconcile')
 return out

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
 if blob.startswith(b'%PDF-'):
  with pdfplumber.open(io.BytesIO(blob)) as pdf:
   if not pdf.pages:raise ValueError('Empty PDF')
   text=pdf.pages[0].extract_text() or ''
  # Reconstruct rows from page-one labelled values, preserving signed amounts.
  # Reject ambiguous multi-column extraction instead of guessing.
  import html
  report_rows=[]
  header=f'Resultatregnskap {quarter}.kv.{year} {quarter}.kv.{year-1}'
  report_rows.append([header])
  for label in METRICS:
   matching=[line for line in text.splitlines() if re.match(r'^\\s*'+re.escape(label)+r'\\s+',line,re.I)]
   if len(matching)!=1:raise ValueError('Missing or ambiguous PDF first-page row '+label)
   tail=re.sub(r'^\\s*'+re.escape(label)+r'\\s+','',matching[0],flags=re.I)
   values=re.findall(r'-?\\d{1,3}(?:[ \\u00a0]\\d{3})+(?:[.,]\\d+)?\\s*%?|-?\\d+(?:[.,]\\d+)?\\s*%?',tail)
   if len(values)<2:raise ValueError('Missing PDF comparison columns '+label)
   report_rows.append([label,values[0],values[1]])
  markup='<table>'+''.join('<tr>'+''.join('<td>'+html.escape(str(v))+'</td>' for v in row)+'</tr>' for row in report_rows)+'</table>'
  return parse_table(markup,year,quarter,url,hashlib.sha256(blob).hexdigest())
 return parse_table(blob.decode('utf-8'),year,quarter,url,hashlib.sha256(blob).hexdigest())

def run():
 page=fetch(INDEX).decode('utf-8','replace')
 candidates=discover(page)
 if not candidates:raise ValueError('No subsidiary quarterly reports on official Frende index')
 data=json.loads(DATA.read_text(encoding='utf-8'))
 existing=data['observations']
 new=[]
 for item in candidates:
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
