#!/usr/bin/env python3
"""Discover exact Tryg A/S group PDF and investor XLSX pairs from official archive."""
import json,re,urllib.request,urllib.parse
from datetime import date
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
            self.links.append((self.a[0],' '.join(' '.join(self.a[1]).split())));self.a=None

def parse(markup,year):
    p=Links();p.feed(markup)
    result={}
    for href,label in p.links:
        url=urllib.parse.urljoin(BASE+str(year),href)
        u=urllib.parse.urlparse(url)
        if u.scheme!='https' or u.hostname not in ('tryg.com','www.tryg.com'):continue
        name=urllib.parse.unquote(u.path.split('/')[-1])
        search_text=label+' '+name
        matches=re.findall(r'(?i)\bQ([1-4])\b|(?i:Q)([1-4])(?=20\d{2})',search_text)
        if matches:
            quarter=int((matches[-1][0] or matches[-1][1]))
        elif re.search(r'(?i)half[- ]year|\bH1\b',search_text):
            quarter=2
        elif re.search(r'(?i)annual[ _-]?report|full[ _-]?year|investor.?tables[_ -]?Q4',search_text):
            quarter=4
        else:
            continue
        if not re.search(r'(?<!\d)'+str(year)+r'(?!\d)',search_text):continue
        kind=None
        if name.lower().endswith('.xlsx') and re.search(r'investor.?tables|investor.?table',search_text,re.I):kind='workbook_url'
        elif name.lower().endswith('.pdf') and re.search(r'interim report|financial report|annual report',search_text,re.I):kind='report_pdf_url'
        if kind:
            item=result.setdefault((year,quarter),{'company':'Tryg','year':year,'quarter':quarter,'source_index_url':BASE+str(year)})
            if kind in item and item[kind]!=url:raise ValueError('Ambiguous Tryg official archive '+str((year,quarter,kind)))
            item[kind]=url
    return [item for _,item in sorted(result.items()) if 'report_pdf_url' in item]

def run(years=None):
    if years is None:
        years=range(2025,date.today().year+1)
    pairs=[]
    for year in years:
        req=urllib.request.Request(BASE+str(year),headers={'User-Agent':'Mozilla/5.0'})
        with urllib.request.urlopen(req,timeout=30) as resp:
            if urllib.parse.urlparse(resp.geturl()).hostname not in ('tryg.com','www.tryg.com'):raise ValueError('Untrusted archive redirect')
            markup=resp.read(2_000_001)
        if len(markup)>2_000_000:raise ValueError('Oversized archive')
        pairs.extend(parse(markup.decode('utf-8','replace'),year))
    if not pairs:raise ValueError('No issuer-linked Tryg PDFs')
    OUT.write_text(json.dumps({'complete':True,'pairs':pairs},ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'Tryg_pairs':[(x['year'],x['quarter']) for x in pairs]}))
    return pairs
if __name__=='__main__':run()
