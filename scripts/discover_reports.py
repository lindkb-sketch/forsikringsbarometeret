#!/usr/bin/env python3
"""Discover potential official interim-report PDFs on registered issuer pages.
Candidates are NOT approved financial data and never update the dashboard.\nQ4 annual/full-year files are discovery candidates only: a validated importer must\nfind a separately labelled fourth-quarter column before publishing any KPI.
"""
import json,re,urllib.request,urllib.parse,html.parser,sys
from pathlib import Path
from verify_nine_document_bytes import approved as approved_delivery_host
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
  # Issuer-approved CDN hosts only; arbitrary cross-domain links are rejected.
  # XLSX remains a discovery candidate for legacy report importers; byte verifier is PDF-only.
  trusted_url=url if parsed.path.lower().endswith('.pdf') else url+'.pdf' if parsed.path.lower().endswith('.xlsx') else url
  base=urllib.parse.urlparse(base_url)
  if parsed.hostname!=base.hostname and not approved_delivery_host(company,trusted_url):continue
  label=(link["text"]+" "+urllib.parse.unquote(parsed.path)).lower()
  # Discovery is diagnostic; no candidate is approved for publication.
  if not re.search(r"\.(?:pdf|xlsx)$",parsed.path,re.I):continue
  report=re.search(r"(interim.?report|quarterly.?report|kvartalsrapport|delårsrapport|q[1-4].{0,30}report|report.{0,30}q[1-4]|investor.?tables|investor.?tabeller|annual.?report|annual.?results|full.?year|year.?end|årsrapport|årsresultat|helårsrapport|helårsresultat|financial.?statements.?release)",label,re.I)
  presentation=re.search(r"(presentation|presentasjon|investor.?slides|results.?slides|resultatpresentasjon)",label,re.I)
  if re.search(r"(press.release|pressemelding|newsletter|supplementary)",label,re.I):continue
  if presentation:
   if not re.search(r"(q[1-4]|[1-4]\.?\s*kvartal|[1-4]\.?\s*quarter|annual|full.?year|helår|årsresultat)",label,re.I):continue
   kind="results_presentation"
   status="candidate_requires_presentation_verification"
  elif report:
   kind="quarterly_report"
   status="candidate_requires_quarterly_report_verification"
  else:continue
  if url not in seen:
   found.append({"company":company,"document_url":url,"document_type":kind,
                 "status":status,
                 "link_text":link["text"].strip()})
   seen.add(url)
 return found
def issuer_report_pages(html,base_url,company):
 """Find official report landing pages, not arbitrary external links."""
 parser=Links();parser.feed(html)
 result=[]
 for link in parser.links:
  url=urllib.parse.urljoin(base_url,link["href"])
  p=urllib.parse.urlsplit(url)
  if p.scheme!="https" or p.username or p.password or p.port not in (None,443):continue
  label=link["text"]+" "+urllib.parse.unquote(p.path)
  if company=="Frende":
   accepted=p.hostname=="frende.wrep.it" and re.search(r"frende.holding",label,re.I) and re.search(r"q[1-4]|[1-4]\\.\\s*kvartal",label,re.I)
  elif company=="Alm. Brand":
   accepted=p.hostname=="investorrelations.almbrand.dk" and "/press-release-details/" in p.path.lower() and re.search(r"interim.report|quarterly.report",label,re.I)
  else:accepted=False
  if accepted:result.append((url,link["text"].strip()))
 return list(dict.fromkeys(result))

def discover_landing_pdfs(html,url,company,label):
 """Accept PDF attachments only on the issuer-approved delivery hosts."""
 parser=Links();parser.feed(html)
 found=[]
 for link in parser.links:
  target=urllib.parse.urljoin(url,link["href"])
  if not approved_delivery_host(company,target):continue
  description=link["text"]+" "+urllib.parse.unquote(target)
  if re.search(r"presentation|presentasjon|slides|appendix|supplement|press.release",description,re.I):continue
  if not re.search(r"report|rapport|download|last ned|pdf",description,re.I):continue
  found.append({"company":company,"document_url":target,"document_type":"quarterly_report",
                "status":"candidate_requires_quarterly_report_verification","link_text":label+" "+link["text"],"landing_url":url})
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
 candidates=[];errors=[];warnings=[]
 for company,url in sorted(pages):
  try:
   html=fetcher(url)
   candidates+=discover(html,url,company)
   if company in ("Frende","Alm. Brand"):
    pages=issuer_report_pages(html,url,company)
    for landing,label in pages[:16]:
     try:
      attachments=discover_landing_pdfs(fetcher(landing),landing,company,label)
      candidates+=attachments
      if not attachments:
       warnings.append(f"{company}: no downloadable PDF on {landing}")
     except Exception as e:warnings.append(f"{company}: {type(e).__name__}: {e}")
  except Exception as e:errors.append(f"{company}: {type(e).__name__}: {e}")
 return {"candidates":candidates,"errors":errors,"complete":not errors,"warnings":warnings}
if __name__=="__main__":
 result=scan()
 # Never overwrite previous results on failure
 if result["complete"]:OUTPUT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
 print(json.dumps({"candidates":len(result["candidates"]),"errors":result["errors"]},ensure_ascii=False))
 sys.exit(bool(result["errors"]))
