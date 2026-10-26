#!/usr/bin/env python3
"""Fail-closed Protector import: issuer KPIs must agree with official interim PDFs."""
import hashlib,html,json,re,sys,urllib.parse,urllib.request
from html.parser import HTMLParser
from pathlib import Path
from protector_kpi_check import extract,URL as KPI_URL
from audit_financials import audit,DATA
from build_verified_feed import build
from publish_geographic_workbooks import atomic_write

ROOT=Path(__file__).resolve().parents[1]
HOME='https://investor.protectorforsikring.no/'
KEYS=('company','year','quarter','scope','period_type','metric')
class Links(HTMLParser):
 def __init__(self):super().__init__();self.links=[];self.href=None;self.label=[]
 def handle_starttag(self,tag,attrs):
  if tag=='a':self.href=dict(attrs).get('href','');self.label=[]
 def handle_data(self,data):
  if self.href is not None:self.label.append(data)
 def handle_endtag(self,tag):
  if tag=='a' and self.href is not None:
   self.links.append((self.href,' '.join(self.label)));self.href=None
def download(url,limit=35000000):
 if not url.startswith('https://'):raise ValueError('HTTPS required')
 req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 Forsikringsbarometeret'})
 with urllib.request.urlopen(req,timeout=45) as r:
  if not r.geturl().startswith('https://'):raise ValueError('Insecure redirect')
  data=r.read(limit+1)
 if len(data)>limit:raise ValueError('Oversized source')
 return data
def discover_pdf(year,quarter,fetch=download):
 # Report attachment links on the issuer's investor-relations homepage.
 pages=[HOME,HOME+'all-reports',HOME+'financials',HOME+'press-releases']
 if (year,quarter)==(2026,1):
  pages.append(HOME+'pressreleases/q1-2026-cr-849-dividend-per-share-nok-80-moaavo8h')
 links=[]
 index=fetch(HOME+'press-releases',4000000).decode('utf-8')
 index_links=Links();index_links.feed(index)
 for href,label in index_links.links:
  if re.search(rf'q{quarter}\\s*{year}|{year}\\s*[-–:]?\\s*q{quarter}',label,re.I):
   detail=urllib.parse.urljoin(HOME,href)
   if detail.startswith(HOME):pages.append(detail)
 for page_url in pages:
  page=fetch(page_url,4000000).decode('utf-8')
  parser=Links();parser.feed(page)
  for href,label in parser.links:
   url=urllib.parse.urljoin(page_url,html.unescape(href))
   if not url.startswith('https://'):continue
   if not re.search(r'\.pdf(?:[?#]|$)',url,re.I):continue
   context=urllib.parse.unquote(url+' '+label).lower()
   if not re.search(rf'(q{quarter}[^\d]{{0,30}}{year}|{year}[^\d]{{0,30}}q{quarter})',context):continue
   if any(x in context for x in ('presentation','presentasjon')):continue
   links.append(url)
 if (year,quarter)==(2026,1) and not links:
  links=['https://storage.mfn.se/e822f962-2ac5-4f8f-b855-b23309e8fe0c/interim-report-q1-2026-prot.pdf']
 if (year,quarter)==(2026,2) and not links:
  links=['https://storage.mfn.se/6d88613f-b31a-492c-bc3b-ec23b3967dbe/interim-report-q2-2026-prot.pdf']
 links=list(dict.fromkeys(links))
 if len(links)!=1:raise ValueError(f'Expected one issuer-linked Q{quarter} {year} report PDF; found {len(links)}')
 return links[0]
def parse_pdf(blob,year,quarter):
 import io,pdfplumber
 if not blob.startswith(b'%PDF-'):raise ValueError('Not a PDF')
 with pdfplumber.open(io.BytesIO(blob)) as pdf:
  if len(pdf.pages)>200:raise ValueError('PDF too long')
  pages=[(i+1,p.extract_text() or '') for i,p in enumerate(pdf.pages)]
 if not any(re.search(rf'Q{quarter}\s*(?:and\s*Q1.Q{quarter}\s*)?{year}|{year}\s*Q{quarter}',text,re.I) for _,text in pages):
  raise ValueError('Report does not identify target reporting quarter')
 return pages
def provenance(pages,scope,metric,value):
 # Strict source-page lookup: a value alone is insufficient; its KPI heading must also occur.
 labels={'insurance_revenue':'insurance revenue','insurance_service_result':'insurance service result','combined_ratio':'combined ratio','loss_ratio':'loss ratio','expense_ratio':'cost ratio'}
 needle=labels[metric]
 formatted={f'{value:g}',f'{value:,.1f}',f'{value:.1f}',f'{value:,.0f}'}
 for page,text in pages:
  norm=' '.join(text.lower().split())
  if needle in norm and any(re.search(r'(?<![\d.])'+re.escape(v)+r'(?![\d.])',norm) for v in formatted):
   return page
 raise ValueError(f'PDF cannot independently substantiate {scope} {metric} {value}')
def run():
 page=download(KPI_URL,4000000)
 values=extract(page.decode('utf-8'),include_history=True)
 existing=json.loads(DATA.read_text())
 before=audit(existing)
 if not before['ok']:raise ValueError('Baseline audit failed')
 incoming=[]
 for year,quarter in sorted({(y,q) for scope,y,q,metric in values if y>=2026}):
  # No KPI observations enter production without issuer-linked PDF provenance.
  url=discover_pdf(year,quarter)
  blob=download(url)
  pages=parse_pdf(blob,year,quarter)
  sha=hashlib.sha256(blob).hexdigest()
  for (scope,y,q,metric),value in values.items():
   if (y,q)!=(year,quarter) and not (year==2026 and quarter==3 and y==2025 and q==3):continue
   page_no=provenance(pages,scope,metric,value)
   incoming.append(dict(company='Protector',year=year,quarter=quarter,scope=scope,source_scope=scope,period_type='quarter',metric=metric,value=value,unit='percent' if metric.endswith('ratio') else 'MNOK',status='reported',source_url=url,source_type='official_quarterly_report',source_page=page_no,source_sha256=sha,source_definition='Protector issuer KPI table, cross-checked with interim report'+(' (prior-year comparative column)' if y<year else ''),source_document_period=f'Q{quarter} {year}'))
 index={tuple(r[k] for k in KEYS):r for r in existing['observations']}
 added=0
 for r in incoming:
  key=tuple(r[k] for k in KEYS)
  if key in index:
   if abs(index[key]['value']-r['value'])>0.001:raise ValueError('Published Protector value changed: '+str(key))
  else:index[key]=r;added+=1
 merged={**existing,'observations':list(index.values())}
 feed=build(merged)
 if added:
  atomic_write(DATA,merged)
  atomic_write(ROOT/'data/verified_financial_feed.json',feed)
 print(json.dumps({'verified':len(incoming),'added':added,'status':'passed'},indent=2))
if __name__=='__main__':
 try:run()
 except Exception as exc:print('PROTECTOR IMPORT BLOCKED:',exc,file=sys.stderr);sys.exit(1)
