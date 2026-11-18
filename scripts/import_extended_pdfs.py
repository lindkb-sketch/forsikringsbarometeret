#!/usr/bin/env python3
"""Conservative issuer-PDF discovery and extraction for KLP and Alm. Brand.

Only approved issuer-hosted PDF URLs are downloaded. Candidate extraction is
diagnostic until a report-specific metric mapping is verified; no guesswork,
no OCR, no overwriting an approved financial snapshot.
"""
import hashlib
import io
import json
import re
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCES = {
    'KLP Skadeforsikring': ('www.klp.no', 'klp.no'),
    'Alm. Brand': ('investorrelations.almbrand.dk', 'almbrand.dk'),
}
INDEX = {
    'KLP Skadeforsikring': 'https://www.klp.no/om-klp/finans-og-ir/rapporter-og-presentasjoner',
    'Alm. Brand': 'https://investorrelations.almbrand.dk/English/financials/default.aspx',
}
MAX_PDF_BYTES = 25_000_000


def approved(url, company):
    parts = urllib.parse.urlsplit(url)
    host = (parts.hostname or '').lower()
    return parts.scheme == 'https' and host in SOURCES[company] and (
        parts.path.lower().endswith('.pdf') or '.pdf' in parts.path.lower()
    )


def candidates(document, base_url, company):
    """Discover only directly linked issuer PDF files; never infer their period."""
    from html.parser import HTMLParser
    class Links(HTMLParser):
        def __init__(self):
            super().__init__()
            self.links = []
        def handle_starttag(self, tag, attrs):
            if tag.lower() == 'a':
                url = dict(attrs).get('href')
                if url:
                    self.links.append(url)
    parser = Links()
    parser.feed(document)
    urls = {urllib.parse.urljoin(base_url, url) for url in parser.links}
    return sorted(url for url in urls if approved(url, company))


def download(url, company):
    if not approved(url, company):
        raise ValueError('PDF URL not approved for ' + company)
    req = urllib.request.Request(url, headers={'User-Agent': 'Forsikringsbarometeret/1.0'})
    with urllib.request.urlopen(req, timeout=30) as response:
        final = response.geturl()
        if not approved(final, company):
            raise ValueError('PDF redirect outside approved issuer hosts')
        raw = response.read(MAX_PDF_BYTES + 1)
    if len(raw) > MAX_PDF_BYTES or not raw.startswith(b'%PDF-'):
        raise ValueError('Invalid or oversized official PDF')
    return raw


def pages(raw):
    import pdfplumber
    with pdfplumber.open(io.BytesIO(raw)) as pdf:
        if not 1 <= len(pdf.pages) <= 500:
            raise ValueError('Unexpected PDF page count')
        return [page.extract_text() or '' for page in pdf.pages]


def inspect_pdf(raw, company, url):
    """Return page-located evidence, not financial observations."""
    if not approved(url, company):
        raise ValueError('Unapproved PDF source')
    result = {'company': company, 'source_url': url,
              'source_sha256': hashlib.sha256(raw).hexdigest(),
              'status': 'requires_manual_metric_mapping', 'pages': []}
    for number, text in enumerate(pages(raw), 1):
        if re.search(r'(premieinntekter|forsikringsinntekter|insurance revenue|combined ratio|skadeprosent|expense ratio|omkostningsprocent)', text, re.I):
            result['pages'].append({'page': number, 'keywords_found': sorted(set(
                x.lower() for x in re.findall(
                    r'premieinntekter|forsikringsinntekter|insurance revenue|combined ratio|skadeprosent|expense ratio|omkostningsprocent',
                    text, re.I)))})
    return result


def main():
    """Produce a diagnostic candidate manifest without publishing metrics."""
    output = {}
    for company, index in INDEX.items():
        try:
            req = urllib.request.Request(index, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=20) as response:
                if response.geturl().split('/')[2].lower() not in SOURCES[company]:
                    raise ValueError('Unexpected issuer index redirect')
                html = response.read(3_000_000).decode('utf-8', 'replace')
            urls = candidates(html, index, company)
            output[company] = {'index_url': index, 'candidate_pdf_urls': urls,
                               'status': 'discovery_only_not_verified'}
        except (OSError, ValueError) as exc:
            output[company] = {'index_url': index, 'candidate_pdf_urls': [],
                               'status': 'source_unavailable', 'error': str(exc)[:180]}
    print(json.dumps(output, ensure_ascii=False, indent=2))
    # Discovery does not assert successful import or investor readiness.


if __name__ == '__main__':
    main()
