#!/usr/bin/env python3
"""Supplement the market commentary with verified original reports/results decks.

No issuer release, news, web article or external statistics supplies commentary.
Archive pages and exchange notices may discover document attachments only.
Unknown slide headings, periods, scopes and narrative layouts fail closed.
Presentation observations never replace report financial observations.
"""
import hashlib,json,re
from html.parser import HTMLParser
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import unquote,urlsplit
from audit_nine_issuer_documents import (INDEXES,KNOWN_PRESENTATIONS,REPORT_ONLY_ISSUERS,
    PRESENTATION,EXCLUDE,archive_links,issuer_detail_links,period_label,report_sources,
    trusted,fetch,verify_document,normalize,ISSUER_RELEASE_PAGES)

SCHEMA=4
GROUP_ONLY={'Sampo','Tryg','Gjensidige','Alm. Brand','Protector','Fremtind','Frende','KLP Skadeforsikring','Storebrand'}
NORWAY_TOTAL={'Fremtind','Frende','KLP Skadeforsikring','Storebrand'}
SPLIT={'Tryg','Gjensidige','Fremtind','Alm. Brand'}
GROWTH_RULES={
    'price':r'\b(?:growth|revenue growth|premium growth|increase in (?:insurance revenue|premiums))\b.{0,100}?\b(?:driven|supported|fuelled|explained)\s+by\b.{0,85}?\b(?:price increases|pricing actions|price adjustments|premium adjustments|rate increases)\b',
    'volume_up':r'\b(?:growth|revenue growth|premium growth)\b.{0,100}?\b(?:driven|supported|fuelled|explained)\s+by\b.{0,85}?\b(?:higher volumes|volume growth|growth in volumes|increased volumes)\b',
    'customer_growth':r'\b(?:customer base|number of customers)\b.{0,40}?\b(?:increased|grew|grown)\b',
    'policy_count_growth':r'\b(?:number of (?:active )?policies|policies in force)\b.{0,40}?\b(?:increased|grew|grown)\b',
    'customer_inflow':r'\b(?:customer inflow|new customer acquisition)\b.{0,50}?\b(?:bank partnerships|distribution partners|distribution agreements)\b',
    'portfolio_growth':r'\b(?:growth was positively impacted by|growth driven by|growth supported by)\s+portfolio growth\b',
    'retention_up':r'\b(?:customer )?retention (?:rates? )?(?:improved|increased|rose)\b',
    'volume_down':r'\b(?:volumes|insurance volumes|number of policies)\s+(?:decreased|declined|fell)\b',
    'risk_selection':r'\bprioriti[sz]ation of profitability over growth\b',
}
PROFIT_RULES={
    'lower_claim_frequency':r'\b(?:lower|reduced|decreased) (?:underlying )?(?:claims? frequency|frequency of (?:mid-sized )?claims)\b',
    'underlying_loss_improved':r'\bunderlying (?:frequency )?(?:claims|loss) ratio (?:improved|decreased|declined)\b',
    'weather_lower':r'\b(?:lower|reduced|fewer) weather(?:-related)? claims\b',
}
NORWEGIAN_GROWTH={
    'price':r'\bveksten (?:er|var) (?:hovedsakelig )?drevet av (?:premiejusteringer|prisjusteringer|prisøkninger)\b',
    'volume_up':r'\bveksten (?:er|var) (?:hovedsakelig )?drevet av (?:volumvekst|økt volum)\b',
    'customer_growth':r'\b(?:kundebestanden|antall kunder) (?:økte|har økt|vokste)\b',
    'policy_count_growth':r'\bantall forsikringer (?:økte|har økt|vokste)\b',
}
NORWEGIAN_PROFIT={
    'lower_claim_frequency':r'\blavere skadefrekvens(?:er)?\b',
    'underlying_loss_improved':r'\bunderliggende skadeprosent (?:er |ble )?(?:forbedret|bedret|redusert)\b',
}

def page_scope(company,raw,y,q,kind):
    """Only explicit, single-scope slide/report headings; never reuse Group
    figures for a segment or apply mixed parent-business text to Insurance."""
    lines=[normalize(l) for l in raw.splitlines() if normalize(l)]
    if not lines:return None
    # Find a current, explicitly labelled results/review heading. Do not
    # interpret mixed comparison tables, outlook, forecasts or consensus.
    candidates=[];period_only=False
    quarter=rf'(?:Q\s*{q}\s*[-/ ]?\s*{y}|{q}\.?\s*kvartal\s*{y})'
    cumulative=rf'(?:Q1\s*-\s*Q{q}\s+{y}|YTD\s+{y}|HIÅ\s+{y}|1-{q*3}/{y})'
    for i,line in enumerate(lines[:12]):
        if re.search(r'\b(?:outlook|guidance|consensus|forecast|target|estimates?|forventninger)\b',line,re.I):continue
        # Exact section titles on issuer materials (not arbitrary narrative).
        if re.fullmatch(r'(?:Group|Group results|Group highlights|Group: results and key figures|Group financial highlights|Konsern|Konsernets resultater|Alm\.? Brand Group)(?:\s*[-:–]\s*.*)?',line,re.I):
            scope='group/all'
        elif company=='Storebrand' and re.fullmatch(r'(?:Insurance|Insurance segment|Insurance: results and key figures|Forsikring)(?:\s*[-:–]\s*.*)?',line,re.I):
            scope='group/all'
        elif company in SPLIT and re.fullmatch(r'(?:Private|Personal Lines|Private segment|General Insurance Private|Privatmarkedet)(?:\s*[-:–]\s*.*)?',line,re.I):
            scope='group/pm'
        elif company in SPLIT and re.fullmatch(r'(?:Commercial|Commercial Lines|Commercial segment|General Insurance Commercial|Bedriftsmarkedet)(?:\s*[-:–]\s*.*)?',line,re.I):
            scope='group/bm'
        elif company=='Gjensidige' and re.fullmatch(r'(?:Private Norway|General Insurance Private Norway|Commercial Norway|General Insurance Commercial Norway)(?:\s*[-:–]\s*.*)?',line,re.I):
            scope='norway/pm' if 'private' in line.lower() else 'norway/bm'
        elif company in ('Gjensidige','Tryg','Protector') and re.fullmatch(r'(?:Norway|Norge)(?:\s*[-:–]\s*.*)?',line,re.I):
            scope='norway/all'
        elif company!='Storebrand' and re.fullmatch(rf'(?:Financial highlights[, ]*|Highlights of |Results |{re.escape(company)}\s+)?{quarter}(?:\s+highlights|\s+results)?',line,re.I):
            # A date/title is period evidence, not a second business scope.
            # A bare date cannot establish the scope of an otherwise unlabelled
            # page. Explicit company-level highlights may serve as a fallback.
            if re.search(r'financial highlights|highlights of |highlights$|^'+re.escape(company)+r'\s+',line,re.I):
                period_only=True
            continue
        elif company=='KLP Skadeforsikring' and re.fullmatch(r'KLP Skadeforsikring(?: AS)?',line,re.I):
            scope='group/all'
        else:continue
        if company=='Storebrand' and not re.match(r'Insurance|Forsikring',line,re.I):continue
        candidates.append((scope,i))
    scopes={x[0] for x in candidates}
    if not scopes and period_only:scopes={'group/all'}
    if len(scopes)!=1:return None
    scope=next(iter(scopes))
    head=' '.join(lines[:12])
    explicit_q=bool(re.search(rf'(?<![\w-]){quarter}\b',head,re.I))
    explicit_y=bool(re.search(rf'\b{cumulative}\b',head,re.I))
    # Only an actual results deck may imply the just-reported quarter from
    # an explicit "highlights of the quarter" slide on a verified cover.
    if explicit_q and explicit_y and q>1:return None
    if explicit_y:mode='ytd'
    elif explicit_q or (kind=='results_presentation' and re.search(r'\bhighlights of the quarter\b|\bquarterly highlights\b',head,re.I)):mode='quarter'
    else:return None
    if re.search(r'\b(?:outlook|guidance|consensus|forecast|targets?)\b',' '.join(lines[:4]),re.I):return None
    # Group-only context is not reused in a foreign geography. Owner-approved
    # Norwegian equivalents can be mapped only to their relevant total.
    views=[scope]
    if scope=='group/all':
        if company in NORWAY_TOTAL:views.append('norway/all')
        if company=='Protector':views.append('group/bm')
    elif scope.startswith('group/'):
        views.append('group/all')
        if company=='Fremtind':views.extend(['norway/'+scope.split('/')[1],'norway/all'])
    elif scope!='norway/all':views.append('norway/all')
    elif company=='Protector':views.append('norway/bm')
    return views,mode

def issuer_deck_insights(company,raw,y,q):
    """Observed results-deck layouts with explicit evidence in current slides.

    The caller has already checked the complete deck's issuer, report period
    and fingerprint. Exact slide titles and local bullet fragments establish
    scope; unrelated appendix charts, targets and forecasts are not used.
    """
    lines=[normalize(l) for l in raw.splitlines() if l.strip()]
    head=' '.join(lines[:5])
    body=' '.join(lines)
    out=[]
    def add(theme,driver,views,pattern,value_pattern=None):
        hit=re.search(pattern,body,re.I)
        if not hit:return
        if value_pattern:
            value=re.search(value_pattern,hit.group(0),re.I)
            if not value:return
            out.append((theme,driver,views,hit.group(0),float(value[1].replace(',','.'))))
        else:out.append((theme,driver,views,hit.group(0),None))
    # Prevent a clearly different quarter in the slide's main title from
    # borrowing the verified cover's identity. Comparative table labels below
    # the heading remain allowed.
    title=' '.join(lines[:2])
    dates=re.findall(r'\bQ([1-4])\s*[/ -]?\s*(20\d{2})\b',title,re.I)
    if dates and (str(q),str(y)) not in dates:return []
    if re.search(r'\b(?:outlook|guidance|forecast|consensus|targets?|appendix)\b',title,re.I):return []
    if company=='Gjensidige' and re.search(r'^Quarterly update\b.{0,90}\bInsurance revenue increased\b',head,re.I):
        add('growth_driver','price',['group/all'],r'\bPricing measures continued to support growth\b')
        add('growth_driver','volume_up',['group/all','group/pm','norway/all','norway/pm'],r'\bHigher volumes in Private Norway and Sweden\b')
        add('growth_driver','volume_down',['group/all','group/bm'],r'\bLower volumes in Commercial\b')
    elif company=='Sampo' and re.search(r'^(?:Palette\s+)?Private UK:\s*Capturing growth with disciplined underwriting\b',head,re.I):
        # Year-on-year AND quarter-on-quarter explicitly identify an actual
        # quarterly LCP movement. Keep LCP as the issuer's own definition;
        # do not equate it with customer count or IFRS revenue growth.
        add('growth_driver','uk_lcp_growth',['group/all'],r'\bLCP growth of \d+(?:[.,]\d+)?%\s+quarter-on-quarter and \d+(?:[.,]\d+)?%\s+year-on-year\b',r'and (\d+(?:[.,]\d+)?)%\s+year-on-year')
    elif company=='Protector' and re.search(rf'^Volume update\s+Q{q}:\s*GWP growth\b',head,re.I):
        hit=re.search(rf'\bQ{q}:\s*GWP growth at ([\d.,]+)%\s*\|\s*([\d.,]+)% in local currencies \(LCY\)',body,re.I)
        if hit:
            reported,local=(float(v.replace(',','.')) for v in hit.groups())
            if local-reported>=2:
                out.append(('growth_driver','gwp_lcy_higher',['group/all','group/bm'],hit.group(0),local))
    elif company=='Storebrand' and re.search(r'\bInsurance\b',body[:1200],re.I) and re.search(r'\bPortfolio premiums\b',body,re.I) and re.search(r'\bKey takeaways\b',body,re.I):
        # Insurance slide only: do not mix Savings or Group pension premiums
        # with the Insurance segment. Retail growth is not a policy count.
        add('growth_driver','retail_growth',['group/all','norway/all'],r'\bStrong growth and result development within Retail\b')
    elif company=='Alm. Brand' and re.search(r'^Personal lines\s+Improved performance driven by lower claims levels\b',head,re.I):
        if not re.search(r'\bClaims ratio improved by [\d.,]+ percentage points? year-on-year\b',body,re.I):return []
        add('growth_driver','price',['group/pm','group/all'],r'\bPremium growth of [\d.,]+%, driven by premium adjustments\b')
        add('profit_driver','underlying_loss_improved',['group/pm','group/all'],r'\bUnderlying claims ratio improved by [\d.,]+ percentage points?\b')
    elif company=='Alm. Brand' and re.search(r'^Commercial lines\s+Improved claims ratio especially driven by lower major claims and run-off gains\b',head,re.I):
        add('profit_driver','underlying_loss_improved',['group/bm','group/all'],r'\bUnderlying claims ratio improved by [\d.,]+ percentage points?\b')
        add('profit_driver','runoff_gains',['group/bm','group/all'],r'\bImproved claims ratio especially driven by lower major claims and run-off gains\b')
    return out

def document_insights(company,y,q,doc,texts):
    """Consume only verified, byte-hashed original documents. Each accepted
    assertion stores the matching original phrase, exact page and period."""
    kind=doc.get('document_type')
    if kind not in ('quarterly_report','results_presentation') or doc.get('status')!='verified_document' or doc.get('format')!='pdf' or not doc.get('issuer_verified') or not doc.get('period_verified'):return []
    sha=doc.get('source_sha256','');url=doc.get('url','')
    if not re.fullmatch(r'[0-9a-f]{64}',sha) or not url.startswith('https://'):return []
    period=f'Q{q} {y}';source_type='official_results_presentation' if kind=='results_presentation' else 'official_quarterly_report'
    out=[]
    def add(page,views,mode,theme,driver,evidence,text=None):
        for pt in ('quarter','ytd') if q==1 else (mode,):
            out.append(dict(company=company,period=period,source_document_period=period,source_type=source_type,source_url=url,source_sha256=sha,source_page=page,period_type=pt,views=views,theme=theme,driver=driver,evidence=evidence,text=text or driver,supplemental_document=True))
    for page,raw in enumerate(texts,1):
        if kind=='results_presentation':
            for theme,driver,views,evidence,value in issuer_deck_insights(company,raw,y,q):
                start=len(out)
                add(page,views,'quarter',theme,driver,evidence)
                if value is not None:
                    for entry in out[start:]:entry['reported_change_pct']=value
        found=page_scope(company,raw,y,q,kind)
        if not found:continue
        views,mode=found
        # Match only within a complete statement or slide bullet, not across
        # unrelated rows/columns. No number is inferred from a chart position.
        chunks=[normalize(l) for l in raw.splitlines() if l.strip()]
        for chunk in chunks:
            if re.search(r'\b(?:expected|expect|target|forecast|guidance|outlook|aim|ambition|will|may|could|forventes|forventer|mål)\b',chunk,re.I):continue
            # Explicit prior-only statements and future-year figures do not
            # describe the current reporting period.
            years={int(v) for v in re.findall(r'\b20\d{2}\b',chunk)}
            if years and y not in years:continue
            for theme,rules in [('growth_driver',GROWTH_RULES),('profit_driver',PROFIT_RULES),('growth_driver',NORWEGIAN_GROWTH),('profit_driver',NORWEGIAN_PROFIT)]:
                for driver,pattern in rules.items():
                    m=re.search(pattern,chunk,re.I)
                    if m:add(page,views,mode,theme,driver,m.group(0))
            # Specific material event: require both the named ruling and
            # an explicit actual accounting impact on the same statement.
            if re.search(r'\b(?:Danish )?Supreme Court ruling\b',chunk,re.I) and re.search(r'workers.{0,5}compensation',chunk,re.I) and re.search(r'\b(?:provision|charge|impact|affected)\b',chunk,re.I):
                if company in ('Tryg','Alm. Brand'):
                    event_mode='ytd' if re.search(r'Figures for Q1-Q[2-4]|one-off provision',chunk,re.I) else mode
                    add(page,views,event_mode,'regulation','workers_compensation_ruling',chunk,'Rapporteringen viser en resultateffekt knyttet til dansk høyesterettsdom om yrkesskadeforsikring.')
    return list({(r['source_sha256'],r['source_page'],r['period_type'],tuple(r['views']),r['theme'],r['driver']):r for r in out}.values())

def presentation_candidates(company,y,q,feed,extended,candidates):
    # Previously verified source and current exact issuer-linked candidates.
    out=[d for d in report_sources(feed,extended,company,y,q) if d['document_type']=='results_presentation']
    for c in candidates.get('candidates',[]):
        if c.get('company')!=company or c.get('document_type')!='results_presentation':continue
        url=c.get('document_url','');label=c.get('link_text','')
        desc=normalize(label+' '+unquote(urlsplit(url).path.rsplit('/',1)[-1]).replace('_',' ').replace('-',' '))
        if not trusted(company,url) or not PRESENTATION.search(desc) or EXCLUDE.search(desc) or not period_label(desc,y,q):continue
        if company in REPORT_ONLY_ISSUERS and not re.search(r'Holding|Skadeforsikring',desc,re.I):continue
        out.append(dict(url=url,document_type='results_presentation',origin='issuer_report_candidates',label=label,origin_kind='issuer_discovery_candidate',exchange=False))
    known=KNOWN_PRESENTATIONS.get((company,y,q))
    if known:
        url,origin,label,digest=known
        out.append(dict(url=url,document_type='results_presentation',origin=origin,label=label,exchange=True,origin_kind='historical_verified_exchange_attachment',expected_sha256=[digest]))
    return out

def discover_presentations(company,y,q):
    # Reuse existing issuer-only discovery for every new period. Bounded
    # fetches and no arbitrary external document URLs.
    found=[];details=[]
    for template in [*INDEXES[company][:3],*ISSUER_RELEASE_PAGES.get((company,y,q),())]:
        url=template.format(year=y)
        try:
            raw,final=fetch(company,url,limit=5_000_000)
            markup=raw.decode('utf-8','replace')
            found.extend(archive_links(company,markup,final,y,q))
            details.extend(issuer_detail_links(company,markup,final,y,q))
            if any(d['document_type']=='results_presentation' for d in found):break
        except Exception as exc:print('MARKET_DECK_DISCOVERY_RETRY',company,type(exc).__name__,str(exc)[:120],flush=True)
    if not any(d['document_type']=='results_presentation' for d in found):
        for url in list(dict.fromkeys(details))[:2]:
            try:
                raw,final=fetch(company,url,limit=5_000_000)
                found.extend(archive_links(company,raw.decode('utf-8','replace'),final,y,q))
            except Exception:continue
    return [d for d in found if d['document_type']=='results_presentation']

class ReportText(HTMLParser):
    """Extract visible paragraph/headline text from verified original HTML."""
    def __init__(self):
        super().__init__(convert_charrefs=True);self.parts=[];self.hidden=[]
    def handle_starttag(self,tag,attrs):
        if tag in ('script','style','nav'):self.hidden.append(tag)
        if not self.hidden and tag in ('p','div','h1','h2','h3','h4','li','br','tr'):self.parts.append('\n')
    def handle_endtag(self,tag):
        if self.hidden and tag==self.hidden[-1]:self.hidden.pop()
        if not self.hidden and tag in ('p','div','h1','h2','h3','h4','li','tr'):self.parts.append('\n')
    def handle_data(self,data):
        if not self.hidden:self.parts.append(data)
    def text(self):return ''.join(self.parts)

def html_report_insights(company,y,q,doc,raw):
    # Frende's official publisher HTML is its original quarterly report.
    # The existing verifier has already reconciled the same report section.
    m=re.fullmatch(r'https://frende\.wrep\.it/q([1-4])-(20\d{2})-frende-holding-as/sec/([67])',doc.get('url',''))
    if company!='Frende' or not m or (int(m[2]),int(m[1]))!=(y,q):return []
    if doc.get('document_type')!='quarterly_report' or doc.get('status')!='verified_document' or doc.get('format')!='html' or not doc.get('issuer_verified') or not doc.get('period_verified'):return []
    if hashlib.sha256(raw).hexdigest()!=doc.get('source_sha256'):return []
    parser=ReportText();parser.feed(raw.decode('utf-8'))
    # Never fabricate a page header or treat table cells as narrative.
    # Require the same explicit period/scope rules as PDF report prose.
    result=document_insights(company,y,q,{**doc,'format':'pdf'},[parser.text()])
    for r in result:r['source_page']=int(m[3])
    return result

def commentary_signature(company,y,q,feed,extended,candidates):
    # Include actual original-report fingerprints, not just a URL or quarter.
    # A report revision or newly discovered presentation invalidates the cache.
    sources=report_sources(feed,extended,company,y,q)
    sources+=presentation_candidates(company,y,q,feed,extended,candidates)
    records=sorted({(d['document_type'],d['url'],tuple(sorted(d.get('expected_sha256',[])))) for d in sources})
    return hashlib.sha256(json.dumps(records,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()

def collect(company,y,q,feed,extended,candidates,report_anchor,existing_report=None):
    docs=[];insights=[];seen=set();errors=[]
    if existing_report:
        docs.append(existing_report)
        seen.add(existing_report['url'])
    report_docs=report_sources(feed,extended,company,y,q)
    report_hashes={h for d in report_docs if d['document_type']=='quarterly_report' for h in d.get('expected_sha256',[])}
    def admit(options,kind):
        for option in options:
            url=option.get('url','')
            if url in seen:continue
            seen.add(url)
            try:
                ev,raw,texts=verify_document(company,option,y,q,feed)
                fmt=ev.get('format')
                if fmt!='pdf' and not (company=='Frende' and kind=='quarterly_report' and fmt=='html'):continue
                if kind=='quarterly_report' and not (ev.get('expected_fingerprint_matches') or fmt=='html' and ev.get('semantic_matches')):continue
                if kind=='results_presentation' and ev.get('source_sha256') in report_hashes:continue
                if any(d['source_sha256']==ev['source_sha256'] for d in docs):continue
                extracted=html_report_insights(company,y,q,ev,raw) if fmt=='html' else document_insights(company,y,q,ev,texts)
                if fmt=='pdf':
                    from market_commentary_explanations import explain
                    extracted.extend(explain(company,y,q,ev,texts))
                docs.append({**{k:ev[k] for k in ('url','document_type','source_sha256','status','source_pages_examined')},
                             'format':fmt,'analysis_status':'reviewed_with_evidence' if extracted else 'reviewed_no_unambiguous_driver',
                             'insight_count':len(extracted)})
                insights.extend(extracted)
                print('MARKET_COMMENTARY_DOCUMENT',company,f'Q{q} {y}',kind,ev['url'],ev['source_sha256'],'insights',len(extracted),flush=True)
                if kind=='results_presentation':
                    # Diagnostic only; source evidence is read on the CI
                    # runner, never substitute a guessed slide or web article.
                    for i,t in enumerate(texts,1):
                        if re.search(r'price|volume|retention|growth|underlying|storskad|premiejustering',t,re.I):
                            relevant=[normalize(l)[:240] for l in t.splitlines() if re.search(r'price|volume|retention|growth|underlying|storskad|premiejustering',l,re.I)]
                            print('MARKET_DECK_LAYOUT',company,i,repr(normalize(t)[:170]),repr(relevant[:3]),flush=True)
                if kind=='results_presentation':return True
            except Exception as exc:
                errors.append(type(exc).__name__+': '+str(exc)[:150])
        return False
    # Read each issuer's current original report, including Frende's
    # separately verified publisher sections. The segment builder supplies
    # its already read primary PDF, avoiding a second download of that URL.
    report_options=[d for d in report_docs if d['document_type']=='quarterly_report']
    report_options.sort(key=lambda d:(d['url']!=report_anchor,d['url']))
    admit(report_options[:5],'quarterly_report')
    options=presentation_candidates(company,y,q,feed,extended,candidates)
    got=admit(options[:5],'results_presentation')
    if not got:
        discovered=discover_presentations(company,y,q)
        options+=discovered
        got=admit(discovered[:5],'results_presentation')
    state='verified' if got else 'report_only' if company in REPORT_ONLY_ISSUERS and not options else 'not_verified'
    report_verified=any(d['document_type']=='quarterly_report' and d['status']=='verified_document' for d in docs)
    return dict(period=f'Q{q} {y}',anchor=report_anchor,report_verified=report_verified,
                presentation_status=state,documents=docs,insights=insights,errors=errors)

def enrich(result,feed,comparison,extended,candidates,previous):
    old=previous.get('commentary_documents',{}) if previous.get('commentary_document_schema')==SCHEMA else {}
    result['commentary_document_schema']=SCHEMA
    result['commentary_documents']={}
    tasks=[]
    for item in comparison.get('companies',[]):
        c=item.get('company');m=re.fullmatch(r'Q([1-4]) (20\d{2})',item.get('period',''))
        if c not in GROUP_ONLY or not m or item.get('status') not in ('verified_quarterly_feed','verified_official_pdf_reconciled'):continue
        q,y=map(int,m.groups())
        anchor=item.get('source_url','');period=f'Q{q} {y}'
        saved=old.get(c,{})
        signature=commentary_signature(c,y,q,feed,extended,candidates)
        # Independently cache each issuer's actual period/document set.
        # Missing decks are retried even when financial observations are
        # unchanged. A late deck or a revised report rebuilds that issuer.
        if saved.get('period')==period and saved.get('anchor')==anchor and saved.get('input_signature')==signature and saved.get('report_verified') is True and saved.get('presentation_status')=='verified':
            result['commentary_documents'][c]=saved;continue
        state=result.get('status',{}).get(c,{})
        existing=None
        if state.get('period')==period and state.get('source_url')==anchor and state.get('document_verified') is True:
            primary=[r for r in result['insights'] if r.get('company')==c and r.get('period')==period and r.get('source_sha256')==state.get('source_sha256')]
            existing=dict(url=anchor,document_type='quarterly_report',source_sha256=state['source_sha256'],
                          status='verified_document',format='pdf',source_pages_examined=state['source_pages_examined'],
                          analysis_status='reviewed_with_evidence' if primary else 'reviewed_no_unambiguous_driver',insight_count=len(primary))
        tasks.append((c,y,q,anchor,existing,signature))
    def run(task):
        c,y,q,anchor,existing,signature=task
        try:
            entry=collect(c,y,q,feed,extended,candidates,anchor,existing)
            entry['input_signature']=signature
            return c,entry
        except Exception as exc:return c,dict(period=f'Q{q} {y}',anchor=anchor,input_signature=signature,report_verified=bool(existing),presentation_status='not_verified',documents=[existing] if existing else [],insights=[],errors=[type(exc).__name__+': '+str(exc)[:150]])
    with ThreadPoolExecutor(max_workers=6) as pool:
        for c,entry in pool.map(run,tasks):result['commentary_documents'][c]=entry
    for c,entry in result['commentary_documents'].items():
        result['insights'].extend(entry.get('insights',[]))
        print('MARKET_COMMENTARY_COVERAGE',c,entry['period'],'report_verified',entry['report_verified'],entry['presentation_status'],len(entry['documents']),len(entry['insights']),entry['errors'][:2],flush=True)
