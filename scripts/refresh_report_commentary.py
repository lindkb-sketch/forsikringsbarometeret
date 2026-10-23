#!/usr/bin/env python3
"""Incremental, fail-closed issuer PDF narrative collection for historical/future quarters.

Only literal passages from the issuer's own report are surfaced, with source PDF,
page and SHA. Never infer causal claims from numeric metrics. Existing curated
editorial notes are retained. One bounded batch per invocation avoids delaying
the 30-minute production publishing cadence.
"""
import hashlib,json,re,urllib.parse,urllib.request,io,os
from pathlib import Path
from collections import defaultdict
import pdfplumber
ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'data/financial_observations.json'
OUT=ROOT/'data/quarterly_insights.json'
TOPICS={
 'large_claims':r'(?i)\b(?:large claims?|major losses|major claims?|large loss(?:es)?|storskad\w*|storbrann\w*|store skader)\b',
 'weather':r'(?i)\b(?:weather|storm|flood(?:ing)?|extreme weather|natcat|natural catastroph\w*|været|værskad\w*|nedbør|flom|naturskad\w*)\b',
 'growth':r'(?i)\b(?:price increases?|premium growth|rate increases?|organic growth|prisøkning\w*|prisjustering\w*|premievekst|volumvekst)\b',
 'profitability':r'(?i)\b(?:underlying profitability|underwriting performance|claims frequency|loss experience|lønnsomhet|skadefrekvens|skadeutvikling|forsikringsdrift)\b'
}
EXCLUDE=re.compile(r'(?i)(?:www\.|https?://|copyright|quarterly report|interim report|table of contents|page \d|\bQ[1-4]\b|\b20[2-3]\d\b)')
def candidates(text):
 lines=[re.sub(r'\s+',' ',v).strip() for v in text.splitlines()]
 joined=' '.join(lines)
 lines+=re.split(r'(?<=[.!?])\s+(?=[A-ZÆØÅ])',joined)
 for line in lines:
  if not 65<=len(line)<=260 or len(line.split())<10:continue
  if re.search(r'\d',line) or EXCLUDE.search(line):continue
  if len(re.findall(r'[a-zA-ZÆØÅæøå]',line))<len(line)*.65:continue
  # Keep complete declarative statements, rather than table captions or headings.
  if not re.search(r'[.!]$',line):continue
  if line.count('|') or line.count(';')>2:continue
  for theme,pattern in TOPICS.items():
   if re.search(pattern,line):
    yield theme,line

def fetch(url):
 host=urllib.parse.urlparse(url)
 if host.scheme!='https' or not host.hostname:raise ValueError('HTTPS issuer PDF required')
 request=urllib.request.Request(url,headers={'User-Agent':'Forsikringsbarometeret/1.0'})
 with urllib.request.urlopen(request,timeout=18) as response:
  redirected=urllib.parse.urlparse(response.geturl())
  if redirected.scheme!='https':raise ValueError('Insecure issuer redirect')
  raw=response.read(18_000_001)
 if len(raw)>18_000_000 or not raw.startswith(b'%PDF-'):raise ValueError('Not a bounded PDF')
 return raw

def extract(company,year,q,url,raw):
 findings={}
 with pdfplumber.open(io.BytesIO(raw)) as pdf:
  # Narrative normally precedes accounting notes and is not on table-heavy pages.
  for ix,page in enumerate(pdf.pages[:14],1):
   for theme,sentence in candidates(page.extract_text() or ''):
    if theme not in findings:
     findings[theme]={'theme':theme,'text':company+' omtaler i kvartalsrapporten: «'+sentence+'»',
      'companies':[company], 'sources':[{'company':company,'url':url,
       'kind':'official_quarterly_report','page':ix,'sha256':hashlib.sha256(raw).hexdigest()}]}
 return findings

def refresh(max_sources=4):
 feed=json.loads(DATA.read_text())['observations']
 storage=json.loads(OUT.read_text()) if OUT.exists() else {'periods':{}}
 by_period=defaultdict(dict)
 for x in feed:
  if x.get('scope')!='group' or x.get('period_type')!='quarter' or x.get('source_type')!='official_quarterly_report':continue
  url=x.get('source_url','')
  if '.pdf' not in urllib.parse.urlparse(url).path.lower():continue
  key=f"Q{x['quarter']} {x['year']}"
  by_period[key].setdefault(x['company'],url)
 # Latest reports first, then systematically backfill older periods.
 periods=sorted(by_period,key=lambda s:(int(s[-4:]),int(s[1])),reverse=True)
 done={(label,c) for label,rows in storage.get('periods',{}).items()
       for row in rows
       for c in row.get('companies',[])}
 attempted=set(tuple(x) for x in storage.get('checked',[])) if storage.get('extraction_version')==2 else set()
 count=0
 for label in periods:
  year=int(label[-4:]);quarter=int(label[1])
  for company,url in sorted(by_period[label].items()):
   if (label,company) in attempted or (label,company) in done:continue
   if count>=max_sources:break
   count+=1
   try:
    excerpts=extract(company,year,quarter,url,fetch(url))
    for row in excerpts.values():
     row['basis']='issuer_pdf_verbatim'
     storage.setdefault('periods',{}).setdefault(label,[]).append(row)
    status='found' if excerpts else 'no_unambiguous_prose'
   except Exception as exc:
    status=type(exc).__name__
   # Retry temporary download errors next run; don't repeatedly parse irrelevant pages.
   if status in ('found','no_unambiguous_prose'):attempted.add((label,company))
   print('REPORT_COMMENTARY',label,company,status,flush=True)
  if count>=max_sources:break
 storage['checked']=[list(x) for x in sorted(attempted)]
 storage['extraction_version']=2
 storage['policy']='Only exact issuer PDF narrative excerpts with page and SHA; no invented event, loss or weather causes.'
 OUT.write_text(json.dumps(storage,ensure_ascii=False,indent=2)+'\n')
 print('REPORT_COMMENTARY_BATCH',count,'documents checked; total archived periods',len(storage['periods']))
if __name__=='__main__':refresh(max_sources=min(25,max(1,int(os.getenv('QUARTER_COMMENTARY_BATCH','4')))))
