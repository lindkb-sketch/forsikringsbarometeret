#!/usr/bin/env python3
"""Strict, source-traceable PDF import of explicitly labelled report highlights.

Downloads registered direct PDF URLs. Only uniquely identified values in
quarter/YTD sections are eligible; ambiguous PDFs are rejected, not guessed.
"""
import hashlib,json,re,urllib.request,io,sys,os,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from audit_financials import audit

LABELS={'insurance_revenue':r'Insurance revenue',
        'insurance_service_result':r'Insurance service result',
        'combined_ratio':r'Combined ratio',
        'expense_ratio':r'Cost ratio'}
VALUE=re.compile(r'(?<!\d)(-?\d{1,3}(?:[ ,]\d{3})*(?:[.,]\d+)?|-?\d{4,}(?:[.,]\d+)?)\s*(%)?')

def read_pdf(blob):
 import pdfplumber
 if not blob.startswith(b'%PDF-') or len(blob)>35_000_000:raise ValueError('Not a bounded PDF')
 with pdfplumber.open(io.BytesIO(blob)) as pdf:
  if len(pdf.pages)>250:raise ValueError('Too many pages')
  return [(i+1,p.extract_text(layout=False) or '') for i,p in enumerate(pdf.pages)]

def parse_highlights(pages,company,year,quarter,url,sha):
 """Conservative parser for Gjensidige group highlights; no other company guessed."""
 if company!='Gjensidige':return []
 matches=[]
 for page_no,text in pages:
  if 'Group highlights' not in text and 'GROUP HIGHLIGHTS' not in text:continue
  # Only bounded heading sections. Do not confuse quarter with year-to-date.
  for period,pattern in [('quarter',rf'(?im)^(?:{["First", "Second", "Third", "Fourth"][quarter-1]}|{quarter}(?:st|nd|rd|th)) quarter\s*$'),('ytd',r'(?im)^Year-to-date\s*$')]:
   heading=re.search(pattern,text)
   if not heading:continue
   tail=text[heading.end():]
   stop=re.search(r'(?im)^(?:Year-to-date|Second quarter|Third quarter|First quarter|Fourth quarter|Profit performance|Group highlights|INTERIM REPORT)\s*$',tail)
   section=tail[:stop.start()] if stop else tail[:2500]
   # Restrict to general-insurance subheading; not group earnings or pensions.
   segment=re.search(r'(?im)^General insurance\s*$',section)
   if not segment:continue
   section=section[segment.end():]
   for metric,label in LABELS.items():
    candidates=[]
    for line in section.splitlines():
     m=re.search(r'^\s*(?:[-•]\s*)?'+label+r'\s*:\s*(?:NOK\s*)?',line,re.I)
     if not m:continue
     v=VALUE.search(line[m.end():])
     if v:
      raw=v.group(1).replace(' ','').replace(',','')
      candidates.append(float(raw))
    if len(candidates)!=1:continue
    matches.append(dict(company=company,year=year,quarter=quarter,scope='group',source_scope='group',period_type=period,metric=metric,value=candidates[0],unit='percent' if metric.endswith('ratio') else 'MNOK',status='reported',source_url=url,source_type='official_quarterly_report',source_page=page_no,source_sha256=sha,source_section='Group highlights / General insurance'))
 # Reject inconsistent duplicate claims across pages.
 keys={};out=[]
 for r in matches:
  key=(r['period_type'],r['metric'])
  if key in keys:
   if keys[key]['value']!=r['value']:raise ValueError('Conflicting PDF highlights '+str(key))
   continue
  keys[key]=r;out.append(r)
 return out

def download(url):
 """Reuse bytes for the same PDF within ONE workflow run, never across runs.

 This is a network optimization, not a source verification shortcut: PDF
 parsing and all downstream financial checks still execute normally.
 """
 if not url.startswith('https://'):raise ValueError('HTTPS required')
 cache_root=os.environ.get('BAROMETER_PDF_RUN_CACHE')
 cache_file=None
 if cache_root:
  cache_file=Path(cache_root)/('pdf-'+hashlib.sha256(url.encode('utf-8')).hexdigest())
  if cache_file.is_file():
   blob=cache_file.read_bytes()
   if blob.startswith(b'%PDF-') and len(blob)<=35_000_000:
    print('PDF_RUN_CACHE_HIT',url,flush=True)
    return blob
 req=urllib.request.Request(url,headers={'User-Agent':'Forsikringsbarometeret/1.0'})
 with urllib.request.urlopen(req,timeout=40) as response:
  if not response.geturl().startswith('https://'):raise ValueError('Insecure redirect')
  blob=response.read(35_000_001)
 if len(blob)>35_000_000:raise ValueError('PDF too large')
 if cache_file and blob.startswith(b'%PDF-'):
  cache_file.parent.mkdir(parents=True,exist_ok=True)
  fd,tmp=tempfile.mkstemp(prefix='.pdf-cache-',dir=cache_file.parent)
  try:
   with os.fdopen(fd,'wb') as out:out.write(blob)
   os.replace(tmp,cache_file)
  finally:
   if os.path.exists(tmp):os.unlink(tmp)
 return blob

def merge(existing,new):
 keys=('company','year','quarter','scope','period_type','metric')
 # Segment observations have the same scope and metric but different entities.
 # Keep each issuer-reported segment separate; never silently collapse them.
 def identity(row):
  return tuple(row[k] for k in keys)+(row.get('segment') if row.get('scope')=='reported_segment' else None,)
 index={identity(r):r for r in existing['observations']}
 added=0
 for r in new:
  key=identity(r)
  if key in index:
   old=index[key]
   if abs(old['value']-r['value'])>0.001:raise ValueError('Conflicting published figure: '+str(key))
  else:index[key]=r;added+=1
 result={**existing,'observations':list(index.values())}
 check=audit(result)
 if not check['ok']:raise ValueError('Audit failed: '+str(check['errors']))
 return result,added

def run(registry=None,fetch=download,extract=read_pdf):
 registry=registry or ROOT/'data/report_sources.json'
 sources=json.loads(Path(registry).read_text())['sources']
 existing=json.loads((ROOT/'data/financial_observations.json').read_text())
 imported=[];statuses=[]
 for s in sources:
  if not s.get('document_url') or not s.get('year') or not s.get('quarter'):continue
  # This parser supports Gjensidige highlights only. Other issuers have
  # dedicated validated importers; never fetch their URLs here.
  if s['company']!='Gjensidige':
   statuses.append({'company':s['company'],'status':'handled_by_dedicated_importer','extracted':0})
   continue
  try:
   blob=fetch(s['document_url']);sha=hashlib.sha256(blob).hexdigest()
   records=parse_highlights(extract(blob),s['company'],s['year'],s['quarter'],s['document_url'],sha)
   imported+=records
   statuses.append({'company':s['company'],'period':f"Q{s['quarter']} {s['year']}",'extracted':len(records),'sha256':sha})
  except Exception as e:
   statuses.append({'company':s['company'],'error':str(e)})
 # If any official registered source fails, do not commit partial new observations.
 if any('error' in x for x in statuses):raise RuntimeError('PDF download/extraction failed: '+str(statuses))
 result,added=merge(existing,imported)
 if added:
  path=ROOT/'data/financial_observations.json'
  fd,tmp=tempfile.mkstemp(dir=path.parent,prefix='.pdf-ingest-',suffix='.json')
  try:
   with os.fdopen(fd,'w') as f:json.dump(result,f,ensure_ascii=False,indent=2);f.write('\n')
   os.replace(tmp,path)
  finally:
   if os.path.exists(tmp):os.unlink(tmp)
 return {'added':added,'sources':statuses,'note':'Unrecognized reports produce zero observations; no inference'}
if __name__=='__main__':
 print(json.dumps(run(),ensure_ascii=False,indent=2))
