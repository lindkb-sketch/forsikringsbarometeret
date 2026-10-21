#!/usr/bin/env python3
"""Independent media headline ingestion; never used as financial data."""
import datetime as dt,email.utils,hashlib,json,re,urllib.parse,urllib.request,xml.etree.ElementTree as ET
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/'data/official_news.json'
PUBLISHERS={'dn.no':'DN','e24.no':'E24','finansavisen.no':'Finansavisen','vg.no':'VG','nrk.no':'NRK','nettavisen.no':'Nettavisen','aftenposten.no':'Aftenposten','reuters.com':'Reuters'}
KEYWORDS=re.compile(r'forsikr|insurance|gjensidige|fremtind|frende|protector|storebrand|tryg|sampo|naturskade|premie',re.I)
def feed_urls():
 q=' OR '.join('"'+x+'"' for x in ['Gjensidige','Tryg forsikring','Fremtind','Frende','Protector Forsikring','Storebrand','If forsikring','Sampo'])
 return ['https://news.google.com/rss/search?'+urllib.parse.urlencode({'q':'('+q+') when:14d','hl':'no','gl':'NO','ceid':'NO:no'})]
def fetch(url):
 req=urllib.request.Request(url,headers={'User-Agent':'Forsikringsbarometeret/1.0'})
 with urllib.request.urlopen(req,timeout=30) as resp:
  if not resp.geturl().startswith('https://'):raise ValueError('Insecure redirect')
  data=resp.read(2_000_001)
 if len(data)>2_000_000:raise ValueError('RSS too large')
 return data
def parse_rss(payload,now=None):
 now=now or dt.datetime.now(dt.timezone.utc); root=ET.fromstring(payload); rows=[]
 for item in root.findall('.//channel/item'):
  title=(item.findtext('title') or '').strip(); src=item.find('source')
  domain=urllib.parse.urlsplit(src.attrib.get('url','')).hostname if src is not None else None
  domain=(domain or '').lower().removeprefix('www.')
  if domain not in PUBLISHERS or not KEYWORDS.search(title):continue
  url=(item.findtext('link') or '').strip()
  if not url.startswith('https://'):continue
  try:published=email.utils.parsedate_to_datetime(item.findtext('pubDate')).astimezone(dt.timezone.utc)
  except (ValueError,TypeError,AttributeError):continue
  if not dt.timedelta(0)<=now-published<=dt.timedelta(days=21):continue
  title=re.sub(r'\s+-\s+'+re.escape((src.text or '').strip())+r'$','',title,flags=re.I).strip()
  key=hashlib.sha256((domain+'|'+re.sub(r'\W+','',title.casefold())).encode()).hexdigest()[:20]
  rows.append({'id':key,'headline':title[:300],'publisher':PUBLISHERS[domain],'published_at':published.isoformat(),'source_url':url,'approved':True,'provenance':'Google News RSS, attributed publisher headline only; full article not verified'})
 return rows
def merge(existing,new):
 items={x['id']:x for x in existing.get('items',[]) if x.get('id')}
 for x in new:items[x['id']]=x
 return {'items':sorted(items.values(),key=lambda x:x['published_at'],reverse=True)[:100],'source_policy':'Independent publisher-attributed media headlines, not quarterly reports'}
def run(fetcher=fetch,out=OUT):
 old=json.loads(out.read_text()) if out.exists() else {'items':[]}
 incoming=[]
 for url in feed_urls():incoming+=parse_rss(fetcher(url))
 result=merge(old,incoming)
 out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');return result
if __name__=='__main__':
 print('Media headlines:',len(run()['items']))
