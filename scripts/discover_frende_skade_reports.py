#!/usr/bin/env python3
"""Discover Frende Skadeforsikring quarterly PDF report references without Excel."""
import html
import json
import re
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'data/frende_skade_reports.json'
ARCHIVE = 'https://www.frende.no/om-oss/finansiell-informasjon/frende-skadeforsikring/'
SEED_2026 = {
    1: 'https://newsweb.oslobors.no/message/671905',
    2: ARCHIVE,
    3: 'https://newsweb.oslobors.no/message/684953',
}
class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.active = None
        self.links = []
    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            self.active = [dict(attrs).get('href', ''), '']
    def handle_data(self, data):
        if self.active is not None:
            self.active[1] += data
    def handle_endtag(self, tag):
        if tag == 'a' and self.active is not None:
            self.links.append(self.active)
            self.active = None

def discover(html):
    parser = Links()
    parser.feed(html)
    reports = {}
    for href, label in parser.links:
        m = re.search(r'([1-4])\.\s*kvartal\s+Frende\s+Skadeforsikring\s+AS\s+(20\d{2})', label, re.I)
        if not m:
            continue
        quarter, year = int(m.group(1)), int(m.group(2))
        url = urllib.parse.urljoin(ARCHIVE, href)
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme != 'https' or parsed.hostname not in ('frende.no','www.frende.no','frende.wrep.it'):
            continue
        # Only link to issuer-controlled original reports. PDF downloads and
        # issuer PDF viewers are allowed; no spreadsheet source candidates.
        if re.search(r'\.(?:xlsx?|xlsm)(?:$|\?)', parsed.path, re.I):
            continue
        key = (year, quarter)
        if key in reports and reports[key] != url:
            raise ValueError('Ambiguous Frende Skade report for %s' % (key,))
        reports[key] = url
    return reports

EXCHANGE='https://live.euronext.com/en/listview/company-press-release/600963'
PDF_PREFIX='/sites/default/files/company_press_releases/attachments_oslo/'

def discover_exchange_pdfs(fetch=None):
    """Locate official issuer press release PDF attachments for future quarters."""
    if fetch is None:
        def fetch(url):
            request=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'})
            with urllib.request.urlopen(request,timeout=35) as response:
                if urllib.parse.urlparse(response.geturl()).hostname!='live.euronext.com':
                    raise ValueError('Untrusted Euronext redirect')
                raw=response.read(4_000_001)
            if len(raw)>4_000_000:raise ValueError('Oversized Euronext response')
            return raw.decode('utf-8','replace')
    listing=fetch(EXCHANGE)
    entries=re.findall(r'data-node-nid="(\d+)"[^>]*>\s*([^<]+)',listing,re.I)
    found={}
    for node,title in entries:
        m=re.search(r'Frende\s+(?:Forsikring|Frosikring)\s+([1-4])\.\s*kvartal\s+(20\d{2})',title,re.I)
        if not m:continue
        quarter,year=int(m.group(1)),int(m.group(2))
        if year<2026:continue
        page=fetch('https://live.euronext.com/en/node/'+node)
        urls=[]
        for relative in re.findall(r'href="([^"]+\.pdf(?:\?[^"]*)?)"',page,re.I):
            relative=html.unescape(relative)
            url=urllib.parse.urljoin(EXCHANGE,relative)
            parsed=urllib.parse.urlparse(url)
            if parsed.scheme!='https' or parsed.hostname!='live.euronext.com':
                continue
            if not parsed.path.startswith(PDF_PREFIX):continue
            filename=urllib.parse.unquote(parsed.path.rsplit('/',1)[-1]).lower()
            if 'frende' in filename:urls.append(url)
        urls=list(dict.fromkeys(urls))
        preferred=[u for u in urls if 'skadeforsikring' in urllib.parse.unquote(urllib.parse.urlparse(u).path).lower()]
        chosen=preferred if preferred else urls
        if len(chosen)!=1:continue
        key=(year,quarter)
        if key in found and found[key]!=chosen[0]:
            # Duplicate issuer notices are ambiguous; require manual review.
            found.pop(key)
            continue
        found[key]=chosen[0]
    return found

def build(html,previous=None,pdf_links=None):
    candidates=discover(html)
    for quarter,url in SEED_2026.items():
        candidates.setdefault((2026,quarter),url)
    prior={(item['year'],item['quarter']):item
           for item in (previous or {}).get('reports',[])}
    for key,item in prior.items():
        candidates.setdefault(key,item['source_url'])
    output=[]
    for (y,q),url in sorted(candidates.items(),reverse=True):
        item={'year':y,'quarter':q,'source_url':url,
              'verification':'report_link_only_not_financial_values'}
        pdf=(pdf_links or {}).get((y,q)) or (url if url.lower().split('?')[0].endswith('.pdf') else None) or prior.get((y,q),{}).get('pdf_url')
        if pdf:item['pdf_url']=pdf
        output.append(item)
    return {'entity':'Frende Skadeforsikring AS',
            'source_policy':'original official PDF reports only',
            'reports':output}

def main():
    req = urllib.request.Request(ARCHIVE, headers={'User-Agent':'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=30) as response:
        if urllib.parse.urlparse(response.geturl()).hostname not in ('frende.no','www.frende.no'):
            raise ValueError('Untrusted archive redirect')
        markup = response.read(3_000_001)
    if len(markup)>3_000_000:
        raise ValueError('Archive too large')
    old=json.loads(OUT.read_text()) if OUT.exists() else None
    try:
        exchange=discover_exchange_pdfs()
    except (OSError,ValueError) as exc:
        print('WARNING: official Euronext PDF discovery unavailable:',str(exc)[:200])
        exchange={}
    result=build(markup.decode('utf-8','replace'),old,exchange)
    OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('FRENDE_SKADE_PDF_REPORTS',len(result['reports']))
if __name__=='__main__':
    main()
