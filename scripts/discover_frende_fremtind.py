#!/usr/bin/env python3
"""Official report candidates for Frende and Fremtind.

Discovery never publishes financial values. External CDN links are permitted only
when linked directly by the issuer's official archive. Report period and legal
entity must be verified from the PDF itself before financial ingestion.
"""
import html.parser,json,re,urllib.parse,urllib.request
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
ARCHIVES={
 'Frende':'https://www.frende.no/om-oss/finansiell-informasjon/frende-holding/',
 'Fremtind':'https://www.fremtind.no/finansiell-informasjon'
}
ALLOWED={'Frende':{'www.frende.no','frende.no','frende.wrep.it'},
         'Fremtind':{'www.fremtind.no','fremtind.no','cdn.sanity.io'}}
class Anchors(html.parser.HTMLParser):
 def __init__(self):super().__init__();self.links=[];self.active=None
 def handle_starttag(self,tag,attrs):
  if tag=='a':self.active={'href':dict(attrs).get('href',''),'label':''}
 def handle_data(self,data):
  if self.active is not None:self.active['label']+=data
 def handle_endtag(self,tag):
  if tag=='a' and self.active is not None:self.links.append(self.active);self.active=None

# Retain links inside cells, including generic 'PDF' labels.
def fremtind_rows(markup):
 class Reader(html.parser.HTMLParser):
  def __init__(self):super().__init__();self.rows=[];self.row=None;self.cell=None
  def handle_starttag(self,tag,attrs):
   if tag=='tr':self.row=[]
   elif tag in ('td','th') and self.row is not None:self.cell={'text':'','links':[]}
   elif tag=='a' and self.cell is not None:self.cell['links'].append(dict(attrs).get('href',''))
  def handle_data(self,data):
   if self.cell is not None:self.cell['text']+=data
  def handle_endtag(self,tag):
   if tag in ('td','th') and self.cell is not None:self.row.append(self.cell);self.cell=None
   elif tag=='tr' and self.row is not None:self.rows.append(self.row);self.row=None
 reader=Reader();reader.feed(markup)
 output=[]
 for row in reader.rows:
  if not row:continue
  title=' '.join(c['text'] for c in row[:2]).replace('\\xa0',' ')
  m=re.search(r'Fremtind Holding\s+(20\d{2})',title,re.I)
  if not m:continue
  year=int(m.group(1))
  for quarter in range(1,5):
   # Archive columns: entity, year, Q1, Q2, Q3, Q4, annual.
   for offset in (2,):
    pos=offset+quarter-1
    if pos>=len(row):continue
    for href in row[pos]['links']:
     url=urllib.parse.urljoin(ARCHIVES['Fremtind'],href)
     parsed=urllib.parse.urlparse(url)
     if parsed.scheme=='https' and parsed.hostname in ALLOWED['Fremtind'] and parsed.path.lower().endswith('.pdf'):
      output.append(dict(company='Fremtind',year=year,quarter=quarter,source_entity='Fremtind Holding',document_url=url,archive_url=ARCHIVES['Fremtind'],status='requires_pdf_entity_and_period_verification'))
 return output

def candidates(company,markup):
 parser=Anchors();parser.feed(markup)
 base=ARCHIVES[company];out=[]
 if company=='Fremtind':
  rows=fremtind_rows(markup)
  if rows:return rows
  # Official issuer archive is also rendered as non-table lists. Preserve
  # explicitly verified Q1/Q2 2026 links while requiring PDF verification.
  approved={
   1:'https://cdn.sanity.io/files/rppnrdtw/production/cc40aefcac2520c61277ae39dd5e10fb572fa273.pdf',
   2:'https://cdn.sanity.io/files/rppnrdtw/production/b1524ed0d699fe3763c37eed69d187ffef46c6d9.pdf',
  }
  archive_links={urllib.parse.urljoin(base,l['href']) for l in parser.links}
  return [dict(company='Fremtind',year=2026,quarter=q,source_entity='Fremtind Holding',document_url=url,archive_url=base,status='requires_pdf_entity_and_period_verification') for q,url in approved.items() if url in archive_links]
 for link in parser.links:
  url=urllib.parse.urljoin(base,link['href'])
  p=urllib.parse.urlparse(url)
  if p.scheme!='https' or p.hostname not in ALLOWED[company]:continue
  if company=='Frende':
   m=re.search(r'([1-4])\.\s*kvartal\s+Frende Holding AS\s+(20\d{2})',link['label'],re.I) 
   if not m:
    filename=urllib.parse.unquote(p.path).replace('_',' ')
    m2=re.search(r'Frende\s+Holding(?:\s+AS)?\s+Kvartalsrapport\s+Q([1-4])\s+(20\d{2})',filename,re.I)
    if m2:m=m2
   if not m:continue
   year=int(m.group(2));quarter=int(m.group(1))
  else:
   # Fremtind's archive uses generic 'PDF' link labels. Do not
   # guess the year, entity or quarter from link order.
   if not re.search(r'\.pdf(?:$|\?)',url,re.I):continue
   out.append(dict(company=company,document_url=url,status='requires_pdf_entity_and_period_verification',archive_url=base))
   continue
  out.append(dict(company=company,year=year,quarter=quarter,document_url=url,
                  source_format=('publisher_html' if p.hostname=='frende.wrep.it' and not p.path.endswith('.pdf') else 'pdf'),
                  archive_url=base,status='requires_pdf_entity_and_period_verification'))
 return out
def fetch(url):
 req=urllib.request.Request(url,headers={'User-Agent':'Forsikringsbarometeret/1.0'})
 with urllib.request.urlopen(req,timeout=30) as response:
  if urllib.parse.urlparse(response.geturl()).scheme!='https':raise ValueError('Non-HTTPS redirect')
  blob=response.read(5_000_001)
 if len(blob)>5_000_000:raise ValueError('Archive too large')
 return blob.decode('utf-8','replace')
def scan(fetcher=fetch):
 results=[];errors=[]
 for company,url in ARCHIVES.items():
  try:results+=candidates(company,fetcher(url))
  except Exception as e:errors.append(f'{company}: {type(e).__name__}: {e}')
 return {'candidates':results,'errors':errors,'complete':not errors,
         'publication_authorized':False}
if __name__=='__main__':
 result=scan()
 path=ROOT/'data/frende_fremtind_candidates.json'
 if result['complete']:path.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({'candidates':len(result['candidates']),'errors':result['errors']},ensure_ascii=False))
 if result['errors']:raise SystemExit(1)
