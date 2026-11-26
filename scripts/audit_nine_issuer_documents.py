#!/usr/bin/env python3
"""Period-specific issuer document discovery and evidence collection.

Never classify a report as a presentation because an archive path contains
"presentasjoner". Never classify parent/segment reports as the target entity.
No financial observations are altered. Unknown sources/layouts remain unresolved.
"""
import hashlib
import html
import io
import json
import os
import re
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote,urljoin,urlsplit,urlencode
from urllib.request import Request,build_opener,HTTPRedirectHandler
from verify_nine_document_bytes import COMPANIES,DELIVERY
from update_newsweb_notices import Client,ISSUERS,timestamp
from publish_geographic_workbooks import atomic_write

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data/nine_issuer_dual_audit.json'
ARTIFACTS=ROOT/'dual-audit'
METRICS=('insurance_revenue','insurance_service_result','combined_ratio','loss_ratio','expense_ratio',
         'insurance_revenue_growth','return_on_equity','solvency_ratio','profit_before_tax')
INDEXES={
 'Fremtind':['https://www.fremtind.no/finansiell-informasjon'],
 'Gjensidige':['https://www.gjensidige.com/investor-relations/reports-and-presentations','https://www.gjensidige.com/no/investorinformasjon/rapporter-og-presentasjoner','https://www.gjensidige.com/investor-relations/','https://www.gjensidige.com/press/stock-exchange-disclosures'],
 'Tryg':['https://tryg.com/en/downloads-{year}'],
 'Sampo':['https://www.sampo.com/investors/quarterly-reporting/','https://www.sampo.com/result','https://www.sampo.com/investors/financial-information/quarterly-reporting/{year}/'],
 'Frende':['https://www.frende.no/om-oss/finansiell-informasjon/frende-holding/'],
 'Protector':['https://investor.protectorforsikring.no/','https://investor.protectorforsikring.no/all-reports','https://investor.protectorforsikring.no/financials','https://investor.protectorforsikring.no/press-releases'],
 'Storebrand':['https://www.storebrand.com/welcome/investor-relations/quarterly-reporting/storebrand-asa/{year}'],
 'KLP Skadeforsikring':['https://www.klp.no/om-klp/finans-og-ir/rapporter-og-presentasjoner'],
 'Alm. Brand':['https://investorrelations.almbrand.dk/English/financials/default.aspx','https://investorrelations.almbrand.dk/Danish/rapporter/default.aspx','https://investorrelations.almbrand.dk/English/news-and-events/default.aspx','https://investorrelations.almbrand.dk/Danish/nyheder-og-events/default.aspx','https://investorrelations.almbrand.dk/news-and-events/default.aspx'],
}
# Q3 2026 issuer release notices checked on the official exchange. The
# dynamic listing also checks subsequent periods; never use a seed as "latest".
RELEASE_SEEDS={('Fremtind',2026,3):684332,('Gjensidige',2026,3):684673,
 ('Protector',2026,3):684546,('Storebrand',2026,3):684457,('Frende',2026,3):684953}
# An exchange delivery host is trusted only for an already verified issuer
# announcement or a previously validated source URL, not arbitrary links.
EXCHANGE_HOSTS={'attachment.news.eu.nasdaq.com','newsweb.oslobors.no','www.newsweb.no','newsweb.no',
                'api3.oslo.oslobors.no','storage.mfn.se','mb.cision.com','kommunikasjon.ntb.no'}
AMOUNTS={'insurance_revenue','insurance_service_result','profit_before_tax'}
# Historical issuer-portal release pages supplement dynamic archive discovery.
# Fetch the issuer page and follow its real links, not guessed PDF addresses.
ISSUER_RELEASE_PAGES={
 ('Alm. Brand',2026,3):('https://investorrelations.almbrand.dk/English/press-release-details/2026/Alm--Brand-AS---Interim-report-for-Q3/default.aspx',),
 ('Gjensidige',2026,3):('https://www.gjensidige.com/news?releaseid=5449048',),
 ('Protector',2026,3):('https://investor.protectorforsikring.no/pressreleases/q3-2026-cr-827-earnings-per-share-nok-102-dividend-nok-500-per-share-mviclalu',)
}
# Previously verified historical source: never describe this as newly
# discovered from an issuer archive. No new exchange lookups by default.
KNOWN_PRESENTATIONS={
 ('Gjensidige',2026,3):('https://mb.cision.com/Public/1122/4414216/8e67f3f3d265f88a.pdf','https://newsweb.oslobors.no/message/684673','Interim presentation Q3 2026.pdf','13a9a984d806db379e5f084f752b9f117235ae1854ca63b153a8efe6ca2ab740')
}
ISSUER_WEB_HOSTS={
 'Gjensidige':{'gjensidige.com','www.gjensidige.com'},
 'Protector':{'investor.protectorforsikring.no','protectorforsikring.no','www.protectorforsikring.no'},
 'Alm. Brand':{'investorrelations.almbrand.dk','almbrand.dk'}
}

def issuer_web_page(company,url):
    p=urlsplit(url)
    return (p.scheme=='https' and p.hostname in ISSUER_WEB_HOSTS.get(company,set())
            and not p.username and not p.password and p.port in (None,443))


def attachment_url(message_id,attachment):
    # The public NewsWeb detail response commonly contains only {id,name}.
    # Construct the documented endpoint using the exact returned identifiers.
    if not re.fullmatch(r'[1-9][0-9]*',str(message_id)) or not isinstance(attachment,dict):
        return ''
    attachment_id=attachment.get('id')
    if isinstance(attachment_id,bool) or not re.fullmatch(r'[1-9][0-9]*',str(attachment_id)):
        return ''
    return 'https://api3.oslo.oslobors.no/v1/newsreader/attachment?'+urlencode({'messageId':int(message_id),'attachmentId':int(attachment_id)})

# Project owner confirmed these issuers do not publish a separate results deck.
# Keep discovering new sources: an actual candidate reactivates the requirement.
REPORT_ONLY_ISSUERS=frozenset({'Fremtind','KLP Skadeforsikring','Frende'})

def presentation_policy(company,documents):
    expected=company not in REPORT_ONLY_ISSUERS
    discovered=any(d.get('document_type')=='results_presentation' for d in documents)
    return {'presentation_required':expected or discovered,
            'presentation_exception':'owner_confirmed_no_separate_results_presentation' if not expected and not discovered else None,
            'presentation_exception_under_review':not expected and discovered}

PRESENTATION=re.compile(r'\b(?:presentation|presentasjon|præsentation|slides|analyst presentation)\b',re.I)
EXCLUDE=re.compile(r'pre[- ]?close|pre[- ]?silent|invitation|transcript|roadshow|capital.market|bond|supplement|sustainability|factbook|newsletter|consensus|estimate|company.presentation',re.I)
ENTITY={
 'Fremtind':r'Fremtind\s+Holding',
 'Gjensidige':r'\bGjensidige\b',
 'Tryg':r'\bTryg\b',
 'Sampo':r'\bSampo\b',
 'Frende':r'Frende\s+Holding',
 'Protector':r'\bProtector\b',
 'Storebrand':r'\bStorebrand\b',
 'KLP Skadeforsikring':r'\bKLP\s+Skadeforsikring\b',
 'Alm. Brand':r'\bAlm\.?\s+Brand\b',
}
def normalize(text):
    return ' '.join(text.replace('\u00a0',' ').translate(str.maketrans('‐‑‒–—−','------')).split())

def period_label(text,y,q):
    t=normalize(unquote(text)).replace('_',' ')
    # The period needs to be printed as a unit, not merely separate year
    # and quarter numbers somewhere in a long document.
    month=('March','June','September','December')[q-1]
    word=('first','second','third','fourth')[q-1]
    return bool(re.search(rf'(?<!\w)(?:Q(?:1\s*-\s*Q)?\s*{q}[\s/-]*{y}|{y}[\s/-]*Q\s*{q}|{q}\s*Q[\s/-]*{y}|{q}\.?\s*(?:kvartal|quarter)\s*{y}|{word}\s+quarter\s+{y}|(?:January|Jan)\s*[-/]\s*{month}\s+{y})(?!\w)',t,re.I)
        or (q==4 and re.search(rf'\b(?:full.year|financial.statement.release|annual.report|årsrapport)\s*{y}\b',t,re.I)))

def trusted(company,url,*,exchange=False):
    p=urlsplit(url)
    if p.scheme!='https' or not p.hostname or p.username or p.password or p.port not in (None,443):return False
    if p.hostname=='s29.q4cdn.com':
        return company=='Alm. Brand' and p.path.startswith('/228553818/files/')
    return p.hostname in DELIVERY[company] or (exchange and p.hostname in EXCHANGE_HOSTS)

class Redirect(HTTPRedirectHandler):
    def __init__(self,company,exchange):self.company=company;self.exchange=exchange
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        if not trusted(self.company,newurl,exchange=self.exchange):raise ValueError('Unapproved redirect')
        return super().redirect_request(req,fp,code,msg,headers,newurl)

def fetch(company,url,*,exchange=False,limit=35_000_000):
    if not trusted(company,url,exchange=exchange):raise ValueError('Untrusted issuer source')
    request=Request(url,headers={'User-Agent':'Mozilla/5.0 Forsikringsbarometeret/1.0'})
    with build_opener(Redirect(company,exchange)).open(request,timeout=30) as response:
        if not trusted(company,response.geturl(),exchange=exchange):raise ValueError('Untrusted final source')
        raw=response.read(limit+1)
        final=response.geturl()
    if len(raw)>limit:raise ValueError('Source exceeds size limit')
    return raw,final

class Anchors(HTMLParser):
    def __init__(self):
        super().__init__();self.links=[];self.current=None;self.heading=None;self.context=''
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        if re.fullmatch(r'h[1-6]',tag):self.heading=[]
        if tag=='a':self.current={'href':attrs.get('href',''),'parts':[attrs.get('title',''),attrs.get('aria-label','')],'heading':self.context}
    def handle_data(self,text):
        if self.heading is not None:self.heading.append(text)
        if self.current is not None:self.current['parts'].append(text)
    def handle_endtag(self,tag):
        if re.fullmatch(r'h[1-6]',tag) and self.heading is not None:
            self.context=normalize(' '.join(self.heading));self.heading=None
        if tag=='a' and self.current is not None:
            self.links.append((self.current['href'],normalize(' '.join(self.current['parts'])),self.current['heading']))
            self.current=None

class IssuerQuarterTable(HTMLParser):
    """Preserve actual header, row and link cells from the group archive."""
    def __init__(self):
        super().__init__();self.heading=None;self.group_heading='';self.table=None
        self.row=None;self.cell=None;self.tables=[];self.depth=0
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        if re.fullmatch(r'h[1-6]',tag):self.heading=[]
        if tag=='table':
            self.depth+=1
            if self.depth==1:self.table={'heading':self.group_heading,'rows':[]}
        if self.depth!=1:return
        if tag=='tr':self.row=[]
        if tag in ('td','th') and self.row is not None:
            self.cell={'parts':[],'links':[],'span':attrs.get('colspan','1')}
        if tag=='a' and self.cell is not None:
            self.cell['links'].append(attrs.get('href',''))
    def handle_data(self,data):
        if self.heading is not None:self.heading.append(data)
        if self.cell is not None:self.cell['parts'].append(data)
    def handle_endtag(self,tag):
        if re.fullmatch(r'h[1-6]',tag) and self.heading is not None:
            text=normalize(' '.join(self.heading))
            if re.search(r'20\d{2}.*Gjensidige',text,re.I):self.group_heading=text
            self.heading=None
        if self.depth==1:
            if tag in ('td','th') and self.cell is not None and self.row is not None:
                self.row.append(self.cell);self.cell=None
            if tag=='tr' and self.row is not None and self.table is not None:
                self.table['rows'].append(self.row);self.row=None
            if tag=='table' and self.table is not None:
                self.tables.append(self.table);self.table=None
        if tag=='table':self.depth=max(0,self.depth-1)

def gjensidige_quarter_table(markup,index,y,q):
    if not issuer_web_page('Gjensidige',index):return []
    parser=IssuerQuarterTable();parser.feed(markup);out=[]
    for table in parser.tables:
        heading=table['heading']
        if not re.search(rf'\b{y}\b.*Gjensidige\s+Forsikring\s+(?:Group|Konsern)\b',heading,re.I):continue
        if re.search(r'pensjon',heading,re.I):continue
        rows=table['rows']
        for i,row in enumerate(rows):
            labels=[normalize(' '.join(c['parts'])) for c in row]
            if any(c['span']!='1' for c in row):continue
            if not all(labels.count(f'Q{k}')==1 for k in range(1,5)):continue
            column=labels.index(f'Q{q}')
            for rr in rows[i+1:]:
                if len(rr)!=len(row) or any(c['span']!='1' for c in rr):continue
                label=normalize(' '.join(rr[0]['parts']))
                if label.casefold() not in ('presentation','presentasjon'):continue
                links=[urljoin(index,u) for u in rr[column]['links'] if u]
                links=[u for u in links if trusted('Gjensidige',u) and urlsplit(u).path.lower().endswith('.pdf')]
                if len(set(links))==1:
                    out.append(dict(url=links[0],document_type='results_presentation',origin=index,
                        label=f'{heading}: Q{q} {label}',exchange=False,origin_kind='issuer_quarter_table'))
    return list({x['url']:x for x in out}.values())

def issuer_detail_links(company,markup,index,y,q):
    if not issuer_web_page(company,index):return []
    parser=Anchors();parser.feed(markup);out=[]
    for href,label,_ in parser.links:
        url=urljoin(index,html.unescape(href))
        if not issuer_web_page(company,url):continue
        p=urlsplit(url)
        if company=='Protector':
            if not p.path.startswith('/pressreleases/'):continue
        elif company=='Gjensidige':
            if p.path!='/news' or not re.fullmatch(r'releaseid=\d+',p.query):continue
        elif company=='Alm. Brand':
            # News list labels can omit the year; the issuer URL carries it.
            # Require the period-specific results announcement path, not a
            # consensus, invitation, outlook or generic portal link.
            if not re.fullmatch(r'/(?:English/press-release-details|Danish/selskabsmeddelelse)/'+str(y)+r'/[^/]+/default\.aspx',p.path,re.I):continue
            descriptor=normalize(label+' '+unquote(p.path).replace('-',' '))
            if EXCLUDE.search(descriptor) or ALM_EXCLUDE.search(descriptor) and not re.search(r'interim report|delårsrapport|annual report|årsrapport',descriptor,re.I):continue
            title=normalize(label+' '+unquote(p.path.rsplit('/',2)[-2]).replace('-',' '))
            if not re.search(r'\b(?:interim report|delårsrapport|quarterly report|annual report|årsrapport|full year results)\b',title,re.I):continue
            if not (period_label(title,y,q) or re.search(rf'\b(?:Q\s*{q}|{q}\.\s*kvartal)\b',title,re.I) or (q==4 and re.search(r'\b(?:annual report|årsrapport|full year results)\b',title,re.I))):continue
            # An explicit different year/quarter in the label is a conflict.
            if any(int(v)!=y for v in re.findall(r'\b20\d{2}\b',label)):continue
            if any(int(v)!=q for v in re.findall(r'\bQ\s*([1-4])\b',title,re.I)):continue
            out.append(url);continue
        else:continue
        descriptor=normalize(label+' '+unquote(p.path).replace('-',' '))
        if period_label(descriptor,y,q) and not EXCLUDE.search(descriptor):out.append(url)
    return list(dict.fromkeys(out))[:8]

def rendered_issuer_html(company,url,y,q):
    """Read dynamically rendered issuer tables only when static HTML is insufficient."""
    if not issuer_web_page(company,url):raise ValueError('Non-issuer browser URL')
    from playwright.sync_api import sync_playwright,TimeoutError as PlaywrightTimeout
    with sync_playwright() as pw:
        browser=pw.chromium.launch(channel='chrome',headless=True,args=['--no-sandbox'])
        try:
            page=browser.new_page()
            feed_responses=[]
            feed_docs=[]
            feed_diagnostics=[]
            page_errors=[]
            if company=='Alm. Brand':
                def track_response(response):
                    if (response.request.resource_type in ('xhr','fetch')
                            and alm_public_feed(response.url)):
                        feed_responses.append(response)
                page.on('response',track_response)
                page.on('pageerror',lambda exc:page_errors.append(type(exc).__name__))
            page.goto(url,wait_until='domcontentloaded',timeout=30000)
            try:
                if company=='Gjensidige':
                    page.wait_for_selector('table a[href], a[href*="releaseid="]',timeout=12000)
                elif company=='Alm. Brand':
                    # The Q4 investor portal inserts document links asynchronously.
                    # Wait for both correctly dated candidates, not a generic PDF
                    # or a navigation link. Return the actual DOM, never guess URLs.
                    # Q4 pages may use a year selector and deliver PDFs in a
                    # JSON response rather than as directly visible anchors.
                    # Only select a year explicitly present on the page.
                    # Never click a legal disclaimer or alter location.
                    selected=set()
                    for i in range(36):
                        if not issuer_web_page(company,page.url):
                            raise ValueError('Browser left issuer website')
                        if i in (4,12,20):
                            for select in page.locator('select').all()[:12]:
                                try:
                                    if not select.is_visible():continue
                                    options=select.locator('option').all_text_contents()
                                    if str(y) in [v.strip() for v in options]:
                                        key=select.get_attribute('id') or str(options)
                                        if key not in selected:
                                            select.select_option(label=str(y),timeout=2500)
                                            selected.add(key)
                                except PlaywrightTimeout:pass
                        kinds={d['document_type'] for d in alm_archive_documents(page.content(),page.url,y,q)}
                        if kinds=={'quarterly_report','results_presentation'}:break
                        page.wait_for_timeout(500)
                    for response in feed_responses[:80]:
                        item={'endpoint':urlsplit(response.url).path,'status':response.status}
                        try:
                            if response.status==200 and 'json' in response.headers.get('content-type','').lower():
                                raw=response.body()
                                if len(raw)<=5_000_000:
                                    data=json.loads(raw)
                                    discovered=alm_feed_documents(data,response.url,page.url,y,q)
                                    feed_docs.extend(discovered)
                                    item['candidate_count']=len(discovered)
                        except Exception as exc:
                            item['error']=type(exc).__name__
                        feed_diagnostics.append(item)
                    # Preserve enough evidence to debug missing links without
                    # storing cookies, query-string API keys or raw responses.
                    parser=Anchors();parser.feed(page.content())
                    pdf_links=[]
                    for href,label,heading in parser.links:
                        target=urljoin(page.url,href)
                        if trusted('Alm. Brand',target) and urlsplit(target).path.lower().endswith('.pdf'):
                            pdf_links.append({'path':urlsplit(target).path,'label':label[:180],'heading':heading[:180]})
                    folder=ARTIFACTS/'Alm-Brand'/f'Q{q}-{y}'
                    folder.mkdir(parents=True,exist_ok=True)
                    suffix=('danish' if '/Danish/' in url else 'english')+'-'+hashlib.sha256(url.encode()).hexdigest()[:8]
                    (folder/f'portal-{suffix}.json').write_text(json.dumps({
                        'page':urlsplit(page.url).path,'title':page.title(),
                        'feed_responses':feed_diagnostics,'pdf_links':pdf_links[:100],
                        'page_error_types':page_errors[:30],
                        'headings':page.locator('h1,h2,h3,h4').all_text_contents()[:40],
                        'selected_year_widgets':len(selected)},ensure_ascii=False,indent=2),encoding='utf-8')
                    print('ALM_PORTAL_FEEDS',json.dumps({'page':urlsplit(page.url).path,
                        'feed_responses':feed_diagnostics,'pdf_link_count':len(pdf_links),
                        'page_errors':len(page_errors)},ensure_ascii=False),flush=True)
                else:
                    page.wait_for_selector('a[href*="/pressreleases/"], a[href*="storage.mfn.se"]',timeout=12000)
            except PlaywrightTimeout:pass
            if not issuer_web_page(company,page.url):raise ValueError('Browser left issuer website')
            return page.content(),page.url,feed_docs
        finally:browser.close()

def alm_public_feed(url):
    """Only actual financial document feeds requested by the issuer page."""
    if not issuer_web_page('Alm. Brand',url):return False
    path=urlsplit(url).path
    return bool(re.match(r'^/(?:feed|Services)/',path,re.I) and
        re.search(r'(?:FinancialReport|Presentation|Event|ContentAsset)(?:Service)?\.svc/',path,re.I))

def alm_feed_documents(data,response_url,index,y,q):
    """Extract explicit document URLs from a same-issuer public JSON response.

    Never combine a title from one record with a URL from another record.
    Never infer a URL from a naming convention or from an imported value.
    """
    if not alm_public_feed(response_url) or not issuer_web_page('Alm. Brand',index):return []
    found={}
    def walk(value,depth=0):
        if depth>20:return
        if isinstance(value,str):
            if value.lstrip().startswith(('{','[')):
                try:walk(json.loads(value),depth+1)
                except (ValueError,TypeError):pass
            return
        if isinstance(value,list):
            for row in value:walk(row,depth+1)
            return
        if not isinstance(value,dict):return
        labels=[v for k,v in value.items() if isinstance(v,str) and
            re.fullmatch(r'(?:title|name|label|linktext|filename|documenttitle|reporttitle|presentationtitle|documenttype|reporttype|reportsubtype|presentationtype)',str(k),re.I)
            and len(v)<300]
        for key,href in value.items():
            if isinstance(href,str) and len(href)<2000:
                target=urljoin(index,href)
                if trusted('Alm. Brand',target) and urlsplit(target).path.lower().endswith('.pdf'):
                    # Explicit filename is sufficient; only if it is generic
                    # try labels from this exact document record.
                    anchor=lambda label:f'<a href="{html.escape(target,quote=True)}">{html.escape(label)}</a>'
                    candidates=alm_archive_documents(anchor(''),index,y,q)
                    if not candidates:
                        candidates=alm_archive_documents(anchor(' '.join(labels)),index,y,q)
                    for d in candidates:
                        d.update(origin_kind='issuer_public_document_feed',feed_endpoint=urlsplit(response_url).path)
                        found[(d['document_type'],d['url'])]=d
            elif isinstance(href,(list,dict)):
                walk(href,depth+1)
            if isinstance(href,str) and href.lstrip().startswith(('{','[')):
                walk(href,depth+1)
    walk(data)
    return list(found.values())

ALM_REPORT=re.compile(r'\b(?:AB\s+GROUP|interim\s+report|quarterly\s+report|delårsrapport|kvartalsrapport|annual\s+report|årsrapport)\b',re.I)
ALM_EXCLUDE=re.compile(r'\b(?:preliminary|preliminær|announcement|selskabsmeddelelse|press\s+release|webcast|key\s+figures|nøgletal|SFCR|solvency|parent\s+company|roadshow|seminar|conference|capital\s+markets?\s+day|investor\s+meeting|consensus|sustainability)\b',re.I)

def alm_archive_documents(markup,index,y,q):
    """Accept actual issuer-linked PDFs with explicit document type and period."""
    if not issuer_web_page('Alm. Brand',index):return []
    parser=Anchors();parser.feed(markup);found={}
    for href,label,heading in parser.links:
        if not href:continue
        url=urljoin(index,html.unescape(href))
        path=urlsplit(url).path
        # Nasdaq serves issuer-disclosed PDFs through extensionless attachment
        # IDs. Accept such a link only from a verified issuer results page and
        # only with an explicit full-report label and period. Verification still
        # downloads the bytes and runs the issuer's full-report parser.
        official_attachment=(urlsplit(url).hostname=='attachment.news.eu.nasdaq.com' and bool(re.fullmatch(r'/[0-9a-f]{32}',path)) and bool(re.search(r'/(?:press-release-details|selskabsmeddelelse)/'+str(y)+r'/',urlsplit(index).path,re.I)))
        if not trusted('Alm. Brand',url,exchange=official_attachment) or not (path.lower().endswith('.pdf') or official_attachment):continue
        if official_attachment and not (re.search(r'\bAB\s+GROUP\b',label,re.I) and period_label(label,y,q)):continue
        name=normalize(unquote(path.rsplit('/',1)[-1]).replace('_',' ').replace('-',' '))
        descriptor=normalize(label+' '+name)
        if EXCLUDE.search(descriptor) or ALM_EXCLUDE.search(descriptor):continue
        is_presentation=bool(PRESENTATION.search(descriptor))
        is_report=bool(ALM_REPORT.search(descriptor) or re.fullmatch(r'(?:Report|Rapport)(?:\s*\(opens in new window\))?',label,re.I))
        if is_presentation==is_report:continue
        # Do not let a current heading turn an explicitly older filename into
        # a current document. A generic link needs a dated enclosing heading.
        has_period=bool(re.search(r'\b(?:Q\s*[1-4]|[1-4]\s*Q|[1-4]\.?\s*(?:quarter|kvartal))[\s/-]*20\d{2}\b|\b20\d{2}[\s/-]*Q\s*[1-4]\b',descriptor,re.I))
        explicit=period_label(descriptor,y,q)
        if not explicit and (has_period or not period_label(heading,y,q)):continue
        if not explicit and re.search(r'\b20\d{2}\b',descriptor) and str(y) not in descriptor:continue
        if is_report and q!=4 and re.search(r'\b(?:annual\s+report|årsrapport)\b',descriptor,re.I):continue
        kind='results_presentation' if is_presentation else 'quarterly_report'
        found[(kind,url)]=dict(url=url,document_type=kind,origin=index,label=label or name,
                              exchange=official_attachment,origin_kind='issuer_archive_or_release')
    return list(found.values())

def archive_links(company,markup,index,y,q):
    if company=='Alm. Brand':return alm_archive_documents(markup,index,y,q)
    parser=Anchors();parser.feed(markup);results=gjensidige_quarter_table(markup,index,y,q) if company=='Gjensidige' else []
    for href,label,heading in parser.links:
        url=urljoin(index,html.unescape(href))
        if not trusted(company,url):continue
        path=urlsplit(url).path
        # ONLY the last component, never the archive's parent directories.
        name=unquote(path.rsplit('/',1)[-1]).replace('_',' ').replace('-',' ')
        descriptor=normalize(label+' '+name)
        if not PRESENTATION.search(descriptor) or EXCLUDE.search(descriptor):continue
        if not path.lower().endswith('.pdf'):continue
        explicit=period_label(descriptor,y,q)
        # Storebrand labels links merely "Analyst presentation", nested
        # beneath a quarter heading on an explicitly year-specific page.
        if company=='Storebrand' and not explicit and index.rstrip('/').endswith('/'+str(y)):
            explicit=bool(re.search(rf'\b{q}(?:st|nd|rd|th)?\.?\s*(?:quarter|kvartal)\b',heading,re.I))
        if not explicit:continue
        if company=='KLP Skadeforsikring' and not re.search(r'skadeforsikring',descriptor,re.I):continue
        if company=='Fremtind' and not re.search(r'holding',descriptor,re.I):continue
        if company=='Frende' and not re.search(r'holding',descriptor,re.I):continue
        results.append(dict(url=url,document_type='results_presentation',origin=index,label=label or name,exchange=False,origin_kind='issuer_archive_or_release'))
    # Some archives encode labelled PDF assets in JSON. A filename alone is
    # accepted only when both presentation type and period are explicit and
    # the exact HTTPS asset occurs in the issuer's returned markup.
    if company in ('Sampo','Alm. Brand','Gjensidige'):
        for href in re.findall(r'(?:https?://[^"\'<>\s\\]+|/globalassets/[^"\'<>\s\\]+)\.pdf(?:\?[^"\'<>\s\\]*)?',markup.replace('\\/','/'),re.I):
            url=urljoin(index,html.unescape(href));name=unquote(urlsplit(url).path.rsplit('/',1)[-1]).replace('_',' ').replace('-',' ')
            if trusted(company,url) and PRESENTATION.search(name) and not EXCLUDE.search(name) and period_label(name,y,q):
                results.append(dict(url=url,document_type='results_presentation',origin=index,label=name,exchange=False,origin_kind='issuer_archive_or_release'))
    return list({x['url']:x for x in results}.values())

def exchange_links(company,y,q,client):
    if company not in ISSUERS:return [],[]
    identity=client.identity(company)
    # Use the filing window following quarter end, bounded by today's date.
    import calendar
    end=date(y,q*3,calendar.monthrange(y,q*3)[1])
    from datetime import timedelta
    start=end+timedelta(days=1);stop=min(date.today(),end+timedelta(days=120))
    ids=set()
    if start<=stop:
        for row in client.listing(identity,start,stop):
            title=str(row.get('title',''))
            if period_label(title,y,q) or re.search(rf'\b{q}\.\s*kvartal\b',title,re.I) and str(y) in title:
                if not EXCLUDE.search(title):ids.add(int(row['messageId']))
    seed=RELEASE_SEEDS.get((company,y,q))
    if seed:ids.add(seed)
    found=[];notes=[]
    for mid in sorted(ids)[:12]:
        message=client.message(mid)
        if (int(message['issuerId']),message['issuerSign'])!=(identity['issuer_id'],identity['issuer_sign']):raise ValueError('Wrong exchange issuer')
        if not start<=timestamp(message['publishedTime']).date()<=stop:continue
        title=str(message.get('title',''))
        if EXCLUDE.search(title):continue
        # Actual attachment names/URLs must be present in the verified
        # announcement response. Unknown schemas are reported, not guessed.
        attachments=message.get('attachments') or message.get('attachmentList') or []
        if isinstance(attachments,dict):attachments=attachments.get('attachments',[])
        if not isinstance(attachments,list):raise ValueError('Unknown exchange attachment schema')
        origin='https://newsweb.oslobors.no/message/'+str(mid)
        notes.append({'announcement':origin,'title':title,'attachment_count':len(attachments),
            'attachment_fields':sorted({k for a in attachments if isinstance(a,dict) for k in a})})
        for a in attachments:
            if not isinstance(a,dict):continue
            label=next((a[k] for k in ('fileName','filename','attachmentName','name','title','description') if isinstance(a.get(k),str)), '')
            href=next((a[k] for k in ('url','attachmentUrl','downloadUrl','fileUrl','href') if isinstance(a.get(k),str)), '')
            if not href:href=attachment_url(mid,a)
            if not href or not label or not trusted(company,href,exchange=True):continue
            if not period_label(label,y,q) and not period_label(title,y,q):continue
            if PRESENTATION.search(label) and not EXCLUDE.search(label):
                found.append(dict(url=href,document_type='results_presentation',origin=origin,label=label,exchange=True))
            elif company=='Frende' and re.search(r'frende\s+holding',label,re.I) and label.lower().endswith('.pdf'):
                found.append(dict(url=href,document_type='quarterly_report',origin=origin,label=label,exchange=True))
    return list({x['url']:x for x in found}.values()),notes

def report_sources(feed,extended,company,y,q):
    docs={}
    def add(url,sha,kind='quarterly_report',pages=(),fmt='pdf'):
        if not url or not re.fullmatch(r'[0-9a-f]{64}',str(sha or '')):return
        x=docs.setdefault((url,kind),dict(url=url,document_type=kind,origin='verified_feed',label='',exchange=True,expected_sha256=[],source_pages=[],format=fmt))
        if sha not in x['expected_sha256']:x['expected_sha256'].append(sha)
        x['source_pages']=sorted(set(x['source_pages'])|{p for p in pages if type(p) is int and p>0})
    for row in feed.get('observations',[]):
        if row.get('company')!=company or row.get('scope')!='group' or (row.get('year'),row.get('quarter'))!=(y,q):continue
        if row.get('metric') not in METRICS or row.get('status') not in ('reported','calculated'):continue
        url=row.get('source_url','')
        add(url,row.get('source_sha256'),pages=[row.get('source_page')],fmt='html' if urlsplit(url).hostname=='frende.wrep.it' else 'pdf')
    item=extended.get('insurers',{}).get(company,{})
    if (item.get('year'),item.get('quarter'))==(y,q):
        if item.get('quarter_calculation'):
            for doc in item.get('source_documents',[]):
                # Different periods: the Q3 supporting report does not become
                # a Q4 report, and Q4 annual flow extraction has a separate gate.
                if (doc.get('year'),doc.get('quarter'))==(y,q):
                    add(doc.get('source_url'),doc.get('source_sha256'),pages=doc.get('source_pages',[]))
        else:
            ev=item.get('ytd_pdf_evidence') or item
            page_map=ev.get('source_pages',{})
            pp=[]
            for v in page_map.values():
                pp.extend(v if isinstance(v,list) else [v])
            add(ev.get('source_url'),ev.get('source_sha256'),pages=pp)
        ev=item.get('presentation_evidence',{})
        add(ev.get('source_url'),ev.get('source_sha256'),'results_presentation',[ev.get('source_page')])
    return list(docs.values())

def verify_pdf_identity(company,texts,y,q,kind):
    head=normalize(' '.join(texts[:6] if company=='Gjensidige' else texts[:3]))
    issuer_confirmed=bool(re.search(ENTITY[company],head,re.I))
    # Protector uses a graphical logo on its cover; the last-page legal
    # attribution explicitly identifies the issuer of the presentation.
    if company=='Protector' and kind=='results_presentation' and not issuer_confirmed:
        attribution=normalize(' '.join(texts[-2:]))
        issuer_confirmed=bool(re.search(r'Investor Presentation',head,re.I)
            and re.search(r'prepared by and is the sole responsibility of Protector Forsikring ASA',attribution,re.I)
            and period_label(normalize(texts[0]),y,q))
    if not issuer_confirmed:raise ValueError('Issuer/entity not established on opening pages or explicit issuer attribution')
    if not period_label(head,y,q):
        # Explicit cover phrases with the quarter number separated from year
        # are allowed only on the cover itself and require a current-period title.
        cover=normalize(texts[0])
        word=('first','second','third','fourth')[q-1]
        gjensidige_period=(company=='Gjensidige' and kind=='quarterly_report' and str(y) in head
                           and re.search(rf'\b(?:{word} quarter|Q\s*{q})\b',head,re.I))
        if not gjensidige_period and not (str(y) in cover and re.search(rf'\bQ\s*{q}\b',cover,re.I)):raise ValueError('Cover period not established')
    if kind=='results_presentation' and not re.search(r'presentation|presentasjon|præsentation|quarterly results|interim results|financial results|quarter results|results|Q[1-4]',head,re.I):
        raise ValueError('Presentation document identity not established')
    if company=='KLP Skadeforsikring' and not re.search(r'KLP\s+Skadeforsikring',normalize(texts[0]),re.I):
        raise ValueError('KLP parent or other entity is not the Skadeforsikring report')
    return True

def verify_document(company,doc,y,q,feed=None):
    url=doc['url'];kind=doc['document_type']
    if doc.get('format')=='html':
        from import_frende_holding import read,extract,extract_revenue,extract_insurance_result
        from import_reported_profit_before_tax import parse_frende
        if company!='Frende':raise ValueError('Unexpected HTML report')
        m=re.fullmatch(r'https://frende\.wrep\.it/(q[1-4]-20\d{2}-frende-holding-as)/sec/([67])',url)
        if not m or m.group(1)!=f'q{q}-{y}-frende-holding-as':raise ValueError('Wrong Frende report section')
        section=int(m.group(2));markup=read(url.rsplit('/sec/',1)[0],section)
        raw=markup.encode('utf-8')
        anchor=next((r for r in (feed or {}).get('observations',[]) if r.get('company')==company and r.get('year')==y and r.get('quarter')==q and r.get('source_url')==url and r.get('metric')=='profit_before_tax'),None)
        parsed=extract(markup,url,y,q)+parse_frende(markup,anchor) if section==6 else extract_revenue(markup,url,y,q)+extract_insurance_result(markup,url,y,q)
        texts=[f'Frende Holding Q{q} {y} section {section}: verified table; {len(parsed)} observations']
        fmt='html'
        final=url
    else:
        raw,final=fetch(company,url,exchange=doc.get('exchange',False))
        if not raw.startswith(b'%PDF-'):raise ValueError('Not PDF bytes')
        import pdfplumber
        with pdfplumber.open(io.BytesIO(raw)) as pdf:
            if not 1<=len(pdf.pages)<=300:raise ValueError('Invalid PDF page count')
            texts=[p.extract_text() or '' for p in pdf.pages]
        # The issuer logo is graphical on Alm. Brand's presentation cover.
        # Only a fingerprint-pinned issuer-linked document may use this exception;
        # the independent solvency parser below still has to verify its table.
        pinned_alm=(company=='Alm. Brand' and kind=='results_presentation' and doc.get('expected_sha256')==[hashlib.sha256(raw).hexdigest()] and urlsplit(url).hostname=='s29.q4cdn.com' and period_label(url,y,q))
        if not pinned_alm:verify_pdf_identity(company,texts,y,q,kind)
        if company=='Alm. Brand' and kind=='quarterly_report' and doc.get('origin_kind','').startswith('issuer_'):
            # Reject a results announcement masquerading as the full report.
            # Reuse the existing issuer's report parser and financial gates.
            from rolling_alm_brand_reports import read_report,verify_report
            report_texts,regions=read_report(raw)
            verify_report(report_texts,final,raw,y,q,regions)
        fmt='pdf'
    digest=hashlib.sha256(raw).hexdigest()
    expected=doc.get('expected_sha256',[])
    semantic_matches=[]
    if expected and set(expected)!={digest}:
        if fmt!='html':raise ValueError('Current source fingerprint differs from imported provenance')
        old=[r for r in (feed or {}).get('observations',[]) if r.get('company')==company and r.get('year')==y and r.get('quarter')==q and r.get('scope')=='group' and r.get('source_url')==url and r.get('metric') in METRICS]
        for r in old:
            rr=[p for p in parsed if (p.get('year'),p.get('quarter'),p.get('scope'),p.get('period_type'),p.get('metric'),p.get('unit'))==(y,q,'group',r['period_type'],r['metric'],r['unit'])]
            if len(rr)!=1 or rr[0]['value']!=r['value']:raise ValueError('Changed HTML and financial table differs or is ambiguous: '+r['metric'])
            semantic_matches.append({'metric':r['metric'],'period_type':r['period_type'],'value':r['value'],'prior_sha256':r['source_sha256']})
        if not old:raise ValueError('Changed HTML without original observations')
    if fmt=='pdf' and any(p>len(texts) for p in doc.get('source_pages',[])):raise ValueError('Imported source page outside document')
    result=dict(url=final,requested_url=url,document_type=kind,origin=doc['origin'],feed_endpoint=doc.get('feed_endpoint'),origin_kind=doc.get('origin_kind','previously_verified_source' if doc.get('expected_sha256') else 'exchange_reserve'),label=doc.get('label',''),
        format=fmt,source_sha256=digest,issuer_verified=True,period_verified=True,
        expected_fingerprint_matches=bool(expected) and set(expected)=={digest},semantic_matches=semantic_matches,
        fingerprint_status='changed_html_values_reparsed_and_matched' if semantic_matches else 'exact_match' if expected else 'new_source',source_pages_examined=len(texts),status='verified_document')
    return result,raw,texts

def collect_company(company,y,q,feed,extended):
    docs=report_sources(feed,extended,company,y,q);indexes=[];errors=[];news=[]
    detail_urls=[]
    checked=set()
    def discover_index(template,render=False):
        url=template.format(year=y)
        if url in checked and not render:return [],[]
        if not render:checked.add(url)
        try:
            feed_docs=[]
            if render:
                markup,final,feed_docs=rendered_issuer_html(company,url,y,q)
            else:
                raw,final=fetch(company,url,limit=5_000_000)
                markup=raw.decode('utf-8','replace')
            found=archive_links(company,markup,final,y,q)
            found=list({(d['document_type'],d['url']):d for d in [*feed_docs,*found]}.values())
            details=issuer_detail_links(company,markup,final,y,q)
            indexes.append(dict(url=final,status='checked',method='rendered_issuer_page' if render else 'issuer_html',
                                presentation_candidates=sum(d['document_type']=='results_presentation' for d in found),
                                report_candidates=sum(d['document_type']=='quarterly_report' for d in found),release_candidates=len(details)))
            return found,details
        except Exception as exc:
            indexes.append(dict(url=url,status='unavailable',method='rendered_issuer_page' if render else 'issuer_html',error=str(exc)[:240]))
            return [],[]
    for template in INDEXES[company]:
        found,details=discover_index(template);docs.extend(found);detail_urls.extend(details)
    release_pages=list(dict.fromkeys([*detail_urls,*ISSUER_RELEASE_PAGES.get((company,y,q),())]))
    for url in release_pages:
        found,_=discover_index(url);docs.extend(found)
    def primary_candidate(kind='results_presentation'):
        return any(d['document_type']==kind and d.get('origin_kind','').startswith('issuer_') for d in docs)
    def needs_render():
        if company=='Alm. Brand':
            return not (primary_candidate('quarterly_report') and primary_candidate())
        return not primary_candidate()
    # Do not fall back to a stock exchange just because the issuer page
    # needs JavaScript. Only render the missing company's relevant index.
    if company in ('Gjensidige','Protector','Alm. Brand') and needs_render():
        templates=INDEXES[company][:2] if company in ('Gjensidige','Alm. Brand') else [INDEXES[company][-1]]
        for template in templates:
            found,details=discover_index(template,render=True);docs.extend(found)
            for url in details:
                found,_=discover_index(url);docs.extend(found)
            if not needs_render():break
        # Result announcements can themselves load attachments asynchronously.
        if company=='Alm. Brand' and needs_render():
            for url in release_pages[:3]:
                found,_=discover_index(url,render=True);docs.extend(found)
                if not needs_render():break
    # A stock-exchange attachment may be used only in an expressly enabled
    # diagnostic fallback; normal report/presentation discovery is issuer-only.
    if not primary_candidate() and os.environ.get('BAROMETER_ALLOW_EXCHANGE_DOCUMENT_FALLBACK')=='1':
        try:
            found,news=exchange_links(company,y,q,Client())
            docs.extend(dict(d,origin_kind='exchange_reserve') for d in found)
        except Exception as exc:errors.append('Exchange reserve discovery: '+str(exc)[:300])
    # Keep the verified historical document for auditing existing data, but
    # expose it as historical rather than issuer-website discovery.
    known=KNOWN_PRESENTATIONS.get((company,y,q))
    if known and not primary_candidate():
        url,origin,label,digest=known
        docs.append(dict(url=url,document_type='results_presentation',origin=origin,label=label,exchange=True,
                         origin_kind='historical_verified_exchange_attachment',expected_sha256=[digest]))
    unique={}
    for doc in docs:
        key=(doc['document_type'],doc['url'])
        if key not in unique:
            unique[key]=doc;continue
        old=unique[key]
        # Keep a verified fingerprint when the same URL is also rediscovered
        # on the issuer's own website; prefer the fresh issuer origin.
        preferred=doc if doc.get('origin_kind','').startswith('issuer_') else old
        unique[key]={**old,**preferred,'expected_sha256':list(dict.fromkeys(old.get('expected_sha256',[])+doc.get('expected_sha256',[]))),
                     'source_pages':sorted(set(old.get('source_pages',[])+doc.get('source_pages',[])))}
    verified=[];loaded=[];seen_verified=set()
    for doc in list(unique.values())[:12]:
        try:
            evidence,raw,texts=verify_document(company,doc,y,q,feed)
            verified.append(evidence)
            identity=(evidence['document_type'],evidence['source_sha256'])
            if identity not in seen_verified:
                loaded.append((evidence,raw,texts));seen_verified.add(identity)
            # Actual PDF/text evidence is a CI artifact, not a new web feed.
            folder=ARTIFACTS/re.sub(r'[^A-Za-z0-9]+','-',company).strip('-')/f'Q{q}-{y}'
            folder.mkdir(parents=True,exist_ok=True)
            name=doc['document_type']+'-'+evidence['source_sha256'][:12]
            (folder/(name+'.txt')).write_text('\n\n'.join(f'--- PAGE {i+1} ---\n{t}' for i,t in enumerate(texts)),encoding='utf-8')
            if evidence['format']=='pdf':(folder/(name+'.pdf')).write_bytes(raw)
        except Exception as exc:
            verified.append(dict(url=doc['url'],document_type=doc['document_type'],origin=doc['origin'],status='unverified',error=type(exc).__name__+': '+str(exc)[:300]))
    types={x['document_type'] for x in verified if x['status']=='verified_document'}
    presentation_found='results_presentation' in types
    # Byte identity is not metric reconciliation. Explicitly compare at least
    # Alm. Brand solvency using the two existing independently verified parsers.
    from reconcile_issuer_presentation_metrics import reconcile,storebrand_flow_tables,gjensidige_positioned_metrics
    matches=[]
    report_docs=[e for e,_,_ in loaded if e['document_type']=='quarterly_report']
    verified_feed=feed
    if company=='Alm. Brand':
        from rolling_alm_brand_reports import read_report,verify_report
        extra=[]
        for ev,raw,_ in loaded:
            if ev['document_type']!='quarterly_report' or not ev['expected_fingerprint_matches']:continue
            try:
                texts,regions=read_report(raw);rr=verify_report(texts,ev['url'],raw,y,q,regions)
                for period,values in [('quarter',rr['metrics']),('ytd',rr['ytd_metrics'])]:
                    for k,v in values.items():
                        extra.append(dict(company=company,year=y,quarter=q,scope='group',period_type=period,metric=k,value=v,
                            unit='MDKK' if k in AMOUNTS else 'percent',source_url=ev['requested_url'],source_sha256=ev['source_sha256'],
                            source_page=rr['source_pages'][k],status='reported'))
            except (ValueError,KeyError,TypeError) as exc:errors.append('Alm report metric replay: '+str(exc))
        verified_feed={'observations':feed.get('observations',[])+extra}
    for pe,pr,pt in loaded:
        if pe['document_type']=='results_presentation':
            additional=[]
            if company=='Storebrand':additional=storebrand_flow_tables(pr,y,q)
            elif company=='Gjensidige':additional=gjensidige_positioned_metrics(pr,y,q)
            matches.extend(reconcile(company,y,q,verified_feed,report_docs,pe,pt,additional=additional))
    if company=='Alm. Brand' and types=={'quarterly_report','results_presentation'}:
        from rolling_alm_brand_reports import read_report,verify_report,presentation_evidence
        reports=[(e,r,t) for e,r,t in loaded if e['document_type']=='quarterly_report' and e['expected_fingerprint_matches']]
        presentations=[(e,r,t) for e,r,t in loaded if e['document_type']=='results_presentation']
        if len(reports)==1:
            try:
                ev,raw,_=reports[0];texts,regions=read_report(raw)
                report=verify_report(texts,ev['url'],raw,y,q,regions)
                for pe,pr,pt in presentations:
                    if pe['source_sha256']==ev['source_sha256']:continue
                    try:
                        checked=presentation_evidence(pt,pe['url'],pr,y,q,report['metrics']['solvency_ratio'])
                        for period in ('quarter','ytd'):
                            matches.append({'metric':'solvency_ratio','period_type':period,'scope':'group','unit':'percent',
                                'status':'match','value':checked['metrics']['solvency_ratio'],'method':'independently_reconciled_group_capital_table',
                                'report':{'source_url':ev['url'],'source_sha256':ev['source_sha256'],'source_page':report['source_pages']['solvency_ratio']},
                                'presentation':{'source_url':pe['url'],'source_sha256':pe['source_sha256'],'source_page':checked['source_page']}})
                    except ValueError as exc:errors.append('Alm presentation reconciliation: '+str(exc))
            except ValueError as exc:errors.append('Alm report reconciliation: '+str(exc))
    # Deduplicate the same metric from independent delivery mirrors; retain
    # every distinct disagreement instead of counting duplicates as more KPIs.
    grouped={}
    for m in matches:
        key=(m['metric'],m['period_type'],m['scope'],m['unit'])
        if key not in grouped or (m['status']=='conflict' and grouped[key]['status']!='conflict'):
            grouped[key]=m
    matches=list(grouped.values())
    report_hashes={x['source_sha256'] for x in verified if x['status']=='verified_document' and x['document_type']=='quarterly_report'}
    presentation_hashes={x['source_sha256'] for x in verified if x['status']=='verified_document' and x['document_type']=='results_presentation'}
    both=bool(report_hashes and presentation_hashes-report_hashes)
    status='conflicting_metric_evidence' if any(m['status']=='conflict' for m in matches) else 'partial_metric_reconciliation' if both and matches else 'both_documents_read_metrics_not_certified' if both else 'presentation_not_verified' if not presentation_found else 'report_not_verified'
    issuer_report_verified=any(d['status']=='verified_document' and d['document_type']=='quarterly_report' and d.get('origin_kind','').startswith('issuer_') for d in verified)
    issuer_presentation_verified=any(d['status']=='verified_document' and d['document_type']=='results_presentation' and d.get('origin_kind','').startswith('issuer_') for d in verified)
    policy=presentation_policy(company,verified)
    if policy['presentation_exception']:
        status='report_only_verified' if report_hashes else 'report_only_not_verified'
    return dict(company=company,year=y,quarter=q,report_verified=bool(report_hashes),presentation_verified=presentation_found,
                **policy,issuer_report_verified=issuer_report_verified,issuer_presentation_verified=issuer_presentation_verified,
                both_distinct_documents_verified=both,metric_reconciliation_status=status,
                archives_checked=indexes,exchange_announcements=news,documents=verified,cross_document_matches=matches,errors=errors)

def audit(feed,extended,comparison):
    rows=comparison.get('companies',[])
    selected={r['company']:r.get('period') for r in rows}
    if set(selected)!=set(COMPANIES):raise ValueError('Nine issuer periods required')
    tasks=[]
    for company in COMPANIES:
        m=re.fullmatch(r'Q([1-4]) (20\d{2})',str(selected[company]))
        if not m:raise ValueError('Invalid issuer period '+company)
        q,y=map(int,m.groups());tasks.append((company,y,q))
    with ThreadPoolExecutor(max_workers=4) as pool:
        result=list(pool.map(lambda t:collect_company(*t,feed,extended),tasks))
    for item in result:
        row=next(r for r in rows if r['company']==item['company'])
        matches={(m['metric'],m['period_type']):m['status'] for m in item['cross_document_matches']}
        slots=[]
        for period,values in [('quarter',row.get('metrics',{})),('ytd',row.get('ytd_metrics',{}))]:
            for metric in METRICS:
                if values.get(metric) is None:continue
                basis=row.get('metric_periods',{}).get(metric,period) if period=='quarter' else period
                key=(metric,basis)
                state=matches.get(key)
                if state is None and metric=='solvency_ratio':state=matches.get((metric,'quarter'))
                status=('report_only_verified' if item['report_verified'] else 'report_unverified') if item['presentation_exception'] else ('matched' if state=='match' else 'conflict' if state=='conflict' else 'presentation_metric_not_yet_verified')
                slots.append(dict(metric=metric,view=period,period_basis=basis,status=status))
        item['metric_inventory']=slots
    required=[x for x in result if x['presentation_required']]
    exceptions=[x for x in result if x['presentation_exception']]
    out={'schema_version':2,'purpose':'issuer_document_and_metric_verification',
         'report_verified_count':sum(x['report_verified'] for x in result),
         'issuer_report_verified_count':sum(x['issuer_report_verified'] for x in result),
         'presentation_required_count':len(required),
         'presentation_verified_count':sum(x['presentation_verified'] for x in required),
         'issuer_presentation_verified_count':sum(x['issuer_presentation_verified'] for x in required),
         'report_only_issuers':[x['company'] for x in exceptions],
         'applicable_document_pairs_verified_count':sum(x['both_distinct_documents_verified'] for x in required),
         'all_required_documents_verified':all(x['report_verified'] for x in result) and all(x['both_distinct_documents_verified'] for x in required),
         'all_nine_both_documents_verified':all(x['both_distinct_documents_verified'] for x in result),
         'all_nine_dual_document_verified':False,'financial_observations_modified':False,
         'presentation_metric_slots':sum(len(x['metric_inventory']) for x in required),
         'presentation_metric_slots_matched':sum(m['status']=='matched' for x in required for m in x['metric_inventory']),
         'presentation_metric_slots_unresolved':sum(m['status']=='presentation_metric_not_yet_verified' for x in required for m in x['metric_inventory']),
         'note':'Document verification is separate from independent metric extraction. Owner-confirmed report-only issuers are exempt from presentation requirements, but must pass original-report verification. Discovery continues for every issuer; a new presentation candidate reopens the requirement. Unverified presentation candidates are not reporting exceptions.',
         'companies':result}
    return out

def main():
    load=lambda name:json.loads((ROOT/'data'/name).read_text(encoding='utf-8'))
    report=audit(load('verified_financial_feed.json'),load('extended_insurer_financials.json'),load('nine_insurer_comparison.json'))
    atomic_write(OUT,report)
    for item in report['companies']:
        print('DUAL_ISSUER_AUDIT',json.dumps({k:item[k] for k in ('company','year','quarter','report_verified','presentation_verified','both_distinct_documents_verified','metric_reconciliation_status','issuer_report_verified','issuer_presentation_verified','presentation_required','presentation_exception','presentation_exception_under_review','archives_checked','exchange_announcements','errors')},ensure_ascii=False),flush=True)
        for d in item['documents']:print('DUAL_DOCUMENT',item['company'],json.dumps(d,ensure_ascii=False),flush=True)
        for m in item['cross_document_matches']:print('DUAL_METRIC_MATCH',item['company'],json.dumps(m,ensure_ascii=False),flush=True)
        print('DUAL_METRIC_INVENTORY',item['company'],json.dumps(item['metric_inventory'],ensure_ascii=False),flush=True)
    print('DUAL_DOCUMENT_SUMMARY',json.dumps({'report_verified':sum(x['report_verified'] for x in report['companies']),
        'presentation_verified':sum(x['presentation_verified'] for x in report['companies']),
        'distinct_pairs':sum(x['both_distinct_documents_verified'] for x in report['companies']),
        'presentations_expected':report['presentation_required_count'],
        'issuer_presentations_verified':report['issuer_presentation_verified_count'],
        'issuer_reports_verified':report['issuer_report_verified_count'],
        'report_only_issuers':report['report_only_issuers'],
        'all_required_documents_verified':report['all_required_documents_verified'],
        'metric_matches':sum(m['status']=='match' for x in report['companies'] for m in x['cross_document_matches']),
        'metric_conflicts':sum(m['status']=='conflict' for x in report['companies'] for m in x['cross_document_matches']),
        'presentation_metric_slots':report['presentation_metric_slots'],
        'presentation_metric_slots_matched':report['presentation_metric_slots_matched'],
        'presentation_metric_slots_unresolved':report['presentation_metric_slots_unresolved'],
        'full_reconciliation':report['all_nine_dual_document_verified']},ensure_ascii=False),flush=True)
if __name__=='__main__':main()
