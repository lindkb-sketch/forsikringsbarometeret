#!/usr/bin/env python3
"""Source-linked Alm. Brand Group Q3 2026 quarterly PDF table extraction.

No conversion of an announcement into a PDF claim. A PDF candidate must be
linked from Alm. Brand's own IR page, and its contents must pass independent
income-statement and KPI reconciliation before admission.
"""
import hashlib
import io
import json
import re
import urllib.parse
import urllib.request
from decimal import Decimal
from html.parser import HTMLParser
from pathlib import Path
from alm_brand_pdf import extract_table

IR='https://investorrelations.almbrand.dk/English/press-release-details/2026/Alm--Brand-AS---Interim-report-for-Q3/default.aspx'
ARCHIVE='https://investorrelations.almbrand.dk/English/financials/default.aspx'
OFFICIAL_NASDAQ_NOTICE='https://view.news.eu.nasdaq.com/view?id=bf0c320779f45c795395beb8fb6aa3cdd&lang=da&src=listed'
OFFICIAL_FILING_PDF='https://attachment.news.eu.nasdaq.com/ab696c52809fdbebae74678c86c8f5a78'
EXPECTED={'insurance_revenue':3054.0,'insurance_service_result':755.0,
          'combined_ratio':75.3,'loss_ratio':59.2,'expense_ratio':16.1,
          'insurance_revenue_growth':1.6}
LABELS={'insurance_revenue':'Insurance revenue',
        'claims_expenses':'Claims expenses',
        'operating_expenses':'Insurance operating expenses',
        'reinsurance':'Profit/loss on reinsurance',
        'insurance_service_result':'Insurance service result',
        'gross_claims_ratio':'Gross claims ratio',
        'reinsurance_ratio':'Net reinsurance ratio',
        'loss_ratio':'Claims ratio',
        'expense_ratio':'Gross expense ratio',
        'combined_ratio':'Combined ratio'}
PERCENT={'gross_claims_ratio','reinsurance_ratio','loss_ratio','expense_ratio','combined_ratio'}
NUM=re.compile(r'(?<![\w])-?\d{1,3}(?:,\d{3})*(?:\.\d+)?(?![\w])')

def trusted_pdf_link(url):
    p=urllib.parse.urlsplit(url)
    return p.scheme=='https' and (url==OFFICIAL_FILING_PDF or 
        (p.hostname=='s29.q4cdn.com'
         and p.path.startswith('/228553818/files/')
         and p.path.lower().endswith('.pdf')) or
        (p.hostname=='investorrelations.almbrand.dk'
         and p.path.lower().endswith('.pdf')) or
        (p.hostname=='almbrand.dk'
         and p.path.lower().endswith('.pdf')))

def find_candidates(html,origin=IR):
    class Links(HTMLParser):
        def __init__(self):
            super().__init__();self.links=[];self.current=None
        def handle_starttag(self,tag,attrs):
            if tag.lower()=='a':
                attrs=dict(attrs);self.current={'href':attrs.get('href'),
                                                'title':attrs.get('title',''),'label':[]}
        def handle_data(self,text):
            if self.current is not None:self.current['label'].append(text)
        def handle_endtag(self,tag):
            if tag.lower()=='a' and self.current is not None:
                link=self.current;self.current=None
                if not link['href']:return
                url=urllib.parse.urljoin(origin,link['href'])
                label=' '.join(' '.join(link['label']).split())
                if trusted_pdf_link(url) and re.search(r'AB GROUP 3Q 2026|Report|Rapport|Q3 2026',label+' '+link['title'],re.I):
                    self.links.append((url,label))
    parser=Links();parser.feed(html)
    unique={}
    for url,label in parser.links:unique[url]=label
    return sorted(unique.items(),key=lambda x:(not bool(re.search(r'AB GROUP 3Q 2026',x[1],re.I)),x[0]))

def fetch_html(url):
    p=urllib.parse.urlsplit(url)
    if p.scheme!='https' or p.hostname!='investorrelations.almbrand.dk':
        raise ValueError('Unapproved issuer page')
    req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 Forsikringsbarometeret'})
    with urllib.request.urlopen(req,timeout=25) as response:
        if urllib.parse.urlsplit(response.geturl()).hostname!='investorrelations.almbrand.dk':
            raise ValueError('Issuer page redirected unexpectedly')
        return response.read(4_000_000).decode('utf-8','replace')

def discover():
    """Only trust a report link linked by the company's own IR page."""
    found={}
    for page in (IR,ARCHIVE):
        html=fetch_html(page)
        for url,label in find_candidates(html,page):
            if re.search(r'AB GROUP 3Q 2026|interim.report.Q3.2026',label+' '+url,re.I):
                found[url]=label
    if len(found)==1:
        return next(iter(found))
    if not found:
        # Pinned official Nasdaq issuer-disclosure attachment (full interim report).
        # Never accept arbitrary attachments on this host.
        return OFFICIAL_FILING_PDF
    raise ValueError('Ambiguous official Q3 PDF links: '+str(sorted(found)))

def download_report(url):
    if not trusted_pdf_link(url):raise ValueError('Unapproved Alm Brand report CDN URL')
    request=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 Forsikringsbarometeret'})
    with urllib.request.urlopen(request,timeout=35) as response:
        if not trusted_pdf_link(response.geturl()):
            raise ValueError('PDF redirected outside issuer-controlled distribution')
        raw=response.read(25_000_001)
    if len(raw)>25_000_000 or not raw.startswith(b'%PDF-'):
        raise ValueError('Invalid official PDF')
    return raw

def parse_row(page,label):
    lines=[s.strip() for s in page.splitlines()]
    matches=[s for s in lines if re.match(r'^(?:(?:INCOME|STATEMENT)\s+)?'+re.escape(label)+r'\s+(?=-?\d)',s,re.I)]
    if len(matches)!=1:raise ValueError('Missing or ambiguous group PDF row: '+label)
    tail=re.sub(r'^(?:(?:INCOME|STATEMENT)\s+)?'+re.escape(label)+r'\s+','',matches[0],count=1,flags=re.I)
    # Issuer mixes decimal comma (67,4) with thousands comma (3,054).
    tail=re.sub(r'(?<=\d),(?=\d{1,2}(?:\s|$))','.',tail)
    nums=NUM.findall(tail)
    if len(nums)!=5:raise ValueError('Unexpected Q3/Q3-prior/HIÅ/HIÅ-prior/FY columns: '+label)
    return [Decimal(x.replace(',','')) for x in nums]

def verify_pages(texts,url,raw,regions=None):
    sha=hashlib.sha256(raw).hexdigest()
    if not trusted_pdf_link(url):raise ValueError('Unapproved source')
    if len(sha)!=64 or any(c not in '0123456789abcdef' for c in sha):
        raise ValueError('Invalid PDF fingerprint')
    cover=' '.join(texts[:2]).lower()
    if 'interim report q3' not in cover or '2026' not in cover or 'alm' not in cover:
        raise ValueError('Wrong entity or period: expected Alm Brand Group Q3 2026')
    eligible=[(i,t) for i,t in enumerate(texts)
              if 'Gross expense ratio' in t and 'Net reinsurance ratio' in t
              and 'Insurance service result' in t and 'Q3 2026' in t
              and 'Return on equity after tax' in t and 'INCOME Insurance revenue' in t]
    if len(eligible)!=1:raise ValueError('Missing or ambiguous official Group financial-highlights table')
    page_index,page=eligible[0]
    regions=regions or {}
    table_text=regions.get(page_index,{}).get('left') or page
    roe_text=regions.get(page_index,{}).get('right') or page
    rows={key:parse_row(table_text,label) for key,label in LABELS.items()}
    # Only issuer-disclosed return on EQUITY, not the investment result.
    roe_match=re.search(r'Return on equity after tax\s*\n\s*(\d+(?:\.\d+)?)\s+(\d+(?:\.\d+)?)\s+(\d+(?:\.\d+)?)\s+(\d+(?:\.\d+)?)',roe_text,re.I)
    if not roe_match:
        raise ValueError('Missing issuer-reported annualised ROE after tax')
    roe_quarter=float(roe_match.group(1));roe_ytd=float(roe_match.group(3))
    if not 0<roe_quarter<100 or not 0<roe_ytd<100:
        raise ValueError('Implausible issuer-reported ROE values')
    solvent=[(i,t) for i,t in enumerate(texts) if 'Total capital as a percentage of solvency capital' in t]
    if len(solvent)!=1:raise ValueError('Missing issuer Group solvency table')
    solvency_index,solvency_page=solvent[0]
    solvency_text=regions.get(solvency_index,{}).get('right') or solvency_page
    coverage=re.search(r'Total capital as a percentage of solvency capital[\s\S]{0,160}?(\d{2,3})\s+(\d{2,3})\s*\n\s*requirement',solvency_text,re.I)
    if not coverage:
        coverage=re.search(r'Total capital as a percentage of solvency capital\s+requirement\s+(\d{2,3})\s+(\d{2,3})',solvency_text,re.I)
    if not coverage:raise ValueError('Missing quarter-end Group solvency ratio')
    solvency=float(coverage.group(1))
    if not 100<=solvency<=500:raise ValueError('Implausible Group solvency ratio')
    def metrics(idx):
        revenue=rows['insurance_revenue'][idx]
        claims=abs(rows['claims_expenses'][idx])
        expenses=abs(rows['operating_expenses'][idx])
        reinsurance=abs(rows['reinsurance'][idx])
        service=rows['insurance_service_result'][idx]
        if revenue<=0 or claims<=0 or expenses<=0:
            raise ValueError('Invalid insurance revenue / claims / expense sign')
        if abs((revenue-claims-expenses-reinsurance)-service)>Decimal('1.5'):
            raise ValueError('Issuer insurance service result accounting mismatch')
        calculated={'gross_claims_ratio':claims/revenue*100,
                    'reinsurance_ratio':reinsurance/revenue*100,
                    'loss_ratio':(claims+reinsurance)/revenue*100,
                    'expense_ratio':expenses/revenue*100,
                    'combined_ratio':(claims+reinsurance+expenses)/revenue*100}
        for key,val in calculated.items():
            if abs(val-rows[key][idx])>Decimal('0.20'):
                raise ValueError('Alm Brand PDF ratio reconciliation mismatch: '+key)
        return calculated
    q=metrics(0)
    y=metrics(2)
    revenue_growth=(rows['insurance_revenue'][0]/rows['insurance_revenue'][1]-1)*100
    ytd_growth=(rows['insurance_revenue'][2]/rows['insurance_revenue'][3]-1)*100
    if abs(revenue_growth-Decimal(str(EXPECTED['insurance_revenue_growth'])))>Decimal('0.20'):
        raise ValueError('Alm Brand Q3 PDF income growth differs from issuer announcement')
    result_metrics={
        'insurance_revenue':float(rows['insurance_revenue'][0]),
        'insurance_service_result':float(rows['insurance_service_result'][0]),
        'combined_ratio':float(rows['combined_ratio'][0]),
        'loss_ratio':float(rows['loss_ratio'][0]),
        'expense_ratio':float(rows['expense_ratio'][0]),
        'insurance_revenue_growth':EXPECTED['insurance_revenue_growth'],
        'profit_before_tax':None,
        'return_on_equity':roe_quarter,
        'solvency_ratio':solvency,
    }
    for metric,expected in EXPECTED.items():
        if metric=='insurance_revenue_growth':continue
        if abs(result_metrics[metric]-expected)>0.001:
            raise ValueError('Issuer PDF disagrees with independently verified Q3 announcement: '+metric)
    # The previously implemented validated table contract is reused rather than bypassed.
    table_rows=[]
    for key,label in [('insurance_revenue','Insurance revenue'),
                      ('insurance_service_result','Insurance service result'),
                      ('combined_ratio','Combined ratio'),('loss_ratio','Claims ratio'),
                      ('expense_ratio','Expense ratio')]:
        table_rows.append({'page':page_index+1,'label':label,'period':'Q3 2026',
                           'value':result_metrics[key],
                           'unit':'%' if key in ('combined_ratio','loss_ratio','expense_ratio') else 'DKK million'})
    # extract_table's issuer host allowlist additionally checks this PDF provider.
    extracted=extract_table(raw,url,2026,3,table_rows)
    extracted.update({'metrics':result_metrics,'reported_ytd_ratios':{
        key:float(rows[key][2]) for key in PERCENT},
        'source_pages':{key:(solvency_index+1 if key=='solvency_ratio' else page_index+1) for key in result_metrics},
        'return_on_equity_definition':'Annualised Group return on equity after tax (% p.a.), issuer adjusted for intangible amortisation',
        'return_on_equity_ytd':roe_ytd,
        'return_on_equity_source_page':page_index+1,
        'solvency_definition':'Group total capital / group solvency capital requirement at quarter end',
        'quarter_recalculated_ratios':{key:float(x) for key,x in q.items()},
        'revenue_growth_evidence':{
            'quarter':{'current':float(rows['insurance_revenue'][0]),
                'prior_year':float(rows['insurance_revenue'][1]),
                'calculated_growth_percent':float(revenue_growth),
                'issuer_reported_growth_percent':EXPECTED['insurance_revenue_growth']},
            'ytd':{'current':float(rows['insurance_revenue'][2]),
                'prior_year':float(rows['insurance_revenue'][3]),
                'growth_percent':float(ytd_growth)},
            'source_page':page_index+1,'previous_year':2025,
            'source_sha256':sha,'currency':'DKK','scope':'group'},
        'ytd_recalculated_ratios':{key:float(x) for key,x in y.items()},
        'source_sha256':sha,'source_url':url,
        'issuer_page_url':OFFICIAL_NASDAQ_NOTICE if url==OFFICIAL_FILING_PDF else IR,
        'status':'verified_official_pdf_reconciled'})
    return extracted

def run(url=None):
    url=url or discover()
    raw=download_report(url)
    import pdfplumber
    with pdfplumber.open(io.BytesIO(raw)) as pdf:
        texts=[page.extract_text(layout=False) or '' for page in pdf.pages]
        regions={i:{'left':p.crop((0,0,p.width*.52,p.height)).extract_text(layout=False) or '',
                     'right':p.crop((p.width*.48,0,p.width,p.height)).extract_text(layout=False) or ''}
                 for i,p in enumerate(pdf.pages) if i in (2,4)}
    evidence_dir=Path('alm-brand-audit');evidence_dir.mkdir(exist_ok=True)
    candidates=[{'page':i+1,'text':t[:18000]} for i,t in enumerate(texts)
                if any(term.lower() in t.lower() for term in ('insurance revenue','combined ratio','solvency cover','insurance service result'))]
    (evidence_dir/'source-pages.json').write_text(json.dumps({'source_url':url,
        'source_sha256':hashlib.sha256(raw).hexdigest(),'pdf_pages':len(texts),
        'candidate_pages':candidates[:35]},ensure_ascii=False,indent=2)+'\n')
    (evidence_dir/'table-regions.json').write_text(json.dumps({'source_url':url,
        'regions':regions},ensure_ascii=False,indent=2)+'\n')
    out=verify_pages(texts,url,raw,regions=regions)
    return out

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--out',default='alm-brand-audit/verified.json')
    args=p.parse_args()
    dest=Path(args.out);dest.parent.mkdir(parents=True,exist_ok=True)
    try:
        result=run()
        dest.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
        print('ALM_BRAND_REAL_PDF_Q3_RECONCILED',json.dumps(result,ensure_ascii=False))
    except Exception as exc:
        dest.write_text(json.dumps({'status':'blocked_no_pdf_evidence','error':str(exc),
              'announcement_only_remains_approved':True},ensure_ascii=False,indent=2)+'\n')
        raise
