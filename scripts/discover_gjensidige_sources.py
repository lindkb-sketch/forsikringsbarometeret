#!/usr/bin/env python3
"""Conservative discovery of future quarterly Gjensidige XLSX and PDF URLs.

Scrapes issuer-controlled investor pages, never guesses asset URLs. A quarter is
eligible only when exactly one XLSX and PDF are explicitly labelled with the
same year and quarter in nearby page text. Unclear cases remain unpublished.
"""
import html,json,re,urllib.parse,urllib.request
from html.parser import HTMLParser
from pathlib import Path

INDEX="https://www.gjensidige.com/investor-relations/reports-and-presentations"
ALLOWED=("gjensidige.com","mb.cision.com")
class Links(HTMLParser):
    def __init__(self):
        super().__init__();self.links=[];self.href=None;self.label=[]
    def handle_starttag(self,tag,attrs):
        if tag=="a":
            self.href=dict(attrs).get("href");self.label=[]
    def handle_data(self,data):
        if self.href is not None:self.label.append(data)
    def handle_endtag(self,tag):
        if tag=="a" and self.href is not None:
            self.links.append((self.href,html.unescape(" ".join(self.label))))
            self.href=None
def discover(page,base=INDEX):
    parser=Links();parser.feed(page)
    grouped={}
    for href,label in parser.links:
        url=urllib.parse.urljoin(base,html.unescape(href))
        parsed=urllib.parse.urlparse(url)
        if parsed.scheme!="https" or parsed.hostname not in ALLOWED:continue
        extension=parsed.path.lower().rsplit(".",1)[-1]
        if extension not in ("xlsx","pdf"):continue
        descriptor=html.unescape(label+" "+urllib.parse.unquote(parsed.path))
        period=re.search(r"(?:q([1-4])\D{0,8}(20\d{2})|(20\d{2})\D{0,8}q([1-4]))",descriptor,re.I)
        if not period:continue
        quarter=int(period.group(1) or period.group(4))
        year=int(period.group(2) or period.group(3))
        if extension=="pdf" and not re.search(r"report|interim|quarter|delårs|kvartal",descriptor,re.I):continue
        if extension=="xlsx" and not re.search(r"key.figures|investor|financial|nøkkeltall|excel",descriptor,re.I):continue
        grouped.setdefault((year,quarter),{}).setdefault(extension,set()).add(url)
    return [{"company":"Gjensidige","year":year,"quarter":quarter,
             "workbook_url":next(iter(items["xlsx"])),"report_pdf_url":next(iter(items["pdf"])),
             "segments":"gjensidige_pm_bm","approved":False,
             "source_index_url":base}
            for (year,quarter),items in sorted(grouped.items())
            if len(items.get("xlsx",()))==len(items.get("pdf",()))==1]

def fetch(url=INDEX):
    req=urllib.request.Request(url,headers={"User-Agent":"Forsikringsbarometeret/1.0"})
    with urllib.request.urlopen(req,timeout=35) as response:
        if response.geturl().split("/")[2]!="www.gjensidige.com":
            raise ValueError("Unexpected issuer index redirect")
        data=response.read(3_000_001)
        if len(data)>3_000_000:raise ValueError("Index too large")
        return data.decode("utf-8")

if __name__=="__main__":
    candidates=discover(fetch())
    path=Path(__file__).resolve().parents[1]/"data"/"gjensidige_discovery_candidates.json"
    path.write_text(json.dumps({"index":INDEX,"candidates":candidates},indent=2)+"\n")
    print(f"Found {len(candidates)} explicitly labelled official source pairs; candidates are NOT automatically approved")
