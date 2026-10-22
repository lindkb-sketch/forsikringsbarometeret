#!/usr/bin/env python3
"""Discover exact Tryg A/S group PDF and investor XLSX pairs from official archive."""
import json,re,urllib.request,urllib.parse
from html.parser import HTMLParser
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data/tryg_candidates.json'
BASE='https://tryg.com/en/downloads-'

class Links(HTMLParser):
    def __init__(self):super().__init__();self.a=None;self.links=[]
    def handle_starttag(self,tag,attrs):
        if tag=='a':self.a=[dict(attrs).get('href',''),[]]
    def handle_data(self,data):
        if self.a:self.a[1].append(data)
    def handle_endtag(self,tag):
        if tag=='a' and self.a:
            self.links.append((self.a[0],' '.join(' '.join(self.a[1]).split()));self.a=None

def parse(markup,year):
    p=Links();p.feed(markup)
    result={}
    for href,label in p.links:
        url=urllib.parse.urljoin(BASE+str(year),href)
        u=urllib.parse.urlparse(url)
        if u.scheme!='https' or u.hostname not in ('tryg.com','www.tryg.com'):continue
        name=urllib.parse.unquote(u.path.split('/')[-1])
        match=re.search(r'(?i)\bQ([1-4])\b',label+' '+name)
        if not match:continue
        quarter=int(match)
        if not re.search(str(year),label+' '+name):continue
        kind=None
        if name.lower().endswith('.xlsx') and re.search('investor.?tables|investor.?table',label+' '+name,re.I):kind='workbook_url'
        elif name.lower().endswith('.pdf') and re.search(r'interim report|financial report',label+' '+name,re.I):kind='report_pdf_url'
        if kind:
            item=result.setdefault((year,quarter),{'company':'Tryg','year':year,'quarter':quarter,'source_index_url':BASE+str(year)})
            if kind in item and item[kind]!=url:raise ValueError('Ambiguous Tryg official archive '+str((year,quarter,kind)))
            item[kind]=url
    return [item for _,item in sorted(result.items()) if 'workbook_url' in item and 'report_pdf_url' in item]

def run(years=None):
    years=years or (2025,2026)
    pairs=[]
    for year in years:
        req=urllib.request.Request(BASE+str(year),headers={'User-Agent':'Mozilla/5.0'})
        with urllib.request.urlopen(req,timeout=30) as resp:
            if urllib.parse.urlparse(resp.geturl()).hostname not in ('tryg.com','www.tryg.com'):raise ValueError('Untrusted archive redirect')
            markup=resp.read(2_000_001)
        if len(markup)>2_000_000:raise ValueError('Oversized archive')
        pairs.extend(parse(markup.decode('utf-8','replace'),year))
    if not pairs:raise ValueError('No issuer-linked Tryg PDF/XLSX pairs')
    OUT.write_text(json.dumps({'complete':True,'pairs':pairs},ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'Tryg_pairs':[(x['year'],x['quarter']) for x in pairs]}))
    return pairs
if __name__=='__main__':run()
