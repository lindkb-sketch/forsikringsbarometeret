#!/usr/bin/env python3
"""Discover official Storebrand quarterly PDF links; never infer numeric results."""
import html.parser
import json
import re
import time
import urllib.parse
import urllib.request

ASA = 'https://www.storebrand.com/welcome/investor-relations/quarterly-reporting/storebrand-asa'
FORSIKRING = 'https://www.storebrand.com/welcome/investor-relations/quarterly-reporting/storebrand-forsikring-as'
HOSTS = frozenset(('storebrand.com', 'www.storebrand.com', 'storebrand.no', 'www.storebrand.no'))


def official(url):
    p = urllib.parse.urlsplit(url)
    return p.scheme == 'https' and p.hostname in HOSTS and not p.username and not p.password


class Links(html.parser.HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.current = None
        self.depth = 0

    def handle_starttag(self, tag, attrs):
        if tag == 'a' and self.current is None:
            self.current = {'href': dict(attrs).get('href', ''), 'text': ''}
            self.depth = 1
        elif self.current is not None:
            self.depth += 1

    def handle_data(self, data):
        if self.current is not None:
            self.current['text'] += data

    def handle_endtag(self, tag):
        if self.current is not None:
            self.depth -= 1
            if self.depth <= 0:
                self.links.append(self.current)
                self.current = None


def links(page, base):
    parser = Links()
    parser.feed(page)
    return [(a['text'].strip(), urllib.parse.urljoin(base, a['href'])) for a in parser.links]


def fetch(url):
    if not official(url):
        raise ValueError('Only official Storebrand HTTPS hosts allowed')
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (compatible; Forsikringsbarometeret/1.0)', 'Accept': 'text/html'})
    last_error = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=25) as response:
                if not official(response.geturl()):
                    raise ValueError('Unexpected redirect to non-Storebrand host')
                blob = response.read(4_000_001)
            if len(blob) > 4_000_000:
                raise ValueError('HTML too large')
            return blob.decode('utf-8', errors='replace')
        except (OSError, TimeoutError) as exc:
            last_error = exc
            if attempt < 2:
                time.sleep(attempt + 1)
    raise RuntimeError(f'Official Storebrand page unavailable: {url}: {last_error}')


def is_pdf(url):
    return official(url) and urllib.parse.urlsplit(url).path.lower().endswith('.pdf')


def discover(fetcher=fetch, year=2026):
    found = []
    group_url = f'{ASA}/{year}'
    page = fetcher(group_url)
    quarter = None
    for match in re.finditer(r'<(?:h[1-6]|a)\b[^>]*>.*?</(?:h[1-6]|a)>', page, re.I | re.S):
        fragment = match.group()
        plain = re.sub('<[^>]+>', ' ', fragment)
        heading = re.search(r'\b([1-4])(?:st|nd|rd|th)?\s*(?:quarter|kvartal)\b', plain, re.I)
        if heading and not fragment.lstrip().lower().startswith('<a'):
            quarter = int(heading.group(1))
        if quarter is None:
            continue
        for text, url in links(fragment, group_url):
            if re.fullmatch(r'Interim report|Quarterly report|Kvartalsrapport', text, re.I) and is_pdf(url):
                found.append(dict(company='Storebrand', entity='Storebrand ASA', scope='group', year=year, quarter=quarter, document_url=url, status='discovered_not_imported'))
    page = fetcher(FORSIKRING)
    current_year = None
    for match in re.finditer(r'<(?:h[1-6]|a)\b[^>]*>.*?</(?:h[1-6]|a)>', page, re.I | re.S):
        fragment = match.group()
        plain = re.sub('<[^>]+>', ' ', fragment).strip()
        yr = re.fullmatch(r'(20\d{2})', plain)
        if yr:
            current_year = int(yr.group(1))
        if current_year != year:
            continue
        for text, url in links(fragment, FORSIKRING):
            q = re.fullmatch(r'([1-4])(?:st|nd|rd|th)?\s*(?:quarter|kvartal)', text, re.I)
            if q and is_pdf(url):
                found.append(dict(company='Storebrand', entity='Storebrand Forsikring AS', scope='norway', year=year, quarter=int(q.group(1)), document_url=url, status='discovered_not_imported'))
    unique = {(r['entity'], r['year'], r['quarter']): r for r in found}
    return {'reports': sorted(unique.values(), key=lambda r: (r['scope'], r['quarter'])), 'discovery_only': True}


if __name__ == '__main__':
    print(json.dumps(discover(), indent=2, ensure_ascii=False))
