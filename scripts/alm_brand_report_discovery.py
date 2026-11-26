#!/usr/bin/env python3
"""Discover actual period-specific issuer reports; Nasdaq RSS is a delivery fallback.

No guessed PDF URL. Neither a press release nor a presentation supplies primary
financial figures. Every returned report is subject to the original PDF parser.
"""
import datetime as dt
import re
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from urllib.parse import urlsplit,parse_qs,urljoin
from urllib.request import Request,build_opener,HTTPRedirectHandler
from audit_nine_issuer_documents import (
    Anchors, alm_archive_documents, issuer_detail_links, period_label,
    issuer_web_page, ALM_EXCLUDE, EXCLUDE)
from alm_brand_live_pdf import trusted_pdf_link,nasdaq_attachment

COMPANY='Alm. Brand'
ARCHIVES=(
    'https://investorrelations.almbrand.dk/English/financials/default.aspx',
    'https://investorrelations.almbrand.dk/Danish/rapporter/default.aspx',
    'https://investorrelations.almbrand.dk/news-and-events/default.aspx',
    'https://investorrelations.almbrand.dk/English/home/default.aspx',
)
RSS='https://api.news.eu.nasdaq.com/news/rss/nasdaqNordicNews'

def notice_url(url):
    p=urlsplit(url)
    ids=parse_qs(p.query).get('id',[])
    return (p.scheme=='https' and p.hostname=='view.news.eu.nasdaq.com'
            and not p.username and not p.password and p.port in (None,443)
            and p.path=='/view' and len(ids)==1 and bool(re.fullmatch(r'[0-9a-f]{32,33}',ids[0])))

def release_title(title,year,quarter,when):
    if not re.search(r'\bAlm\.?\s+Brand\s+(?:A/S|Group)\b',title,re.I):return False
    if not re.search(r'interim report|quarterly report|delårsrapport|kvartalsrapport|full.year results',title,re.I):return False
    if EXCLUDE.search(title):return False
    if any(int(v)!=year for v in re.findall(r'\b20\d{2}\b',title)):return False
    if not (period_label(title,year,quarter) or
            re.search(rf'\b(?:Q\s*{quarter}|{quarter}\.\s*kvartal)\b',title,re.I)):return False
    import calendar
    end=dt.date(year,quarter*3,calendar.monthrange(year,quarter*3)[1])
    return end<when<=end+dt.timedelta(days=120)

def fetch(url):
    def allowed(u):
        return issuer_web_page(COMPANY,u) or notice_url(u) or u==RSS
    if not allowed(url):raise ValueError('Unapproved report index')
    class Redirect(HTTPRedirectHandler):
        def redirect_request(self,req,fp,code,msg,headers,newurl):
            if not allowed(newurl):raise ValueError('Unapproved report discovery redirect')
            return super().redirect_request(req,fp,code,msg,headers,newurl)
    with build_opener(Redirect()).open(Request(url,headers={'User-Agent':'Mozilla/5.0 Forsikringsbarometeret'}),timeout=25) as response:
        if not allowed(response.geturl()):raise ValueError('Unexpected report discovery origin')
        raw=response.read(5_000_001)
    if len(raw)>5_000_000:raise ValueError('Report discovery response too large')
    return raw.decode('utf-8','replace')

def rss_notices(markup,year,quarter):
    root=ET.fromstring(markup)
    found=[]
    for item in root.iter():
        if item.tag.rsplit('}',1)[-1]!='item':continue
        fields={c.tag.rsplit('}',1)[-1]:(c.text or '').strip() for c in item}
        try:when=parsedate_to_datetime(fields.get('pubDate','')).date()
        except (TypeError,ValueError,AttributeError):continue
        link=fields.get('link','')
        if notice_url(link) and release_title(fields.get('title',''),year,quarter,when):
            found.append((link,fields['title'],when))
    return list(dict.fromkeys(found))[:6]

def notice_reports(markup,origin,year,quarter,title,when):
    if not notice_url(origin) or not release_title(title,year,quarter,when):return []
    # Require actual issuer/quarter identity in the filing page, separately
    # from the RSS entry; never attach a report from a different announcement.
    from html.parser import HTMLParser
    class Text(HTMLParser):
        def __init__(self):super().__init__();self.parts=[]
        def handle_data(self,data):self.parts.append(data)
    parser=Text();parser.feed(markup);body=' '.join(' '.join(parser.parts).split())
    if not re.search(r'\bAlm\.?\s+Brand\b',body,re.I) or not re.search(r'interim report|delårsrapport|quarterly report|kvartalsrapport',body,re.I):return []
    if not (period_label(body,year,quarter) or re.search(rf'\b(?:Q\s*{quarter}|{quarter}\.\s*kvartal)\b',body,re.I)):return []
    links=Anchors();links.feed(markup);out=[]
    for href,label,_ in links.links:
        url=urljoin(origin,href)
        if not nasdaq_attachment(url):continue
        desc=label.replace('-',' ').replace('_',' ')
        if EXCLUDE.search(desc) or ALM_EXCLUDE.search(desc):continue
        if not re.search(r'\b(?:AB\s+GROUP|interim report|quarterly report|delårsrapport)\b',desc,re.I):continue
        if not period_label(desc,year,quarter):continue
        out.append(dict(url=url,document_type='quarterly_report',origin=origin,
                        origin_kind='official_exchange_disclosure',label=label))
    return out

def discover(year,quarter,*,fetcher=fetch):
    found={}
    details=[]
    successes=0
    def ingest(url):
        nonlocal successes
        try:
            markup=fetcher(url);successes+=1
            for doc in alm_archive_documents(markup,url,year,quarter):
                found[(doc['document_type'],doc['url'])]=doc
            details.extend(issuer_detail_links(COMPANY,markup,url,year,quarter))
        except Exception as exc:
            print(f'::warning::Alm. Brand archive unavailable ({type(exc).__name__})',flush=True)
    for url in ARCHIVES:ingest(url)
    for url in list(dict.fromkeys(details))[:6]:ingest(url)
    if not any(k[0]=='quarterly_report' for k in found):
        try:
            for origin,title,when in rss_notices(fetcher(RSS),year,quarter):
                try:
                    for doc in notice_reports(fetcher(origin),origin,year,quarter,title,when):
                        found[(doc['document_type'],doc['url'])]=doc
                except Exception as exc:
                    print(f'::warning::Alm. Brand exchange notice unavailable ({type(exc).__name__})',flush=True)
        except Exception as exc:
            print(f'::warning::Alm. Brand Nasdaq RSS unavailable ({type(exc).__name__})',flush=True)
            if not successes:raise ValueError('No official Alm. Brand discovery channel available') from exc
    return list(found.values())
