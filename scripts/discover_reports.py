#!/usr/bin/env python3
"""Discover potential official interim-report PDFs on registered issuer pages.
Candidates are NOT approved financial data and never update the dashboard.\nQ4 annual/full-year files are discovery candidates only: a validated importer must\nfind a separately labelled fourth-quarter column before publishing any KPI.
"""
import json,re,urllib.request,urllib.parse,html.parser,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
REGISTRY=ROOT/"data/report_sources.json"
OUTPUT=ROOT/"data/report_candidates.json"
class Links(html.parser.HTMLParser):
 def __init__(self):
  super().__init__();self.links=[];self.current=None
 def handle_starttag(self,tag,attrs):
  if tag=="a":
   self.current={"href":dict(attrs).get("href",""),"text":""}
 def handle_data(self,data):
  if self.current is not None:self.current["text"]+=data
 def handle_endtag(self,tag):
  if tag=="a" and self.current is not None:
   self.links.append(self.current);self.current=None
def discover(html,base_url,company):
 parser=Links();parser.feed(html)
 found=[];seen=set()
 for link in parser.links:
  url=urllib.parse.urljoin(base_url,link["href"])
  parsed=urllib.parse.urlparse(url)
  if parsed.scheme!="https":continue
  # Same host or same registrable domain; no third-party press distribution.
  base=urllib.parse.urlparse(base_url)
  if parsed.hostname!=base.hostname:continue
  label=(link["text"]+" "+urllib.parse.unquote(parsed.path)).lower()
  # Require interim-report context, and an explicit PDF file extension.
  if not re.search(r"\.(?:pdf|xlsx)$",parsed.path,re.I):continue
  if not re.search(r"(interim.?report|quarterly.?report|kvartalsrapport|delårsrapport|q[1-4].{0,30}report|report.{0,30}q[1-4]|investor.?tables|investor.?tabeller|annual.?report|annual.?results|full.?year|year.?end|årsrapport|årsresultat|helårsrapport|helårsresultat|financial.?statements.?release)",label,re.I):continue
  if re.search(r"(presentation|presentasjon|press.release|pressemelding|newsletter|supplementary)",label,re.I):continue
  if url not in seen:
   found.append({"company":company,"document_url":url,"status":"candidate_requires_quarterly_report_verification","link_text":link["text"].strip()})
   seen.add(url)
 return found
def scan(fetcher=None):
 if fetcher is None:
  def fetcher(url):
   req=urllib.request.Request(url,headers={"User-Agent":"Forsikringsbarometeret/1.0"})
   with urllib.request.urlopen(req,timeout=20) as r:
    blob=r.read(4*1024*1024+1)
   if len(blob)>4*1024*1024:raise ValueError("Index too large")
   return blob.decode("utf-8",errors="replace")
 sources=json.loads(REGISTRY.read_text())["sources"]
 pages={(r["company"],r["index_url"]) for r in sources if r.get("index_url")}
 # Include official year/quarter archive pages. This scans both missing
 # historical quarters and newly published periods on EVERY scheduled run.
 # Issuer-specific layouts still require their own strict numeric parsers.
 from datetime import date
 current=date.today()
 for year in range(2024,current.year+1):
  pages.add(("Tryg",f"https://tryg.com/en/downloads-{year}"))
  for quarter in range(1,5):
   if (year,quarter)>(current.year,(current.month-1)//3+1):continue
   pages.add(("Sampo",f"https://www.sampo.com/investors/quarterly-reporting/q{quarter}-{year}/"))
 # The Sampo issuer archive, not its corporate homepage, is the index.
 pages.discard(("Sampo","https://www.sampo.com/"))
 candidates=[];errors=[]
 for company,url in sorted(pages):
  try:candidates+=discover(fetcher(url),url,company)
  except Exception as e:errors.append(f"{company}: {type(e).__name__}: {e}")
 return {"candidates":candidates,"errors":errors,"complete":not errors}
if __name__=="__main__":
 result=scan()
 # Never overwrite previous results on failure
 if result["complete"]:OUTPUT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
 print(json.dumps({"candidates":len(result["candidates"]),"errors":result["errors"]},ensure_ascii=False))
 sys.exit(bool(result["errors"]))
