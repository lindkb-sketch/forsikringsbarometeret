#!/usr/bin/env python3
"""Best-effort public NewsWeb search ingestion. Never publish inferred notices."""
import datetime as dt
import html.parser
import json
import os
import re
import tempfile
import urllib.parse
import urllib.request
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data/newsweb_notices.json'
BASE='https://newsweb.oslobors.no'
# Explicit issuer signs only. Do not infer Frende/Fremtind/If/Tryg issuer identities.
ISSUERS={'Gjensidige':'GJF','Protector':'PROT','Storebrand':'STB'}
COMPANIES=('Fremtind','Gjensidige','Tryg','Sampo','Frende','Protector','Storebrand')
AGE=dt.timedelta(days=92)

class Rows(html.parser.HTMLParser):
    def __init__(self):
        super().__init__();self.rows=[];self.row=None;self.cell=None;self.link=None
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        if tag=='tr':self.row=[]
        elif tag in ('td','th') and self.row is not None:self.cell={'text':'','href':None}
        elif tag=='a' and self.cell is not None:self.cell['href']=attrs.get('href')
    def handle_data(self,data):
        if self.cell is not None:self.cell['text']+=data
    def handle_endtag(self,tag):
        if tag in ('td','th') and self.cell is not None and self.row is not None:
            self.row.append(self.cell);self.cell=None
        elif tag=='tr' and self.row is not None:
            self.rows.append(self.row);self.row=None

def parse(page,issuer,now):
    parser=Rows();parser.feed(page)
    notices=[]
    for row in parser.rows:
        if len(row)<4:continue
        fields=[re.sub(r'\\s+',' ',c['text']).strip() for c in row]
        if issuer not in fields:continue  # exact issuer sign, not title substring
        date=next((x for x in fields if re.fullmatch(r'\\d{2}\\.\\d{2}\\.\\d{4} \\d{2}:\\d{2}',x)),None)
        if not date:continue
        published=dt.datetime.strptime(date,'%d.%m.%Y %H:%M').replace(tzinfo=dt.timezone(dt.timedelta(hours=1)))
        # If the HTML lacks an explicit offset, do not claim a precise UTC instant.
        # Use Oslo's DST-aware time zone.
        from zoneinfo import ZoneInfo
        published=published.replace(tzinfo=ZoneInfo('Europe/Oslo'))
        if not dt.timedelta(0)<=now-published<=AGE:continue
        for cell in row:
            href=cell['href']
            if not href:continue
            url=urllib.parse.urljoin(BASE,href)
            u=urllib.parse.urlsplit(url)
            if u.scheme!='https' or u.hostname!='newsweb.oslobors.no':continue
            title=re.sub(r'\\s+',' ',cell['text']).strip()
            if len(title)<5:continue
            notices.append({'source':'NewsWeb','title':title[:240],
              'url':url,'published_at':published.isoformat()})
    return sorted({n['url']:n for n in notices}.values(),
                  key=lambda n:n['published_at'],reverse=True)

def fetch(issuer):
    url=BASE+'/search?'+urllib.parse.urlencode({'issuer':issuer})
    request=urllib.request.Request(url,headers={'User-Agent':'Forsikringsbarometeret/1.0'})
    with urllib.request.urlopen(request,timeout=20) as response:
        if urllib.parse.urlsplit(response.geturl()).hostname!='newsweb.oslobors.no':
            raise ValueError('Unexpected NewsWeb redirect')
        body=response.read(1_000_001)
    if len(body)>1_000_000:raise ValueError('Response too large')
    return body.decode('utf-8')

def update(fetcher=fetch,now=None):
    now=now or dt.datetime.now(dt.timezone.utc)
    old=json.loads(OUT.read_text(encoding='utf-8'))
    notices={c:[] for c in COMPANIES}
    errors={}
    for company,sign in ISSUERS.items():
        try:
            found=parse(fetcher(sign),sign,now)
            if not found:raise ValueError('No parseable official notice; retaining prior records')
            notices[company]=found[:15]
        except Exception as exc:
            errors[company]=str(exc)[:160]
            notices[company]=[n for n in old.get('notices',{}).get(company,[])
                if n.get('source')=='NewsWeb' and
                isinstance(n.get('url'),str) and n['url'].startswith(BASE+'/') and
                isinstance(n.get('published_at'),str) and
                dt.timedelta(0)<=now-dt.datetime.fromisoformat(n['published_at'])<=AGE]
    result={'source':'NewsWeb','updated_at':now.isoformat(),'notices':notices}
    if old.get('notices')==notices:return old
    fd,temp=tempfile.mkstemp(dir=OUT.parent,prefix='.newsweb-')
    try:
        with os.fdopen(fd,'w',encoding='utf-8') as f:json.dump(result,f,ensure_ascii=False,indent=2);f.write('\\n')
        os.replace(temp,OUT)
    finally:
        if os.path.exists(temp):os.unlink(temp)
    return result

if __name__=='__main__':
    data=update()
    print('NEWSWEB_FEED',data['updated_at'],{k:len(v) for k,v in data['notices'].items()})
