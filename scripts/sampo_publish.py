#!/usr/bin/env python3
"""Strict Sampo group + two Nordic segments, quarter and YTD from issuer PDFs."""
import hashlib,io,json,re,sys,urllib.request,urllib.parse
from html.parser import HTMLParser
from pathlib import Path
import pdfplumber
from audit_financials import DATA,audit
from build_verified_feed import OUT,build
from publish_geographic_workbooks import atomic_write
SOURCES={
 (2025,3):'https://www.sampo.com/globalassets/investors/quarterly-reporting/2025/q3/sampo-groups-interim-statement-q3-2025.pdf',
 (2025,4):'https://www.sampo.com/globalassets/investors/quarterly-reporting/2025/q4/financial-statement-release-2025.pdf',
 (2026,1):'https://www.sampo.com/globalassets/investors/quarterly-reporting/2026/q1/interim-statement-q1-2026.pdf',
 (2026,2):'https://attachment.news.eu.nasdaq.com/a036fbfb26e58152a2998c5090e90d969',
}
class PDFLinks(HTMLParser):
 def __init__(self):super().__init__();self.links=[]
 def handle_starttag(self,tag,attrs):
  if tag=='a':
   href=dict(attrs).get('href','')
   if href:self.links.append(href)
def discover(year,quarter):
 # Use the issuer's live report archive. Ambiguity blocks publication.
 indexes=[f'https://www.sampo.com/investors/quarterly-reporting/q{quarter}-{year}/',
          'https://www.sampo.com/investors/quarterly-reporting/',
          'https://www.sampo.com/investors/financial-information/quarterly-reporting/']
 urls=set()
 for index in indexes:
  try:
   with urllib.request.urlopen(urllib.request.Request(index,headers={'User-Agent':'Mozilla/5.0'}),timeout=20) as response:
    markup=response.read(4_000_000).decode('utf-8')
   parser=PDFLinks();parser.feed(markup)
   for href in parser.links:
    url=urllib.parse.urljoin(index,href)
    label=urllib.parse.unquote(url).lower()
    if not re.search(r'\.pdf(?:$|[?#])',label):continue
    if not re.search(rf'(q{quarter}[^0-9]{{0,20}}{year}|{year}[^0-9]{{0,20}}q{quarter}|interim.statement.q{quarter}.{year}|half.year.financial.report.{year})',label):continue
    if 'presentation' in label:continue
    urls.add(url)
  except Exception:continue
 if len(urls)>1:raise ValueError(f'Ambiguous Sampo official PDF Q{quarter}/{year}: {sorted(urls)}')
 return next(iter(urls)) if urls else None
SEGMENTS=('Private Nordic','Nordic Commercial')
LABELS={'insurance_revenue':r'Insurance revenue, net','insurance_service_result':r'Underwriting result','loss_ratio':r'Risk ratio,?\s*%','expense_ratio':r'Cost ratio,?\s*%','combined_ratio':r'Combined ratio,?\s*%'}
KEYS=('company','year','quarter','scope','period_type','metric','segment')
def number(text):
 return float(text.replace(',','').replace('−','-'))
def parse(blob,url,year,quarter):
 if not blob.startswith(b'%PDF'):raise ValueError('Source is not a PDF')
 sha=hashlib.sha256(blob).hexdigest()
 with pdfplumber.open(io.BytesIO(blob)) as pdf:
  pages=[(i+1,p.extract_text() or '') for i,p in enumerate(pdf.pages)]
 header=' '.join(t for _,t in pages[:5])
 if str(year) not in header:raise ValueError('Incorrect report year')
 quarter_words={1:('January-March','Jan-Mar','Q1'),2:('January-June','Apr-Jun','April-June','Q2'),3:('January-September','Jul-Sep','July-September','Q3'),4:('January-December','Oct-Dec','October-December','Q4','fourth quarter','financial statement release')}
 if not any(word.lower() in header.lower() for word in quarter_words[quarter]):raise ValueError('Report quarter does not match target period')
 observations=[]
 labels={'insurance_revenue':'Insurance revenue, net','insurance_service_result':'Underwriting result','loss_ratio':'Risk ratio','expense_ratio':'Cost ratio','combined_ratio':'Combined ratio'}
 for segment in ('Sampo Group',)+SEGMENTS:
  candidates=[]
  for page,text in pages:
   if segment=='Sampo Group':
    if 'Insurance revenue' not in text or 'Nordic underlying development' not in text:continue
    block=text.split('Nordic underlying development')[0]
   else:
    match=re.search(r'(?m)^'+re.escape(segment)+r'\s*$',text)
    if not match:continue
    block=text[match.end():]
    end=re.search(r'(?m)^(?:Private UK|Nordic Commercial|Nordic Industrial|Premium development|Underwriting performance)\s*$',block)
    if end:block=block[:end.start()]
   if 'Underwriting result' in block and 'Combined ratio' in block:candidates.append((page,block))
  if not candidates:raise ValueError(f'Missing financial table: {segment}')
  page,block=candidates[0]
  for metric,label in labels.items():
   match_label='Insurance revenue' if segment=='Sampo Group' and metric=='insurance_revenue' else label
   lines=[line.strip() for line in block.splitlines() if re.match(r'^\s*'+re.escape(match_label)+r'.{0,40}?(?:EURm\s+|%\s+)[-\d]',line,re.I)]
   if len(lines)!=1:
    if segment!='Sampo Group' and metric in ('loss_ratio','expense_ratio'):
     # Ratios are in the dedicated segment detail, not the overview.
     detail=[(p,t) for p,t in pages if re.search(r'(?m)^'+re.escape(segment)+r'\s*$',t) and 'Key ratios' in t]
     if len(detail)!=1:raise ValueError(f'Missing segment ratio table: {segment}')
     page,block=detail[0]
     lines=[line.strip() for line in block.splitlines() if re.match(r'^\s*'+re.escape(label)+r',?\s*%\s+[-\d]',line,re.I)]
    if len(lines)!=1:
     print('PDF TABLE DIAGNOSTIC',year,quarter,segment,metric,'page',page,repr(block[:2500]),file=sys.stderr)
     raise ValueError(f'Ambiguous {segment} {metric}: {len(lines)}')
   match=re.match(r'^'+re.escape(match_label)+r'.{0,40}?(?:EURm|%)?\s+',lines[0],re.I)
   if not match:raise ValueError(f'Unexpected label {segment} {metric}')
   vals=re.findall(r'-?\d[\d,]*(?:\.\d+)?',lines[0][match.end():])
   if not vals:raise ValueError(f'Missing numeric value: {segment} {metric}')
   # The first numeric column is the current quarter, including Q2 and Q3.
   period='quarter'
   observations.append(dict(company='Sampo',year=year,quarter=quarter,scope='group' if segment=='Sampo Group' else 'reported_segment',segment=None if segment=='Sampo Group' else segment,source_scope='group' if segment=='Sampo Group' else 'reported_segment',period_type=period,metric=metric,value=number(vals[0]),unit='percent' if metric.endswith('ratio') else 'EURm',status='reported',source_url=url,source_page=page,source_type='official_quarterly_report',source_sha256=sha,source_definition='Sampo interim statement; '+segment+' reported financial table'))
   # Q3 2025 financial overview includes the same-definition Q3 2024
   # comparator; never use annual or brokerage-free IFRS rows instead.
   if (year,quarter)==(2025,3) and segment=='Sampo Group' and metric=='insurance_revenue':
    if len(vals)<2:raise ValueError('Sampo Q3 2024 comparative column missing')
    observations.append(dict(company='Sampo',year=2024,quarter=3,scope='group',
      segment=None,source_scope='group',period_type='quarter',metric=metric,
      value=number(vals[1]),unit='EURm',status='reported',source_url=url,
      source_page=page,source_type='official_quarterly_report',source_sha256=sha,
      source_document_period='Q3 2025',
      source_definition='Sampo interim statement; Sampo Group reported financial table (Q3 2024 comparative column)'))
 return observations
def run():
 baseline=json.loads(DATA.read_text())
 if not audit(baseline)['ok']:raise ValueError('Baseline failed audit')
 # Remove only the importer-created Q2 records mislabelled YTD in the initial release.
 baseline['observations']=[r for r in baseline['observations'] if not (r.get('company')=='Sampo' and r.get('year')==2026 and r.get('quarter')==2 and r.get('period_type')=='ytd' and r.get('source_definition','').startswith('Sampo interim statement;'))]
 index={tuple(r.get(k) for k in KEYS):r for r in baseline['observations']}
 added=0
 from datetime import date
 today=date.today()
 targets=dict(SOURCES)
 for year in range(2025,today.year+1):
  for q in range(1,5):
   if (year,q) in targets:continue
   if (year,q)>(today.year,(today.month-1)//3+1):continue
   found=discover(year,q)
   if found:targets[(year,q)]=found
 for (year,q),url in sorted(targets.items()):
  req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'})
  with urllib.request.urlopen(req,timeout=45) as response:blob=response.read(30_000_001)
  if len(blob)>30_000_000:raise ValueError('PDF too large')
  for row in parse(blob,url,year,q):
   key=tuple(row.get(k) for k in KEYS)
   if key in index:
    if abs(index[key]['value']-row['value'])>0.001:raise ValueError(f'Conflicting historical Sampo value: {key}')
   else:index[key]=row;added+=1
 merged={**baseline,'observations':list(index.values())}
 feed=build(merged)
 if added:
  atomic_write(DATA,merged);atomic_write(OUT,feed)
 print(json.dumps({'added':added,'sampo_rows':sum(r['company']=='Sampo' for r in merged['observations'])}))
if __name__=='__main__':
 try:run()
 except Exception as e:print('SAMPO IMPORT BLOCKED:',e,file=sys.stderr);sys.exit(1)
