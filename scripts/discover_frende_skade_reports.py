#!/usr/bin/env python3
"""Discover Frende Skadeforsikring quarterly PDF report references without Excel."""
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

def build(html, previous=None):
    candidates = discover(html)
    # Historical exchange announcements are authoritative entry points to
    # attached original PDFs, not evidence that numeric cells were extracted.
    for quarter, url in SEED_2026.items():
        candidates.setdefault((2026, quarter), url)
    if previous:
        for item in previous.get('reports', []):
            key = (item['year'],item['quarter'])
            candidates.setdefault(key,item['source_url'])
    return {'entity':'Frende Skadeforsikring AS','source_policy':'official PDF reports only',
            'reports':[{'year':y,'quarter':q,'source_url':url,
                        'verification':'report_link_only_not_financial_values'}
                       for (y,q),url in sorted(candidates.items(),reverse=True)]}

def main():
    req = urllib.request.Request(ARCHIVE, headers={'User-Agent':'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=30) as response:
        if urllib.parse.urlparse(response.geturl()).hostname not in ('frende.no','www.frende.no'):
            raise ValueError('Untrusted archive redirect')
        markup = response.read(3_000_001)
    if len(markup)>3_000_000:
        raise ValueError('Archive too large')
    old=json.loads(OUT.read_text()) if OUT.exists() else None
    result=build(markup.decode('utf-8','replace'),old)
    OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('FRENDE_SKADE_PDF_REPORTS',len(result['reports']))
if __name__=='__main__':
    main()
