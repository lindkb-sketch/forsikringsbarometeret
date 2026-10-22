#!/usr/bin/env python3
"""Fail-safe Gjensidige report availability diagnostic; no numeric publication."""
import argparse
import html.parser
import json
import re
import urllib.parse
import urllib.request

ARCHIVE = "https://www.gjensidige.com/investor-relations/reports-and-presentations"
HOME = "https://www.gjensidige.com/investor-relations/"
ALLOWED = {"gjensidige.com", "www.gjensidige.com"}

class Anchors(html.parser.HTMLParser):
    def __init__(self):
        super().__init__()
        self.items = []
        self.href = None
        self.label = ""
    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self.href = dict(attrs).get("href")
            self.label = ""
    def handle_data(self, data):
        if self.href is not None:
            self.label += data
    def handle_endtag(self, tag):
        if tag == "a" and self.href is not None:
            self.items.append((self.label.strip(), self.href))
            self.href = None

def is_official_pdf(url):
    p = urllib.parse.urlsplit(url)
    return p.scheme == "https" and p.hostname in ALLOWED and p.path.lower().endswith(".pdf")

def candidates(page, base=ARCHIVE, quarter=3, year=2026):
    parser = Anchors()
    parser.feed(page)
    results = []
    for label, href in parser.items:
        url = urllib.parse.urljoin(base, href)
        context = urllib.parse.unquote(label + " " + url).lower()
        if is_official_pdf(url) and re.search(r"(?:q|quarter|kvartal)[-_ ]?" + str(quarter), context) and str(year) in context:
            if not re.search(r"presentation|presentasjon|slides|pre.close|invitation", context):
                results.append(url)
    return sorted(set(results))

def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Forsikringsbarometeret/1.0"})
    with urllib.request.urlopen(req, timeout=30) as response:
        if urllib.parse.urlsplit(response.geturl()).hostname not in ALLOWED:
            raise ValueError("Off-domain redirect")
        page = response.read(4_000_001)
    if len(page) > 4_000_000:
        raise ValueError("Report index exceeds size limit")
    return page.decode("utf-8", errors="replace")

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--quarter", type=int, choices=(1,2,3,4), default=3)
    p.add_argument("--year", type=int, default=2026)
    args = p.parse_args()
    matches = []
    errors = []
    for url in (ARCHIVE, HOME):
        try:
            matches.extend(candidates(fetch(url), url, args.quarter, args.year))
        except Exception as exc:
            errors.append(str(exc))
    result = {"company": "Gjensidige", "period": f"Q{args.quarter} {args.year}",
              "official_pdf_candidates": sorted(set(matches)),
              "source_pages_checked": [ARCHIVE, HOME],
              "source_errors": errors,
              "status": "candidate_only_not_verified_or_published",
              "note": "A PDF link is not proof of report content or correct financial numbers."}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if len(errors) == 2:
        raise SystemExit("Both official source pages unavailable")

if __name__ == "__main__":
    main()
