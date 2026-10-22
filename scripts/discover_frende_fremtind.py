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
def candidates(company,markup):
 parser=Anchors();parser.feed(markup)
 base=ARCHIVES[company];out=[]
 for link in parser.links:
  url=urllib.parse.urljoin(base,link['href'])
  p=urllib.parse.urlparse(url)
  if p.scheme!='https' or p.hostname not in ALLOWED[company]:continue
  if company=='Frende':
   m=re.search(r'([1-4])\\.\\s*kvartal\\s+Frende Holding AS\\s+(20\\d{2})',link['label'],re.I)
   if not m:continue
   year=int(m.group(2));quarter=int(m.group(1))
  else:
   # Fremtind's archive uses generic 'PDF' link labels. Do not
   # guess the year, entity or quarter from link order.
   if not re.search(r'\\.pdf(?:$|\\?)',url,re.I):continue
   out.append(dict(company=company,document_url=url,status='requires_pdf_entity_and_period_verification',archive_url=base))
   continue
  out.append(dict(company=company,year=year,quarter=quarter,document_url=url,
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
