#!/usr/bin/env python3
"""Strict Sampo group + two Nordic segments, quarter and YTD from issuer PDFs."""
import hashlib,io,json,re,sys,urllib.request
from pathlib import Path
import pdfplumber
from audit_financials import DATA,audit
from build_verified_feed import OUT,build
from publish_geographic_workbooks import atomic_write
SOURCES={
 (2026,1):'https://www.sampo.com/globalassets/investors/quarterly-reporting/2026/q1/interim-statement-q1-2026.pdf',
 (2026,2):'https://attachment.news.eu.nasdaq.com/a036fbfb26e58152a2998c5090e90d969',
}
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
 alltext=' '.join(t for _,t in pages[:6])
 if str(year) not in alltext:raise ValueError('Incorrect report year')
 observations=[]
 for segment in ('Sampo Group',)+SEGMENTS:
  candidates=[]
  for page,text in pages:
   # Segment's own table begins at the segment heading, never use a group figure as segment figure.
   pattern=r'(?m)^'+re.escape(segment)+r'\s*$'
   for m in re.finditer(pattern,text):
    block=text[m.end():]
    end=re.search(r'(?m)^(?:Private Nordic|Private UK|Nordic Commercial|Nordic Industrial|Net financial result|Premium development|Underwriting performance|Financial position|Segments)\s*$',block)
    if end:block=block[:end.start()]
    if 'Insurance revenue, net' in block and 'Combined ratio' in block:candidates.append((page,block))
  if not candidates:raise ValueError(f'Missing segment financial table: {segment}')
  page,block=candidates[0]
  for metric,label in LABELS.items():
   lines=[line for line in block.splitlines() if re.match(r'^\s*'+label+r'\s+',line,re.I)]
   if len(lines)!=1:raise ValueError(f'Ambiguous {segment} {metric}: {len(lines)}')
   vals=re.findall(r'(?<!\w)-?\d[\d,]*(?:\.\d+)?(?!\w)',lines[0][len(re.match(r'^\s*'+label,lines[0],re.I).group()):])
   if len(vals)<(4 if quarter>1 else 2):raise ValueError(f'Insufficient columns: {segment} {metric}')
   for period,index in [('quarter',0)]+([('ytd',2)] if quarter>1 else []):
    observations.append(dict(company='Sampo',year=year,quarter=quarter,scope='group' if segment=='Sampo Group' else 'reported_segment',segment=None if segment=='Sampo Group' else segment,source_scope='group' if segment=='Sampo Group' else 'reported_segment',period_type=period,metric=metric,value=number(vals[index]),unit='percent' if metric.endswith('ratio') else 'EURm',status='reported',source_url=url,source_page=page,source_type='official_quarterly_report',source_sha256=sha,source_definition='Sampo financial report; '+segment+' reported table'))
 return observations
def run():
 baseline=json.loads(DATA.read_text())
 if not audit(baseline)['ok']:raise ValueError('Baseline failed audit')
 index={tuple(r.get(k) for k in KEYS):r for r in baseline['observations']}
 added=0
 for (year,q),url in SOURCES.items():
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
