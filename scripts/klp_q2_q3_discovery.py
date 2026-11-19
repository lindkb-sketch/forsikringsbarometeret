#!/usr/bin/env python3
"""Discover and inspect official KLP Skadeforsikring Q2/Q3 2026 PDFs.

Evidence only. Never publish guessed quarterly or cumulative financial values.
"""
import hashlib
import json
import re
import urllib.request
from pathlib import Path
from import_extended_pdfs import INDEX, approved, download, pages
from html.parser import HTMLParser
from urllib.parse import urljoin

INDEX_URL=INDEX['KLP Skadeforsikring']
PERIODS=(2,3)

def classify(url):
    from urllib.parse import unquote
    name=unquote(url).lower()
    if 'skadeforsikring' not in name or '2026' not in name:
        return None
    for quarter in PERIODS:
        if re.search(r'(?:q|kvartal[ _-]*)(?:'+str(quarter)+r')\b',name):
            return quarter
    return None

def discover(html):
    """Find issuer, year and visible quarter text across HTML heading tags."""
    class Archive(HTMLParser):
        def __init__(self):
            super().__init__()
            self.company=None
            self.year=None
            self.anchor=None
            self.in_heading=False
            self.heading=[]
            self.found={q:[] for q in PERIODS}
        def handle_starttag(self,tag,attrs):
            tag=tag.lower()
            if tag=='a':self.anchor={'href':dict(attrs).get('href'),'label':[]}
            elif tag in ('h1','h2','h3','h4'):self.in_heading=True;self.heading=[]
        def handle_data(self,data):
            text=' '.join(data.split())
            if not text:return
            if self.anchor is not None:self.anchor['label'].append(text)
            elif self.in_heading:self.heading.append(text)
            else:self.context(text)
        def context(self,text):
            if text in ('KLP Konsern','KLP Banken','KLP Kommunekreditt',
                        'KLP Boligkreditt','KLP Skadeforsikring'):
                self.company=text;self.year=None
            elif re.fullmatch(r'20\\d{2}',text):self.year=int(text)
        def handle_endtag(self,tag):
            tag=tag.lower()
            if tag in ('h1','h2','h3','h4') and self.in_heading:
                self.context(' '.join(self.heading));self.in_heading=False
            if tag!='a' or self.anchor is None:return
            label=' '.join(self.anchor['label']).lower()
            href=self.anchor['href']
            if self.company=='KLP Skadeforsikring' and self.year==2026 and href:
                url=urljoin(INDEX_URL,href)
                if approved(url,'KLP Skadeforsikring'):
                    for q in PERIODS:
                        if re.search(r'kvartalsrapport\\s+(?:for\\s+)?'+str(q)+r'\\.\\s*kvartal',label):
                            if url not in self.found[q]:self.found[q].append(url)
            self.anchor=None
    parser=Archive();parser.feed(html)
    return parser.found

def scan(url,quarter):
    raw=download(url,'KLP Skadeforsikring')
    text_pages=pages(raw)
    period=re.compile(r'(?:'+str(quarter)+r'\.\s*kvartal(?:\s*2026)?|q'+str(quarter)+r'\s*2026)',re.I)
    if not any(period.search(text) for text in text_pages[:5]):
        raise ValueError('Issuer PDF does not identify expected quarter')
    evidence={'quarter':quarter,'url':url,'sha256':hashlib.sha256(raw).hexdigest(),
              'pdf_pages':len(text_pages),'status':'requires_column_and_ratio_reconciliation',
              'reconciliation_verified':False,'publication_approved':False,'candidate_pages':[]}
    for i,text in enumerate(text_pages,1):
        if re.search(r'forsikringsinntekter|forsikringskostnader|gjenforsikringsresultat|totalskadeprosent|nøkkeltall',text,re.I):
            evidence['candidate_pages'].append({'page':i,'text':text[:18000]})
    if not evidence['candidate_pages']:raise ValueError('No financial pages detected')
    return evidence

def run():
    req=urllib.request.Request(INDEX_URL,headers={'User-Agent':'Mozilla/5.0'})
    with urllib.request.urlopen(req,timeout=25) as response:
        if response.geturl().split('/')[2].lower() not in ('www.klp.no','klp.no'):
            raise ValueError('Issuer archive redirected outside approved hosts')
        html=response.read(3_000_000).decode('utf-8','replace')
    found=discover(html)
    report={'index':INDEX_URL,'periods':{},'missing':[],'status':'diagnostic_only'}
    for quarter in PERIODS:
        choices=found[quarter]
        if len(choices)!=1:
            report['periods'][str(quarter)]={'candidate_urls':choices,'status':'ambiguous_or_missing'}
            report['missing'].append(quarter)
            continue
        try:
            report['periods'][str(quarter)]=scan(choices[0],quarter)
        except Exception as exc:
            report['periods'][str(quarter)]={'candidate_urls':choices,'status':'source_or_layout_error',
                                              'error':str(exc)[:300]}
            report['missing'].append(quarter)
    return report

if __name__=='__main__':
    output=Path('klp-audit/q2-q3-discovery.json')
    output.parent.mkdir(parents=True,exist_ok=True)
    try:
        result=run()
    except Exception as exc:
        result={'status':'archive_unavailable','error':str(exc)[:300],'publication_approved':False}
    output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('KLP_Q2_Q3_DISCOVERY',json.dumps({'status':result['status'],
        'quarters':{k:{'status':v['status'],'url':v.get('url'),
                       'pages':len(v.get('candidate_pages',[]))}
                    for k,v in result.get('periods',{}).items()},
        'missing':result.get('missing')},ensure_ascii=False))
    if result['status']=='archive_unavailable':
        raise SystemExit('Issuer archive unavailable: inspect uploaded evidence')
    if result.get('missing'):
        print('KLP_REPORTS_NOT_YET_DISCOVERED',result['missing'])
