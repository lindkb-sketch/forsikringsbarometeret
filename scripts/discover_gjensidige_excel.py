#!/usr/bin/env python3
"""Discover Gjensidige's official quarter Excel workbooks from its IR archive.

No guessed URLs: each candidate must be linked from an issuer-hosted
quarter/year table and contain an actual XLSX archive.
"""
import re
import urllib.parse
import urllib.request
from datetime import date
from html.parser import HTMLParser
from pathlib import Path
from publish_geographic_workbooks import download

INDEX='https://www.gjensidige.com/investor-relations/reports-and-presentations'
class Tables(HTMLParser):
    def __init__(self):
        super().__init__();self.tables=[];self.table=None;self.row=None;self.cell=None;self.link=None
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=='table':self.table=[]
        if tag=='tr' and self.table is not None:self.row=[]
        if tag in ('td','th') and self.row is not None:self.cell={'text':'','links':[]}
        if tag=='a' and self.cell is not None:self.link=a.get('href')
    def handle_data(self,data):
        if self.cell is not None:self.cell['text']+=data
    def handle_endtag(self,tag):
        if tag=='a': 
            if self.link and self.cell is not None:self.cell['links'].append(self.link)
            self.link=None
        if tag in ('td','th') and self.cell is not None:
            self.row.append(self.cell);self.cell=None
        if tag=='tr' and self.row is not None:
            self.table.append(self.row);self.row=None
        if tag=='table' and self.table is not None:
            self.tables.append(self.table);self.table=None

def discover(year,quarter,fetch=None):
    if fetch is None:
        def fetch(url):
            req=urllib.request.Request(url,headers={'User-Agent':'Forsikringsbarometeret/1.0'})
            with urllib.request.urlopen(req,timeout=30) as resp:
                if urllib.parse.urlsplit(resp.geturl()).hostname not in ('www.gjensidige.com','gjensidige.com'):
                    raise ValueError('Untrusted IR redirect')
                return resp.read(4000000).decode('utf-8','replace')
    html=fetch(INDEX)
    parser=Tables();parser.feed(html)
    candidates=[]
    for table in parser.tables:
        if not table:continue
        headings=[' '.join(c['text'].split()).lower() for c in table[0]]
        columns=[i for i,h in enumerate(headings) if re.fullmatch(r'q\\s*'+str(quarter),h)]
        if len(columns)!=1:continue
        col=columns[0]
        for row in table[1:]:
            if len(row)<=col:continue
            label=' '.join(row[0]['text'].split()).lower()
            if not re.search(r'key figures|nøkkeltall|apm',label):continue
            for href in row[col]['links']:
                url=urllib.parse.urljoin(INDEX,href)
                host=urllib.parse.urlsplit(url).hostname or ''
                if host not in ('www.gjensidige.com','gjensidige.com','mb.cision.com'):continue
                if not url.lower().split('?')[0].endswith('.xlsx'):continue
                candidates.append(url)
    return sorted(set(candidates))

if __name__=='__main__':
    import sys
    year=int(sys.argv[1]) if len(sys.argv)>1 else date.today().year
    quarter=int(sys.argv[2]) if len(sys.argv)>2 else (date.today().month-1)//3+1
    urls=discover(year,quarter)
    print('Official Gjensidige workbook candidates:',urls)
    if not urls:raise SystemExit('No issuer-linked Excel workbook discovered; cannot publish Norway data')
