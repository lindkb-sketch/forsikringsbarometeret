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
 if str(year) not in ' '.join(t for _,t in pages[:5]):raise ValueError('Incorrect report year')
 observations=[]
 labels={'insurance_revenue':'Insurance revenue, net','insurance_service_result':'Underwriting result','loss_ratio':'Risk ratio','expense_ratio':'Cost ratio','combined_ratio':'Combined ratio'}
 for segment in ('Sampo Group',)+SEGMENTS:
  candidates=[]
  for page,text in pages:
   if segment=='Sampo Group':
    if 'Insurance revenue' not in text or 'Nordic underlying development' not in text:continue
    block=text.split('Nordic underlying development')[0]
   else:
    match=re.search(r'(?m)^'+re.escape(segment)+r'\\s*$',text)
    if not match:continue
    block=text[match.end():]
    end=re.search(r'(?m)^(?:Private UK|Nordic Commercial|Nordic Industrial|Premium development|Underwriting performance)\\s*$',block)
    if end:block=block[:end.start()]
   if 'Underwriting result' in block and 'Combined ratio' in block:candidates.append((page,block))
  if not candidates:raise ValueError(f'Missing financial table: {segment}')
  page,block=candidates[0]
  for metric,label in labels.items():
   match_label='Insurance revenue' if segment=='Sampo Group' and metric=='insurance_revenue' else label
   lines=[line.strip() for line in block.splitlines() if re.match(r'^\\s*'+re.escape(match_label)+r'.{0,40}?(?:EURm\\s+|%\\s+)[-\\d]',line,re.I)]
   if len(lines)!=1:
    if segment!='Sampo Group' and metric in ('loss_ratio','expense_ratio'):
     # Ratios are in the dedicated segment detail, not the overview.
     detail=[(p,t) for p,t in pages if re.search(r'(?m)^'+re.escape(segment)+r'\\s*$',t) and 'Key ratios' in t]
     if len(detail)!=1:raise ValueError(f'Missing segment ratio table: {segment}')
     page,block=detail[0]
     lines=[line.strip() for line in block.splitlines() if re.match(r'^\\s*'+re.escape(label)+r',?\\s*%\\s+[-\\d]',line,re.I)]
    if len(lines)!=1:
     print('PDF TABLE DIAGNOSTIC',year,quarter,segment,metric,'page',page,repr(block[:2500]),file=sys.stderr)
     raise ValueError(f'Ambiguous {segment} {metric}: {len(lines)}')
   match=re.match(r'^'+re.escape(match_label)+r'.{0,40}?(?:EURm|%)?\\s+',lines[0],re.I)
   if not match:raise ValueError(f'Unexpected label {segment} {metric}')
   vals=re.findall(r'-?\\d[\\d,]*(?:\\.\\d+)?',lines[0][match.end():])
   if not vals:raise ValueError(f'Missing numeric value: {segment} {metric}')
   # For Q2+, use the first YTD column, derive quarter only from verified prior YTD.
   period='quarter' if quarter==1 else 'ytd'
   observations.append(dict(company='Sampo',year=year,quarter=quarter,scope='group' if segment=='Sampo Group' else 'reported_segment',segment=None if segment=='Sampo Group' else segment,source_scope='group' if segment=='Sampo Group' else 'reported_segment',period_type=period,metric=metric,value=number(vals[0]),unit='percent' if metric.endswith('ratio') else 'EURm',status='reported',source_url=url,source_page=page,source_type='official_quarterly_report',source_sha256=sha,source_definition='Sampo interim statement; '+segment+' reported financial table'))
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
