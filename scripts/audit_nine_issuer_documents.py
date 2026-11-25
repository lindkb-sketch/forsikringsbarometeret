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
import re
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote,urljoin,urlsplit
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
 'Gjensidige':['https://www.gjensidige.com/investor-relations/reports-and-presentations','https://www.gjensidige.com/investor-relations/'],
 'Tryg':['https://tryg.com/en/downloads-{year}'],
 'Sampo':['https://www.sampo.com/investors/quarterly-reporting/','https://www.sampo.com/result','https://www.sampo.com/investors/financial-information/quarterly-reporting/{year}/'],
 'Frende':['https://www.frende.no/om-oss/finansiell-informasjon/frende-holding/'],
 'Protector':['https://investor.protectorforsikring.no/','https://investor.protectorforsikring.no/all-reports','https://investor.protectorforsikring.no/financials','https://investor.protectorforsikring.no/press-releases'],
 'Storebrand':['https://www.storebrand.com/welcome/investor-relations/quarterly-reporting/storebrand-asa/{year}'],
 'KLP Skadeforsikring':['https://www.klp.no/om-klp/finans-og-ir/rapporter-og-presentasjoner'],
 'Alm. Brand':['https://investorrelations.almbrand.dk/English/financials/default.aspx','https://investorrelations.almbrand.dk/Danish/rapporter/default.aspx'],
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

def archive_links(company,markup,index,y,q):
    parser=Anchors();parser.feed(markup);results=[]
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
        results.append(dict(url=url,document_type='results_presentation',origin=index,label=label or name,exchange=False))
    # Some archives encode labelled PDF assets in JSON. A filename alone is
    # accepted only when both presentation type and period are explicit and
    # the exact HTTPS asset occurs in the issuer's returned markup.
    if company in ('Sampo','Alm. Brand','Gjensidige'):
        for href in re.findall(r'(?:https?://[^"\'<>\s\\]+|/globalassets/[^"\'<>\s\\]+)\.pdf(?:\?[^"\'<>\s\\]*)?',markup.replace('\\/','/'),re.I):
            url=urljoin(index,html.unescape(href));name=unquote(urlsplit(url).path.rsplit('/',1)[-1]).replace('_',' ').replace('-',' ')
            if trusted(company,url) and PRESENTATION.search(name) and not EXCLUDE.search(name) and period_label(name,y,q):
                results.append(dict(url=url,document_type='results_presentation',origin=index,label=name,exchange=False))
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
    if not re.search(ENTITY[company],head,re.I):raise ValueError('Issuer/entity not established on opening pages')
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
    result=dict(url=final,requested_url=url,document_type=kind,origin=doc['origin'],label=doc.get('label',''),
        format=fmt,source_sha256=digest,issuer_verified=True,period_verified=True,
        expected_fingerprint_matches=bool(expected) and set(expected)=={digest},semantic_matches=semantic_matches,
        fingerprint_status='changed_html_values_reparsed_and_matched' if semantic_matches else 'exact_match' if expected else 'new_source',source_pages_examined=len(texts),status='verified_document')
    return result,raw,texts

def collect_company(company,y,q,feed,extended):
    docs=report_sources(feed,extended,company,y,q);indexes=[];errors=[];news=[]
    def discover_index(template):
        url=template.format(year=y)
        try:
            raw,final=fetch(company,url,limit=5_000_000)
            found=archive_links(company,raw.decode('utf-8','replace'),final,y,q)
            return dict(url=final,status='checked',presentation_candidates=len(found)),found
        except Exception as exc:
            return dict(url=url,status='unavailable',error=str(exc)[:240]),[]
    for template in INDEXES[company]:
        entry,found=discover_index(template);indexes.append(entry);docs.extend(found)
    try:
        found,news=exchange_links(company,y,q,Client());docs.extend(found)
    except Exception as exc:errors.append('Exchange discovery: '+str(exc)[:300])
    unique={}
    for doc in docs:
        key=(doc['document_type'],doc['url'])
        if key not in unique or doc.get('expected_sha256'):unique[key]=doc
    verified=[];loaded=[]
    for doc in list(unique.values())[:12]:
        try:
            evidence,raw,texts=verify_document(company,doc,y,q,feed)
            verified.append(evidence);loaded.append((evidence,raw,texts))
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
    from reconcile_issuer_presentation_metrics import reconcile
    matches=[]
    for pe,pr,pt in loaded:
        if pe['document_type']=='results_presentation':
            matches.extend(reconcile(company,y,q,feed,[e for e,_,_ in loaded if e['document_type']=='quarterly_report'],pe,pt))
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
    report_hashes={x['source_sha256'] for x in verified if x['status']=='verified_document' and x['document_type']=='quarterly_report'}
    presentation_hashes={x['source_sha256'] for x in verified if x['status']=='verified_document' and x['document_type']=='results_presentation'}
    both=bool(report_hashes and presentation_hashes-report_hashes)
    status='conflicting_metric_evidence' if any(m['status']=='conflict' for m in matches) else 'partial_metric_reconciliation' if both and matches else 'both_documents_read_metrics_not_certified' if both else 'presentation_not_verified' if not presentation_found else 'report_not_verified'
    policy=presentation_policy(company,verified)
    if policy['presentation_exception']:
        status='report_only_verified' if report_hashes else 'report_only_not_verified'
    return dict(company=company,year=y,quarter=q,report_verified=bool(report_hashes),presentation_verified=presentation_found,
                **policy,
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
    required=[x for x in result if x['presentation_required']]
    exceptions=[x for x in result if x['presentation_exception']]
    out={'schema_version':2,'purpose':'issuer_document_and_metric_verification',
         'report_verified_count':sum(x['report_verified'] for x in result),
         'presentation_required_count':len(required),
         'presentation_verified_count':sum(x['presentation_verified'] for x in required),
         'report_only_issuers':[x['company'] for x in exceptions],
         'applicable_document_pairs_verified_count':sum(x['both_distinct_documents_verified'] for x in required),
         'all_required_documents_verified':all(x['report_verified'] for x in result) and all(x['both_distinct_documents_verified'] for x in required),
         'all_nine_both_documents_verified':all(x['both_distinct_documents_verified'] for x in result),
         'all_nine_dual_document_verified':False,'financial_observations_modified':False,
         'note':'Document verification is separate from independent metric extraction. Owner-confirmed report-only issuers are exempt from presentation requirements, but must pass original-report verification. Discovery continues for every issuer; a new presentation candidate reopens the requirement. Unverified presentation candidates are not reporting exceptions.',
         'companies':result}
    return out

def main():
    load=lambda name:json.loads((ROOT/'data'/name).read_text(encoding='utf-8'))
    report=audit(load('verified_financial_feed.json'),load('extended_insurer_financials.json'),load('nine_insurer_comparison.json'))
    atomic_write(OUT,report)
    for item in report['companies']:
        print('DUAL_ISSUER_AUDIT',json.dumps({k:item[k] for k in ('company','year','quarter','report_verified','presentation_verified','both_distinct_documents_verified','metric_reconciliation_status','presentation_required','presentation_exception','presentation_exception_under_review','archives_checked','exchange_announcements','errors')},ensure_ascii=False),flush=True)
        for d in item['documents']:print('DUAL_DOCUMENT',item['company'],json.dumps(d,ensure_ascii=False),flush=True)
        for m in item['cross_document_matches']:print('DUAL_METRIC_MATCH',item['company'],json.dumps(m,ensure_ascii=False),flush=True)
    print('DUAL_DOCUMENT_SUMMARY',json.dumps({'report_verified':sum(x['report_verified'] for x in report['companies']),
        'presentation_verified':sum(x['presentation_verified'] for x in report['companies']),
        'distinct_pairs':sum(x['both_distinct_documents_verified'] for x in report['companies']),
        'presentations_expected':report['presentation_required_count'],
        'report_only_issuers':report['report_only_issuers'],
        'all_required_documents_verified':report['all_required_documents_verified'],
        'metric_matches':sum(m['status']=='match' for x in report['companies'] for m in x['cross_document_matches']),
        'metric_conflicts':sum(m['status']=='conflict' for x in report['companies'] for m in x['cross_document_matches']),
        'full_reconciliation':report['all_nine_dual_document_verified']},ensure_ascii=False),flush=True)
if __name__=='__main__':main()
