#!/usr/bin/env python3
"""Independent media headline ingestion; never used as financial data."""
import datetime as dt,email.utils,hashlib,json,re,unicodedata,urllib.parse,urllib.request,xml.etree.ElementTree as ET
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/'data/official_news.json'
PUBLISHERS={'dn.no':'DN','e24.no':'E24','finansavisen.no':'Finansavisen','vg.no':'VG','nrk.no':'NRK','nettavisen.no':'Nettavisen','aftenposten.no':'Aftenposten','reuters.com':'Reuters'}
KEYWORDS=re.compile(r'forsikr|insurance|gjensidige|fremtind|frende|protector|storebrand|tryg|sampo|if forsikring|naturskade|premie',re.I)
# Headlines are signals, not verified article content. Reject equity-market
# transactions, untitled company pages and earnings-only headlines.
NOISE=re.compile(r'(?i)aksj|børs|ticker|kursmål|kjøpsanbefal|primærinnsider|pd?mr\\b|meldepliktig|styremedlem|innsidehandel|notice of transaction|transaction by|rapportkalender|kvartalsresultat|kvartalsrapport|resultatfremleggelse|utbytte|stock|share price|analytiker')
EVENTS=re.compile(r'(?i)oppkjøp|oppkjøper|kjøper opp|fusjon|sammenslå|overtar|oppkjøpsbud|acquisition|merger|takeover|m&a|partnerskap|samarbeidsavtale|distribusjonsavtale|bankavtale|partneravtale|avtale med|strategisk samarbeid|strategisk sats|lanserer|markedsandel|konkurrans|kundeflukt|kundetap|kundevekst|prisøk|prishopp|prisvekst|øker forsikringspris|forsikringspremi|premieøk|naturskad|flom|storbrann|brannskad|ekstremvær|rekordskad|svindel|cyberangrep|dataangrep|erstatningskrav|store skader|store skade|millioner i skade|millionar i skade|insurance rates|market share|distribution deal|major claim|catastroph')
def relevant(title):
 return bool(KEYWORDS.search(title) and EVENTS.search(title) and not NOISE.search(title))
def feed_urls():
 queries=[
  '("Gjensidige" OR "Tryg forsikring" OR "Fremtind" OR "Frende" OR "Protector Forsikring" OR "Storebrand" OR "If forsikring" OR "Sampo") (oppkjøp OR fusjon OR samarbeid OR konkurranse OR markedsandel OR prisøkning OR forsikring) when:7d',
  '("forsikring" OR "forsikringsbransjen" OR "insurance") (oppkjøp OR partnerskap OR distribusjon OR naturskade OR storbrann OR premieøkning OR konkurranse) when:7d',
 ]
 return ['https://news.google.com/rss/search?'+urllib.parse.urlencode({'q':q,'hl':'no','gl':'NO','ceid':'NO:no'}) for q in queries]
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
  if domain not in PUBLISHERS:continue
  url=(item.findtext('link') or '').strip()
  if not url.startswith('https://'):continue
  try:published=email.utils.parsedate_to_datetime(item.findtext('pubDate')).astimezone(dt.timezone.utc)
  except (ValueError,TypeError,AttributeError):continue
  if not dt.timedelta(0)<=now-published<=dt.timedelta(days=21):continue
  title=re.sub(r'\s+-\s+'+re.escape((src.text or '').strip())+r'$','',title,flags=re.I).strip()
  if not relevant(title):continue
  key=hashlib.sha256((domain+'|'+re.sub(r'\W+','',title.casefold())).encode()).hexdigest()[:20]
  rows.append({'id':key,'headline':title[:300],'publisher':PUBLISHERS[domain],'published_at':published.isoformat(),'source_url':url,'approved':True,'provenance':'Google News RSS, attributed publisher headline only; full article not verified'})
 return rows
STOPWORDS={'med','for','til','som','har','fra','etter','det','den','og','nye','sine','etter','ved','fra','en','ett','sitt','sier','der','sin','norge','forsikring'}
def tokens(title):
 text=unicodedata.normalize('NFKD',title.casefold())
 text=''.join(c for c in text if not unicodedata.combining(c))
 text=text.replace('storbrannen','brann').replace('brannen','brann').replace('millionar','millioner').replace('kosta','kostet').replace('aukar','øker').replace('auka','økte').replace('prisane','prisene').replace('oppkjøpet','oppkjøp').replace('kjøper opp','oppkjøp')
 return set(t for t in re.split(r'[^a-z0-9æøå]+',text) if len(t)>2 and t not in STOPWORDS)
def issuers(title):
 text=title.casefold()
 names=('gjensidige','fremtind','frende','protector','storebrand','tryg','sampo')
 return {name for name in names if re.search(r'(?<![a-z])'+name+r'(?![a-z])',text)}
def same_story(a,b):
 left,right=issuers(a['headline']),issuers(b['headline'])
 if left and right and not left.intersection(right):return False
 if a.get('source_url')==b.get('source_url'):return True
 x,y=tokens(a['headline']),tokens(b['headline'])
 if not x or not y:return False
 overlap=len(x&y)
 if overlap>=3 and overlap/min(len(x),len(y))>=0.7:return True
 # Different editorial wording about the same insurer, insured event and
 # monetary impact must not occupy two cards (including Bokmål/Nynorsk).
 important=lambda t:set(re.findall(r'[0-9]+(?:[.,][0-9]+)?',t))
 numbers_a,numbers_b=important(a['headline']),important(b['headline'])
 event_a=bool(re.search(r'brann|skad|flom|storm',a['headline'],re.I))
 event_b=bool(re.search(r'brann|skad|flom|storm',b['headline'],re.I))
 if left and left==right and event_a and event_b and numbers_a and numbers_a==numbers_b:
  return True
 return False
def merge(existing,new):
 items={x['id']:x for x in existing.get('items',[]) if x.get('id')}
 for x in new:items[x['id']]=x
 items={k:v for k,v in items.items() if relevant(v.get('headline',''))}
 approved=sorted(items.values(),key=lambda x:x['published_at'],reverse=True)
 distinct=[]
 for row in approved:
  if not any(same_story(row,prior) for prior in distinct):distinct.append(row)
  if len(distinct)>=100:break
 return {'items':distinct,'source_policy':'Independent publisher-attributed media headlines, deduplicated across publishers; not quarterly reports'}
def run(fetcher=fetch,out=OUT):
 old=json.loads(out.read_text()) if out.exists() else {'items':[]}
 incoming=[]
 for url in feed_urls():incoming+=parse_rss(fetcher(url))
 result=merge(old,incoming)
 out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');return result
if __name__=='__main__':
 print('Media headlines:',len(run()['items']))
