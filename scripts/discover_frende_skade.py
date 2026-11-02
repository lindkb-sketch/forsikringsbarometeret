#!/usr/bin/env python3
"""Discover official Frende Skade quarterly PDF links, fail closed on unverified values."""
import re,urllib.request,urllib.parse
from html.parser import HTMLParser
INDEX='https://www.frende.no/om-oss/finansiell-informasjon/frende-skadeforsikring/'
class Links(HTMLParser):
 def __init__(self):super().__init__();self.href=None;self.label=[];self.links=[]
 def handle_starttag(self,tag,attrs):
  if tag=='a':self.href=dict(attrs).get('href');self.label=[]
 def handle_data(self,data):
  if self.href is not None:self.label.append(data)
 def handle_endtag(self,tag):
  if tag=='a' and self.href is not None:
   self.links.append((' '.join(' '.join(self.label).split()),self.href))
   self.href=None
def discover(markup):
 parser=Links();parser.feed(markup)
 result=[]
 for label,href in parser.links:
  match=re.search(r'([1-4])\.\s*kvartal\s+Frende Skadeforsikring AS\s+(20\d{2})',label,re.I)
  if not match:continue
  url=urllib.parse.urljoin(INDEX,href)
  if not url.startswith('https://'):continue
  result.append(dict(year=int(match.group(2)),quarter=int(match.group(1)),url=url))
 return sorted(result,key=lambda x:(x['year'],x['quarter']),reverse=True)
def run():
 req=urllib.request.Request(INDEX,headers={'User-Agent':'Forsikringsbarometeret/1.0'})
 with urllib.request.urlopen(req,timeout=35) as response:
  html=response.read(2_000_001).decode('utf-8','replace')
 links=discover(html)
 if not links:raise ValueError('No official Frende Skade quarterly reports discovered')
 print('FRENDE_SKADE_REPORTS',links[:6])
 # Discovery alone is not proof of numbers. Keep the subsidiary feed empty until
 # the independent legal-entity PDF table parser verifies values and dates.
if __name__=='__main__':run()
