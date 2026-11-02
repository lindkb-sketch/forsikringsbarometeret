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
    """Parse publisher's actual first-page Resultat table with signed columns."""
    import html
    from html.parser import HTMLParser
    class Plain(HTMLParser):
        def __init__(self):
            super().__init__();self.parts=[]
        def handle_data(self,text):
            if text.strip():self.parts.append(text.strip())
    reader=Plain();reader.feed(markup)
    text=' '.join(reader.parts) if '<' in markup else markup
    text=html.unescape(text).replace('\u00a0',' ')
    header=re.search(r'Resultatregnskap\s+'+str(quarter)+r'\.\s*kv\.\s*'+str(year)+
        r'\s+'+str(quarter)+r'\.\s*kv\.\s*'+str(year-1),text,re.I)
    if not header:raise ValueError('Missing same-quarter current/prior header')
    # Thousands separated by whitespace, with negative signs sometimes adjacent.
    amount=r'-?\d{1,3}(?:\s+\d{3})+(?:[.,]\d+)?|-?\d+(?:[.,]\d+)?'
    labels=list(METRICS)
    out=[]
    for label,metric in METRICS.items():
        start=re.search(re.escape(label),text,re.I)
        if not start:raise ValueError('Missing Frende Skade row '+label)
        tail=text[start.end():]
        hits=list(re.finditer(amount,tail))
        if len(hits)<2:raise ValueError('Missing current/prior amounts '+label)
        # Stop at next named row to avoid silently borrowing another metric.
        next_labels=[m.start() for other in labels if other!=label
                     for m in [re.search(re.escape(other),tail,re.I)] if m]
        boundary=min(next_labels) if next_labels else len(tail)
        values=[m.group() for m in hits if m.start()<boundary][:2]
        if len(values)!=2:raise ValueError('Ambiguous current/prior amounts '+label)
        for y,raw in ((year,values[0]),(year-1,values[1])):
            value=float(raw.replace(' ','').replace(',','.'))
            ratio=metric in ('expense_ratio','loss_ratio','combined_ratio')
            if ratio and not 0<=value<=150:raise ValueError('Invalid percentage '+label)
            out.append(dict(company='Frende',scope='norway',source_scope='legal_entity',
                source_entity=ENTITY,year=y,quarter=quarter,period_type='quarter',
                metric=metric,value=round(value if ratio else value/1000,3),
                unit='percent' if ratio else 'NOKm',status='reported',
                source_type='official_quarterly_report',source_url=url,
                source_page=1,source_sha256=source_hash,
                source_document_period=f'Q{quarter} {year}',
                source_definition=label+(' (premieinntekter f.e.r., not IFRS 17)' if metric=='insurance_revenue' else '')))
    by={(r['year'],r['metric']):r['value'] for r in out}
    for y in (year,year-1):
        if abs(by[y,'combined_ratio']-by[y,'loss_ratio']-by[y,'expense_ratio'])>0.4:
            raise ValueError('Ratio components do not reconcile')
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
   matching=[line for line in text.splitlines() if re.match(r'^\s*'+re.escape(label)+r'\s+',line,re.I)]
   if len(matching)!=1:raise ValueError('Missing or ambiguous PDF first-page row '+label)
   tail=re.sub(r'^\s*'+re.escape(label)+r'\s+','',matching[0],flags=re.I)
   values=re.findall(r'-?\d{1,3}(?:[ \u00a0]\d{3})+(?:[.,]\d+)?\s*%?|-?\d+(?:[.,]\d+)?\s*%?',tail)
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
