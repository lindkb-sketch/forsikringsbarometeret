#!/usr/bin/env python3
"""Import explicitly reported issuer ROE/ROOF from official quarterly PDFs only.

No estimation, no investment return used as equity return. Missing labels
remain missing; only an unambiguous, period-matched report value is published.
"""
import hashlib
import io
import json
import re
import pdfplumber
from audit_financials import DATA, audit
from build_verified_feed import build
from ingest_official_pdf import download
from publish_geographic_workbooks import atomic_write

LABELS={
 'Gjensidige':(
   r'(?:annualis(?:ed|z) return on equity|return on equity,? annualis(?:ed|z))',
   'ROE annualised'),
 'Protector':(
   r'return on equity,? annualis(?:ed|z)',
   'ROE annualised'),
 'Fremtind':(
   r'annualisert\s+egenkapitalavkastning\s+justert\s+for',
   'Annualisert egenkapitalavkastning justert for transaksjonen med Eika Forsikring AS'),
 'Tryg':(
   r'(?:return on own funds\s*\(ROOF\)|\bROOF\b)',
   'ROOF annualised'),
}
NUMBER=r'-?\d{1,3}(?:[.,]\d{1,2})?'

def extract(blob,company,year,quarter):
    if not blob.startswith(b'%PDF-'):raise ValueError('Not an issuer PDF')
    label,definition=LABELS[company]
    candidates=[]
    with pdfplumber.open(io.BytesIO(blob)) as pdf:
        for pageno,page in enumerate(pdf.pages,1):
            text=' '.join((page.extract_text() or '').split())
            # First prefer a prose statement such as ROOF was 47.0% or
            # ROE of 34.2%; no unverified positional table columns.
            patterns=[
              r'(?:'+label+r')\s*(?:was|of|at|:|increased to|amounted to|reached)?\s*('+NUMBER+r')\s*(?:per cent|%)',
              r'(?:'+label+r')\s*(?:increased|decreased)\s+to\s*('+NUMBER+r')\s*(?:per cent|%)',
            ]
            for pattern in patterns:
                for m in re.finditer(pattern,text,re.I):
                    value=float(m.group(1).replace(',','.'))
                    if -100<=value<=200:candidates.append((pageno,value))
    # Tryg's quarterly PDF states ROOF under Dividend and solvency.
    # PDF line breaks and typography can separate the caption and value.
    # Require an explicit issuer ROOF caption and percentage on the SAME
    # page, never infer ROOF from solvency ratio or ordinary profit.
    if company=='Tryg' and not candidates:
        roof_patterns=[
            re.compile(r"return\s+on\s+own\s+funds\s*\(\s*ROOF\s*\)"
                       r"[^.\n]{0,100}?(-?\d{1,3}(?:[.,]\d{1,2})?)\s*%",re.I),
            re.compile(r"\bROOF\b\s*(?:\(\s*%\s*\))?\s*(?:was|of|at|:)?"
                       r"\s*(-?\d{1,3}(?:[.,]\d{1,2})?)\s*%",re.I),
        ]
        with pdfplumber.open(io.BytesIO(blob)) as pdf:
            for pageno,page in enumerate(pdf.pages,1):
                raw=page.extract_text() or ''
                variants=[raw,re.sub(r"\s+"," ",raw)]
                for variant in variants:
                    for pattern in roof_patterns:
                        for match in pattern.finditer(variant):
                            value=float(match.group(1).replace(',','.'))
                            if -100<=value<=200:
                                candidates.append((pageno,value))
    # Fremtind's Eika-adjusted equity return is in the Holding PDF KPI
    # table. It may be split across rows and need not pass the independent
    # revenue/combined-ratio table extraction to be an official figure.
    if company=='Fremtind':
        caption=re.compile(
            r'annualisert\s+egenkapitalavkastning\s+justert\s+for\s+'
            r'(?:transaksjonen|fusjonen)\s+med\s+Eika\s*Forsikring\s+AS',
            re.I)
        with pdfplumber.open(io.BytesIO(blob)) as pdf:
            for pageno,page in enumerate(pdf.pages,1):
                lines=(page.extract_text() or '').splitlines()
                for i,line in enumerate(lines):
                    context=' '.join(lines[i:i+3])
                    m=caption.search(context)
                    if not m:continue
                    remainder=context[m.end():]
                    # Capture the first explicitly printed percentage in the
                    # current-quarter column, never a plain equity amount.
                    values=re.findall(r'(?<![\w.,])-?\d{1,3}(?:[.,]\d{1,2})?\s*%',remainder)
                    if values:
                        value=float(values[0].replace('%','').replace(' ','').replace(',','.'))
                        if -100<=value<=200:candidates.append((pageno,value))
    # Protector's official KPI appendix reports ROE in a quarterly table,
    # with a superscript footnote and a separate percent-unit column.
    # Only the first numeric value of that explicitly labelled Q-row is
    # the current quarter; do not mistake investment returns for equity.
    if company=='Protector':
        with pdfplumber.open(io.BytesIO(blob)) as pdf:
            for pageno,page in enumerate(pdf.pages,1):
                lines=(page.extract_text() or '').splitlines()
                for i,line in enumerate(lines):
                    if not re.match(r'^\s*Return on equity,?\s*annualis(?:ed|z)[¹²³*]?',line,re.I):
                        continue
                    header=' '.join(lines[max(0,i-45):i])
                    if not (re.search(r'Q\s*'+str(quarter)+r'\s*'+str(year),header,re.I)
                            or re.search(r'Q'+str(quarter)+r'\s*\(?.*?'+str(year),header,re.I)):
                        continue
                    tail=re.sub(r'^\s*Return on equity,?\s*annualis(?:ed|z)[¹²³*]*', '',line,flags=re.I)
                    m=re.match(r'\s*(?:%\s*)?(-?\d{1,3}(?:[.,]\d{1,2})?)\s*%?',tail)
                    if m:
                        candidates.append((pageno,float(m.group(1).replace(',','.'))))
    distinct={round(v,3) for _,v in candidates}
    if len(distinct)!=1:
        raise ValueError(company+' explicit return missing or ambiguous: '+str(sorted(distinct)))
    pageno,value=candidates[0]
    return pageno,value,definition

def official_tryg_presentations(year,quarter):
    """Issuer archive PDF links; never use Excel or arbitrary search results."""
    from html.parser import HTMLParser
    from urllib.parse import urljoin,urlparse
    from urllib.request import Request,urlopen
    class Links(HTMLParser):
        def __init__(self):
            super().__init__();self.url=None;self.text=[];self.links=[]
        def handle_starttag(self,tag,attrs):
            if tag=='a':
                self.url=dict(attrs).get('href');self.text=[]
        def handle_data(self,data):
            if self.url is not None:self.text.append(data)
        def handle_endtag(self,tag):
            if tag=='a' and self.url is not None:
                self.links.append((self.url,' '.join(self.text)))
                self.url=None
    archive=f'https://tryg.com/en/downloads-{year}'
    with urlopen(Request(archive,headers={'User-Agent':'Forsikringsbarometeret/1.0'}),timeout=20) as response:
        parser=Links();parser.feed(response.read(350_001).decode('utf-8','replace'))
    for href,title in parser.links:
        dest=urljoin(archive,href)
        parsed=urlparse(dest)
        if parsed.scheme!='https' or parsed.hostname not in ('tryg.com','www.tryg.com'):continue
        if not parsed.path.lower().endswith('.pdf'):continue
        if re.search(rf'Q{quarter}\s+{year}\s*[-–]\s*Investor presentation',title,re.I):
            yield dest

def run():
    data=json.loads(DATA.read_text(encoding='utf-8'))
    records=data['observations']
    sources=sorted({(r['company'],r['year'],r['quarter'],r['source_url'])
        for r in records if r.get('company') in LABELS and
        r.get('scope')=='group' and r.get('period_type')=='quarter'
        and r.get('metric')=='insurance_revenue' and
        r.get('source_type')=='official_quarterly_report' and r.get('year')>=2025
        and (not r.get('source_document_period')
             or r['source_document_period']==f"Q{r['quarter']} {r['year']}")})
    existing={(r['company'],r['year'],r['quarter'],r['scope'],r['period_type'],r['metric']):r
              for r in records}
    added=0
    for company,year,quarter,url in sources:
        # Never assign a previous year's ROE/ROOF by reading the current
        # period's PDF without a separately verified year-labelled column.
        # In particular, the 2026 Gjensidige/Tryg PDF must not generate a
        # 2025 observation simply because a 2025 revenue comparator exists.
        document_year=re.search(r'20\d{2}',url)
        if document_year and int(document_year.group())>year:
            print('::warning::RETURN_PERIOD_DOCUMENT_MISMATCH',company,year,quarter,url,flush=True)
            continue
        k=(company,year,quarter,'group','quarter','return_on_equity')
        if k in existing:continue
        try:
            blob=download(url)
            page,value,definition=extract(blob,company,year,quarter)
        except Exception as error:
            # Tryg publishes an official PDF investor presentation for each
            # quarter, including Q4 when the annual PDF is oversized.
            # A reported ROOF value from that presentation is sufficient.
            recovered=None
            if company=='Tryg':
                try:
                    for alternate in official_tryg_presentations(year,quarter):
                        try:
                            candidate=download(alternate)
                            verified_page,verified_value,verified_definition=extract(candidate,company,year,quarter)
                            recovered=(alternate,candidate,verified_page,verified_value,verified_definition)
                            break
                        except (ValueError,OSError,TimeoutError):
                            continue
                except (ValueError,OSError,TimeoutError) as lookup_error:
                    print('::warning::RETURN_PRESENTATION_UNAVAILABLE',company,year,quarter,str(lookup_error)[:120],flush=True)
            if recovered is None:
                print('::warning::RETURN_PDF_UNVERIFIED',company,year,quarter,str(error)[:130],flush=True)
                continue
            url,blob,page,value,definition=recovered
        row=dict(company=company,year=year,quarter=quarter,scope='group',
            source_scope='group',period_type='quarter',metric='return_on_equity',
            value=value,unit='percent',status='reported',
            source_type='official_quarterly_report',source_url=url,
            source_page=page,source_sha256=hashlib.sha256(blob).hexdigest(),
            source_document_period=f'Q{quarter} {year}',source_definition=definition)
        records.append(row)
        existing[k]=row
        added+=1
        print('REPORTED_RETURN_PDF',company,year,quarter,value,definition,flush=True)
    if not audit(data)['ok']:raise ValueError('Reported returns failed audit')
    if added:
        atomic_write(DATA,data)
        atomic_write(DATA.parent/'verified_financial_feed.json',build(data))
    print('REPORTED_RETURN_PDF_ADDED',added,flush=True)

if __name__=='__main__':run()
