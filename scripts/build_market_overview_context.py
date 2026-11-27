#!/usr/bin/env python3
"""Market-only supplementary HIÅ rows and narrowly source-scoped commentary.

Prefer explicit cumulative columns. Weighted quarter aggregation requires
complete same-year observations of the identical scope. Never alter the
primary financial feed. A missing or changed original report fails closed.
"""
import hashlib,json,math,re
from pathlib import Path
from urllib.parse import urlsplit
from build_market_overview_segments import anchors,download,read_pages,norm,values,tryg_header,gjensidige_header,METRICS,SEGMENTS,parse_alm
from fremtind_apm_market import parse_income,parse_cr,BASIS

ROOT=Path(__file__).resolve().parents[1]
TARGET=ROOT/'data/market_overview_context.json'
VERSION=8
RATIOS=('combined_ratio','loss_ratio','expense_ratio')
NUM=r'[-−]?\d[\d,]*(?:\.\d+)?'
KEYS=('company','year','quarter','period_type','scope','segment','metric')
def key(r):return tuple(r.get(k) for k in KEYS)
def finite(v):return type(v) in (int,float) and math.isfinite(v)
def source(a,page):return dict(source_url=a['source_url'],source_sha256=a['source_sha256'],source_page=page)
def record(a,y,scope,seg,k,v,page,method='reported',definition='Original report: cumulative columns',documents=None):
    if not finite(v):raise ValueError('Nonfinite HIÅ value')
    return dict(company=a['company'],year=y,quarter=a['quarter'],scope=scope,segment=seg,
        period_type='ytd',metric=k,value=v,unit=('MDKK' if a['company'] in ('Tryg','Alm. Brand') else 'MNOK') if k=='insurance_revenue' else 'percent',
        status=method,source_type='official_quarterly_report',source_document_period=f"Q{a['quarter']} {a['year']}",
        source_definition=definition,source_section='HIÅ / '+(seg or scope),**source(a,page),
        market_anchor={k:a[k] for k in ('source_url','source_sha256')},source_documents=documents or [source(a,page)])
def make_rows(a,y,scope,seg,m,page,method='reported',documents=None,definition='Original report: cumulative columns'):
    if not finite(m.get('insurance_revenue')) or m['insurance_revenue']<=0 or not finite(m.get('combined_ratio')) or not 0<=m['combined_ratio']<=250:raise ValueError('Invalid HIÅ income or CR')
    if set(RATIOS).issubset(m):
        if any(not finite(m[k]) or m[k]<0 for k in RATIOS) or abs(m['combined_ratio']-m['loss_ratio']-m['expense_ratio'])>.25:raise ValueError('HIÅ CR components do not reconcile')
    elif a['company']!='Fremtind' or scope!='reported_segment' or any(k in m for k in RATIOS[1:]):raise ValueError('Missing ratio components')
    return [record(a,y,scope,seg,k,v,page,method,definition,documents) for k,v in m.items()]

def weighted(a,scope,seg,rows):
    out=[]
    for y in (a['year'],a['year']-1):
        blocks=[]
        for q in range(1,a['quarter']+1):
            rr=[r for r in rows if r.get('company')==a['company'] and r.get('scope')==scope and r.get('segment')==seg and r.get('year')==y and r.get('quarter')==q and r.get('period_type')=='quarter' and r.get('metric') in METRICS and r.get('status') in ('reported','calculated') and r.get('source_type')=='official_quarterly_report' and re.fullmatch(r'[0-9a-f]{64}',r.get('source_sha256','')) and type(r.get('source_page')) is int and r['source_page']>0 and finite(r.get('value'))]
            m={r['metric']:r for r in rr}
            if len(rr)!=4 or set(m)!=set(METRICS) or m['insurance_revenue']['value']<=0:break
            if abs(m['combined_ratio']['value']-m['loss_ratio']['value']-m['expense_ratio']['value'])>.25:break
            blocks.append(m)
        if len(blocks)!=a['quarter']:continue
        units={b['insurance_revenue']['unit'] for b in blocks}
        if not (units<={'MNOK','NOKm'} or units<={'MDKK','DKKm'}):continue
        if any(b[k]['unit']!='percent' for b in blocks for k in RATIOS):continue
        total=sum(b['insurance_revenue']['value'] for b in blocks)
        m={'insurance_revenue':total,**{k:sum(b[k]['value']*b['insurance_revenue']['value'] for b in blocks)/total for k in RATIOS}}
        docs=[{k:r[k] for k in ('year','quarter','metric','value','unit','source_url','source_sha256','source_page')} for b in reversed(blocks) for r in b.values()]
        out.extend(make_rows(a,y,scope,seg,m,docs[0]['source_page'],'calculated',docs,'Complete Q1 through Qn: income-weighted ratios, same scope and currency'))
    return out

def table_values(lines,company,count,allow_extra=False):
    """For identified tables only. Permit extra plot labels on Gjensidige Norway."""
    labels={'insurance_revenue':'Insurance revenue','combined_ratio':'Combined ratio','loss_ratio':'Loss ratio, net of reinsurance' if company=='Gjensidige' else 'Claims ratio, net of reinsurance','expense_ratio':'Cost ratio' if company=='Gjensidige' else 'Expense ratio'}
    result={}
    for metric,label in labels.items():
        found=[]
        for l in lines:
            # Norway tables start with the exact metric label; Tryg and
            # Gjensidige group narrative may precede a table row.
            m=re.search((r'^' if allow_extra else r'(?<!\w)')+re.escape(label)+r'(?:[¹²³⁴⁵⁶⁷⁸⁹⁰* ]+|[a-z]\))?\s+(?=[\d−-])',l,re.I)
            if not m:continue
            if metric=='loss_ratio' and re.search(r'underlying(?: frequency)?\s*$',l[:m.start()],re.I):continue
            nums=re.findall(NUM,l[m.end():])
            if len(nums)<count or (not allow_extra and len(nums)!=count):continue
            found.append([float(n.replace(',','').replace('−','-')) for n in nums[:count]])
        if len(found)!=1:raise ValueError('Ambiguous '+company+' '+metric)
        result[metric]=found[0]
    return result

def gj_blocks(a,pages):
    y,q=a['year'],a['quarter'];active=None
    for page,t in pages:
        lines=[norm(l) for l in t.splitlines()]
        heads=[m.group(1).title() for l in lines if (m:=re.fullmatch(r'General Insurance (Private(?: Norway| Denmark)?|Commercial(?: Norway| Denmark)?|Sweden)(?: \(change in local currency\))?',l,re.I))]
        if len(set(heads))>1:active=None;continue
        if heads:active=heads[0]
        elif any(re.fullmatch(r'(?:Pension|Management of the investment portfolio|Group highlights|Consolidated financial statement|Notes and key figures)',l,re.I) for l in lines):active=None
        if active not in ('Private','Commercial','Private Norway','Commercial Norway'):continue
        if not gjensidige_header(lines,y,q) or not any('NOK millions' in l for l in lines):continue
        header=' '.join(lines[:30])
        if q==1:pos=(0,1);counts=(3,2,5,4)
        elif re.search(r'\bYTD\s+'+str(y)+r'\s+YTD\s+'+str(y-1)+r'\b',header,re.I):pos=(2,3);counts=(5,4) if re.search(r'\bFY\s+'+str(y-1),header) else (4,)
        elif q==4 and re.search(r'\b(?:FY|Full year)\s+'+str(y)+r'\s+(?:FY|Full year)\s+'+str(y-1),header,re.I):pos=(2,3);counts=(4,5)
        else:continue
        for count in counts:
            try:
                v=table_values(lines,'Gjensidige',count,active.endswith('Norway'))
                break
            except ValueError:v=None
        if v is not None:yield active,page,lines,v,pos

def gj_ytd(a,pages):
    out=[];seen=set()
    for seg,page,lines,v,pos in gj_blocks(a,pages):
        if seg in seen:raise ValueError('Ambiguous cumulative Gjensidige segment')
        seen.add(seg)
        for y,i in zip((a['year'],a['year']-1),pos):out.extend(make_rows(a,y,'reported_segment',seg,{k:v[k][i] for k in METRICS},page))
    for y in (a['year'],a['year']-1):
        rows=[r for r in out if r['year']==y and r['segment'] in ('Private Norway','Commercial Norway')]
        if len(rows)!=8:continue
        rev={r['segment']:r['value'] for r in rows if r['metric']=='insurance_revenue'}
        total=sum(rev.values())
        m={'insurance_revenue':total,**{k:sum(r['value']*rev[r['segment']] for r in rows if r['metric']==k)/total for k in RATIOS}}
        docs=[{k:r[k] for k in ('metric','value','source_url','source_sha256','source_page','segment')} for r in rows]
        out.extend(make_rows(a,y,'norway',None,m,docs[0]['source_page'],'calculated',docs,'Income-weighted reported cumulative Norway PM/BM'))
    return out

def tryg_ytd(a,pages):
    y,q=a['year'],a['quarter'];out=[];found=set()
    for page,t in pages:
        lines=[norm(l) for l in t.splitlines()];header=' '.join(lines[:45])
        for seg in SEGMENTS:
            if not any(re.fullmatch(r'Key figures\s*[-–]\s*'+seg,l,re.I) for l in lines):continue
            # Require both matching isolated and cumulative headings, with
            # exact year order. Q1 is by definition the cumulative period.
            if q==1:continue
            if not re.search(r'\bQ'+str(q)+r'\s+Q'+str(q)+r'\s+Q1\s*[-–]\s*Q'+str(q)+r'\s+Q1\s*[-–]\s*Q'+str(q)+r'\b',header):continue
            if not re.search(str(y)+r'\s+'+str(y-1)+r'\s+'+str(y)+r'\s+'+str(y-1),header):continue
            try:v=table_values(lines,'Tryg',5)
            except ValueError:continue
            if seg in found:raise ValueError('Ambiguous Tryg cumulative segment')
            found.add(seg)
            for yr,i in ((y,2),(y-1,3)):out.extend(make_rows(a,yr,'reported_segment',seg,{k:v[k][i] for k in METRICS},page))
    # Geography's quarterly outline has the explicitly identified Norway
    # series. If no explicit cumulative geography table is available, use
    # every quarter's reported ratios and income on that exact basis.
    quarter_rows=[]
    for page,t in pages:
        lines=[norm(l) for l in t.splitlines()]
        if not any(re.fullmatch(r'Quarterly outline\s*[-–]\s*(?:Geography|Segments)',l,re.I) for l in lines):continue
        for label,scope,seg in [('Norwegian general insurance','norway',None),('Private','reported_segment','Private'),('Commercial','reported_segment','Commercial')]:
            pp=[i for i,l in enumerate(lines) if l==label]
            if len(pp)!=1:continue
            pos=pp[0];pairs=tryg_header(lines[:pos],y,q)
            if not pairs:continue
            end=next((i for i in range(pos+1,len(lines)) if re.fullmatch(r'Commercial|Swedish general insurance|Other general insurance|Private|Norwegian general insurance',lines[i],re.I) or re.match(r'^(?:IFRS 3 adjustment|Group items|Tryg total|Quarterly outline)',lines[i],re.I)),len(lines))
            try:v=values(lines[pos+1:end],'Tryg',len(pairs))
            except ValueError:continue
            for idx,(qr,yr) in enumerate(pairs):
                for k in METRICS:
                    quarter_rows.append(dict(company='Tryg',scope=scope,segment=seg,year=int(yr),quarter=int(qr),period_type='quarter',metric=k,value=v[k][idx],unit='MDKK' if k=='insurance_revenue' else 'percent',status='reported',source_type='official_quarterly_report',**source(a,page)))
    for scope,seg in [('norway',None)]+[('reported_segment',s) for s in SEGMENTS if s not in found]:
        out.extend(weighted(a,scope,seg,quarter_rows))
    return out

def fremtind_ytd(a,pages):
    y,q=a['year'],a['quarter'];u,h=a['source_url'],a['source_sha256']
    inc=parse_income(pages,y,q,u,h);cr=parse_cr(pages,y,q,u,h)
    ratios={}
    for page,t in pages:
        if page!=cr['source_page']:continue
        for seg,label in zip(SEGMENTS,('PM','BM')):
            matches=[]
            for line in t.splitlines():
                m=re.search(r'\b'+label+r'\s+((?:\d{1,3}(?:[,.]\d+)?\s*%\s*){2,5})',norm(line))
                if m:
                    vals=[float(x.replace(',','.')) for x in re.findall(r'(\d{1,3}(?:[,.]\d+)?)\s*%',m[1])]
                    if len(vals)==(3 if q==1 else 4 if q==4 else 5):matches.append(vals)
            if len(matches)!=1:raise ValueError('Fremtind cumulative CR columns ambiguous')
            ratios[seg]=matches[0][:2] if q==1 else matches[0][2:4]
    growth={}
    for page,t in pages:
        text=norm(t)
        if 'Resultatutvikling hittil i år' not in text:continue
        tail=text.split('Resultatutvikling hittil i år',1)[1][:2300]
        pm=re.search(r'privatmarkedet har en (økning|nedgang|reduksjon) i.{0,500}?inntekter fra forsikringstjenester på\s+(\d+(?:[,.]\d+)?)\s+prosent',tail,re.I)
        if not pm:continue
        bm=re.search(r'bedriftsmarkedet har en.{0,250}?\b(økning|nedgang|reduksjon)\s+på\s+(\d+(?:[,.]\d+)?)\s+prosent',tail[pm.end():],re.I)
        if bm:growth={s:(float(m[2].replace(',','.'))*(1 if m[1].lower()=='økning' else -1),page) for s,m in zip(SEGMENTS,(pm,bm))}
    out=[]
    for seg in SEGMENTS:
        out.append(record(a,y,'reported_segment',seg,'insurance_revenue',inc['income'][seg],inc['source_page'],definition=BASIS))
        for yr,ratio in zip((y,y-1),ratios[seg]):out.append(record(a,yr,'reported_segment',seg,'combined_ratio',ratio,cr['source_page'],definition=BASIS))
        if seg in growth:out.append(record(a,y,'reported_segment',seg,'insurance_revenue_growth',growth[seg][0],growth[seg][1],definition=BASIS))
    return out

def protector_ytd(a,pages):
    y,q=a['year'],a['quarter'];out=[]
    for page,t in pages:
        lines=[norm(l) for l in t.splitlines()]
        if not any(re.fullmatch(r'Segment information\s*[-–]\s*(?:Q1\s*[-–]\s*Q'+str(q)+r'|YTD|H1|FY'+(r'|Q1' if q==1 else '')+r')',l,re.I) for l in lines):continue
        if not any(re.search(r'UK\s+Sweden\s+Norway\s+Denmark\s+France',l) for l in lines):continue
        header=' '.join(lines[:12])
        if len(re.findall(r'\b'+str(y)+r'\b',header))<4 or len(re.findall(r'\b'+str(y-1)+r'\b',header))<4:continue
        v={}
        for k,label in [('insurance_revenue','Insurance revenue'),('loss_ratio','Loss ratio, net of reinsurance'),('expense_ratio','Cost ratio'),('combined_ratio','Combined ratio')]:
            hits=[m for l in lines if (m:=re.fullmatch(r'^'+re.escape(label)+r'[¹²³⁴⁵⁶⁷⁸⁹*]?\s+(.+)',l,re.I))]
            if len(hits)!=1:break
            nums=re.findall(NUM,hits[0][1])
            if len(nums) not in (9,10):break
            v[k]=[float(x.replace(',','').replace('−','-')) for x in nums]
        if set(v)!=set(METRICS):continue
        if out:raise ValueError('Ambiguous Protector HIÅ geography')
        for yr,i in ((y,4),(y-1,5)):out.extend(make_rows(a,yr,'norway',None,{k:v[k][i] for k in METRICS},page))
    return out

def verify_alm_market_quarter(pages,year,quarter,url,digest):
    """Verify segment evidence independently of unrelated group ROE/PBT layout."""
    from alm_brand_live_pdf import trusted_pdf_link
    from build_market_overview_segments import valid_batch
    if not trusted_pdf_link(url) or not re.fullmatch(r'[0-9a-f]{64}',digest):
        raise ValueError('Untrusted Alm market report provenance')
    cover=' '.join(norm(t) for page,t in pages if page in (1,2))
    if not re.search(r'\bAlm\.?\s+Brand\b',cover,re.I) or not re.search(rf'\bQ\s*{quarter}\s+{year}\b',cover,re.I):
        raise ValueError('Alm market report issuer/period cover mismatch')
    rows=parse_alm(pages,year,quarter,url,digest)
    anchor=dict(company='Alm. Brand',year=year,quarter=quarter,source_url=url,source_sha256=digest)
    if not valid_batch(rows,anchor):raise ValueError('Incomplete or invalid Alm market segment batch')
    by_page=dict(pages)
    labels=('Claims expenses','Insurance operating expenses','Profit/loss on reinsurance','Insurance service result')
    for seg in SEGMENTS:
        segment=[r for r in rows if r['segment']==seg]
        page_ids={r['source_page'] for r in segment}
        if len(page_ids)!=1:raise ValueError('Ambiguous Alm segment source page')
        lines=[norm(l) for l in by_page[next(iter(page_ids))].splitlines()]
        headers=[i for i,l in enumerate(lines) if re.search(r'\bDKKm\s+'+str(year)+r'\s+'+str(year-1)+r'\s+Change\b',l,re.I)]
        if len(headers)!=1:raise ValueError('Ambiguous Alm segment financial table')
        amounts={}
        for label in labels:
            pattern=r'(?<!\w)'+re.escape(label)+r'\s+('+NUM+r')\s+('+NUM+r')\s+('+NUM+r')\s*$'
            hits=[m.groups() for l in lines[headers[0]+1:] if (m:=re.search(pattern,l,re.I))]
            if len(hits)!=1:raise ValueError('Missing/ambiguous Alm segment amount: '+label)
            amounts[label]=[float(v.replace(',','').replace('−','-')) for v in hits[0]]
        for idx,yr in enumerate((year,year-1)):
            m={r['metric']:r['value'] for r in segment if r['year']==yr}
            rev=m['insurance_revenue']
            claims,cost,reinsurance,service=(amounts[k][idx] for k in labels)
            if not all(finite(v) for v in (claims,cost,reinsurance,service)) or claims>0 or cost>0:
                raise ValueError('Invalid Alm segment financial amounts')
            # Amounts rounded to whole MDKK; reported ratios to 0.1 pp.
            if abs(rev+claims+cost+reinsurance-service)>3:
                raise ValueError('Alm segment insurance accounting mismatch')
            calculated={'loss_ratio':-(claims+reinsurance)/rev*100,
                        'expense_ratio':-cost/rev*100,
                        'combined_ratio':-(claims+cost+reinsurance)/rev*100}
            if any(abs(m[k]-v)>.25 for k,v in calculated.items()):
                raise ValueError('Alm segment amount/ratio mismatch')
    return rows

def alm_ytd(a,pages,report_sources=None):
    y,q=a['year'],a['quarter']
    from alm_brand_report_discovery import discover
    from alm_brand_live_pdf import download_report,trusted_pdf_link
    from build_market_overview_segments import valid_batch
    report_sources={} if report_sources is None else report_sources
    # The current report has already been checked against the official feed's
    # fingerprint. Its verified source is retained across scheduled updates.
    rows=parse_alm(pages,y,q,a['source_url'],a['source_sha256'])
    if not valid_batch(rows,a):raise ValueError('Invalid current Alm segment batch')
    if q<4:rows=verify_alm_market_quarter(pages,y,q,a['source_url'],a['source_sha256'])
    report_sources[f'Q{q} {y}']={k:a[k] for k in ('source_url','source_sha256')}
    if q==1:return [{**r,'period_type':'ytd','market_anchor':{k:a[k] for k in ('source_url','source_sha256')},'source_documents':[source(a,r['source_page'])]} for r in rows]
    # Bootstrap only: official historical filings predating this registry.
    # All future quarters are remembered automatically from verified reports.
    historical={
        (2026,1):'https://attachment.news.eu.nasdaq.com/a8aef29e05c3998da5abf849fa270f731',
        (2026,2):'https://attachment.news.eu.nasdaq.com/a0593252bfc0d0f3ddce26fe6f42f412c',
    }
    for earlier in range(1,q):
        period=f'Q{earlier} {y}'
        saved=report_sources.get(period)
        if saved is not None:
            # Never silently replace a previously verified document with a new
            # PDF; retry on the next scheduled run if the source is unavailable.
            url=saved['source_url']
            if not trusted_pdf_link(url):raise ValueError('Untrusted saved Alm report')
            raw=download_report(url)
            sha=hashlib.sha256(raw).hexdigest()
            if sha!=saved['source_sha256']:raise ValueError('Saved Alm report fingerprint changed: '+period)
            rows.extend(verify_alm_market_quarter(read_pages(raw),y,earlier,url,sha))
            print('ALM_MARKET_PRIOR_REUSED',period,url,sha,flush=True)
            continue
        fallback=historical.get((y,earlier))
        try:docs=discover(y,earlier)
        except Exception as exc:
            if not fallback:raise
            print('::warning::ALM_MARKET_DISCOVERY',earlier,type(exc).__name__,str(exc)[:150],flush=True)
            docs=[]
        urls=list(dict.fromkeys(x['url'] for x in docs if x.get('document_type')=='quarterly_report' and trusted_pdf_link(x['url'])))
        batches={}
        def admit(url):
            try:
                raw=download_report(url)
                sha=hashlib.sha256(raw).hexdigest()
                batch=verify_alm_market_quarter(read_pages(raw),y,earlier,url,sha)
                batches[sha]=(url,batch)
                print('ALM_MARKET_PRIOR_VERIFIED',y,earlier,url,sha,flush=True)
            except Exception as exc:print('::warning::ALM_MARKET_PRIOR',earlier,type(exc).__name__,str(exc)[:150],flush=True)
        for url in urls[:5]:admit(url)
        if not batches and fallback and fallback not in urls[:5] and trusted_pdf_link(fallback):
            admit(fallback)
        if len(batches)!=1:raise ValueError('Unique verified Alm report missing '+period)
        sha,(url,batch)=next(iter(batches.items()))
        report_sources[period]=dict(source_url=url,source_sha256=sha)
        rows.extend(batch)
    result=[r for seg in SEGMENTS for r in weighted(a,'reported_segment',seg,rows)]
    if len(result)!=16:raise ValueError('Incomplete Alm HIÅ segment coverage')
    return result

def insight(a,page,views,theme,text,mode='quarter'):
    period=f"Q{a['quarter']} {a['year']}"
    return dict(company=a['company'],period=period,source_document_period=period,source_type='official_quarterly_report',period_type=mode,views=views,theme=theme,text=text,**source(a,page))

def growth_drivers(a,pages):
    """Positive evidence only, tied to verified original-report pages and scope.
    An unfamiliar disclosure layout yields no driver, never a guessed cause.
    """
    company=a['company'];q=a['quarter'];out=[]
    alm_sections={}
    gj_sections={}
    if company=='Alm. Brand':
        try:alm_sections={r['source_page']:r['segment'] for r in parse_alm(pages,a['year'],q,a['source_url'],a['source_sha256'])}
        except ValueError:return []
    if company=='Gjensidige':gj_sections={p:seg for seg,p,_,_,_ in gj_blocks(a,pages)}
    def add(page,views,mode,driver,evidence):
        modes=('quarter','ytd') if q==1 else (mode,)
        for period_type in modes:
            theme='profit_driver' if driver in ('lower_claim_frequency','underlying_loss_improved') else 'growth_driver'
            row=insight(a,page,views,theme,driver,period_type)
            row.update(driver=driver,evidence=evidence)
            if not any((r['driver'],r['period_type'],r['views'])==(driver,period_type,views) for r in out):
                out.append(row)
    def match(text,pattern):
        m=re.search(pattern,text,re.I)
        return m.group(0) if m else None
    for page,raw in pages:
        text=norm(raw.replace('\u00ad',''))
        if company=='Fremtind':
            if not ('Styrets beretning' in text and 'privatmarkedet har en' in text.lower() and 'bedriftsmarkedet har en' in text.lower()):continue
            hits=re.findall(r'Veksten er hovedsakelig drevet av premiejusteringer',text,re.I)
            quarter='Resultatutvikling i kvartalet' in text
            cumulative='Resultatutvikling hittil i år' in text
            views=['group/all','norway/all','group/pm','norway/pm','group/bm','norway/bm']
            if hits and quarter and not cumulative:add(page,views,'quarter','price',hits[0])
            elif hits and cumulative and not quarter:add(page,views,'ytd','price',hits[0])
            elif len(hits)==2 and quarter and cumulative:
                for mode in ('quarter','ytd'):add(page,views,mode,'price',hits[0])
            losses=re.findall(r'lavere skadefrekvenser på bil og næringsbygg',text,re.I)
            totals=['group/all','norway/all']
            if losses and quarter and not cumulative:add(page,totals,'quarter','lower_claim_frequency',losses[0])
            elif losses and cumulative and not quarter:add(page,totals,'ytd','lower_claim_frequency',losses[0])
            elif len(losses)==2 and quarter and cumulative:
                for mode in ('quarter','ytd'):add(page,totals,mode,'lower_claim_frequency',losses[0])
        elif company=='Alm. Brand':
            # Validate the section and exact isolated-quarter table before
            # interpreting its management review. No Group-to-Norway inference.
            seg=alm_sections.get(page)
            if seg=='Private':
                views=['group/pm','group/all']
                for driver,pattern in [('price',r'price adjustments to miti-?\s*gate claims inflation'),('customer_inflow',r'customer inflow through bank partnerships')]:
                    evidence=match(text,pattern)
                    if evidence:add(page,views,'quarter',driver,evidence)
            elif seg=='Commercial':
                views=['group/bm','group/all']
                for driver,pattern in [('competition',r'(?:continued|increasingly) soft market for workers.{0,3} compensation'),('risk_selection',r'continued focus on reducing volatility for large commercial clients')]:
                    evidence=match(text,pattern)
                    if evidence:add(page,views,'quarter',driver,evidence)
        elif company=='Tryg':
            if not re.search(r'\bKey figures\s*[-–]\s*Private\b',text,re.I):continue
            # These disclosures are in the Q-results narrative, not the
            # adjacent Q1-Qn claims table. Never call a Nordic number Norway.
            if not re.search(rf'\bResults Q{q} {a["year"]}\b',text,re.I):continue
            views=['group/pm','group/all']
            # PDF text extraction interleaves the review with a neighbouring
            # expense column and ratio table. Require both exact narrative
            # fragments close together, not a generic mention of a portfolio.
            evidence=match(text,r'growth was positively impacted by portfolio growth in selected segments')
            if not evidence:
                lines=[norm(l) for l in raw.splitlines()]
                for i,line in enumerate(lines):
                    if not re.search(r'\bgrowth was positively impacted by portfolio\b',line,re.I):continue
                    for j in range(i+1,min(i+4,len(lines))):
                        if re.match(r'^growth in selected segments\b',lines[j],re.I):
                            evidence=' | '.join(lines[i:j+1])
                            break
                    if evidence:break
            if evidence:add(page,views,'quarter','portfolio_growth',evidence)
            for driver,pattern in [('retention_up',r'retention rates improved slightly'),('underlying_loss_improved',rf'underlying claims ratio improved.{0,100}in Q{q} {a["year"]}')]:
                evidence=match(text,pattern)
                if evidence:add(page,views,'quarter',driver,evidence)
        elif company=='Gjensidige':
            # Require a verified segment chapter and a separately identified
            # quarter/YTD narrative. Norwegian submarket wording is required
            # before including Norwegian views; no Denmark-to-Norway inference.
            headers=[norm(l) for l in raw.splitlines()]
            named=next((seg for seg in ('Private','Commercial') if any(re.fullmatch('General Insurance '+seg,l,re.I) for l in headers)),None)
            if named and 'Development during the quarter' in text:seg,mode=named,'quarter'
            elif gj_sections.get(page) in ('Private','Commercial') and 'Year-to-date development' in text:seg,mode=gj_sections[page],'ytd'
            else:continue
            if not re.search(r'\bIn Norway,(?:(?!In Denmark).){0,140}?insurance revenue increased\b',text,re.I):continue
            market='pm' if seg=='Private' else 'bm'
            views=['group/'+market,'group/all','norway/'+market,'norway/all']
            if seg=='Private':
                rules=[('price',r'(?:primarily )?driven by price increases and higher volumes'),
                       ('volume_up',r'price increases and higher volumes for (?:the main product lines|property)'),
                       ('volume_pm_products',r'higher volumes for property,.{0,100}accident and health and travel insurance'),
                       ('customer_growth',r'number of customers increased')]
            else:
                rules=[('price',r'driven by price increases for all products'),
                       ('volume_down',r'decreased due to consistent prioritisation of'),
                       ('risk_selection',r'prioritisation of.{0,180}profitability over growth')]
            for driver,pattern in rules:
                evidence=match(text,pattern)
                if evidence:add(page,views,mode,driver,evidence)
    return out

def narratives(a,pages):
    out=[];c=a['company']
    if c=='Gjensidige':
        for seg,page,lines,v,ytd in gj_blocks(a,pages):
            market='pm' if seg.startswith('Private') else 'bm'
            views=['norway/'+market,'norway/all'] if seg.endswith('Norway') else ['group/'+market,'group/all']
            label={'Private':'privatmarkedet','Commercial':'bedriftsmarkedet','Private Norway':'norsk privatmarked','Commercial Norway':'norsk bedriftsmarked'}[seg]
            for l in lines:
                m=re.search(r'\bLarge losses, net of reinsurance[¹²³⁴⁵⁶⁷⁸⁹*]?\s+(.+)$',l,re.I)
                if not m or re.search(r'[A-Za-z]',m[1]):continue
                nums=re.findall(NUM,m[1])
                if len(nums) not in (4,5):continue
                for mode,pos in [('quarter',(0,1)),('ytd',ytd)]:
                    now,prior=[float(nums[i].replace(',','')) for i in pos]
                    if min(now,prior)<0 or abs(now-prior)<10:continue
                    out.append(insight(a,page,views,'large_claims','Gjensidige rapporterer '+('lavere' if now<prior else 'høyere')+' storskader i '+label+' enn samme periode i fjor.',mode))
    elif c=='Fremtind':
        for page,t in pages:
            text=norm(t)
            # An actual report, not a press release, is the source of the
            # named event. Only emit it when the report states the impact.
            fire=re.search(r'Brannen i Krokstadelva utgjorde ([\d ]+) millioner kroner av',text,re.I)
            if fire and 'Resultatutvikling i kvartalet' in text:
                amount=int(fire[1].replace(' ',''))
                if amount>=100:
                    msg=f'Brannen i Krokstadelva ga rapporterte storskader på {amount} mill. kroner i kvartalet.'
                    out.extend([insight(a,page,['group/all','norway/all'],'material_event',msg),insight(a,page,['group/all','norway/all'],'material_event','I siste kvartal: '+msg,'ytd')])
            if not re.search(r'Segment Privatmarkedet og Bedriftsmarkedet|Segmentresultater',text,re.I):continue
            for market,label in [('pm','Privatmarkedet'),('bm','Bedriftsmarkedet')]:
                hit=re.search(r'\b'+label+r'\s+utgjorde\s+([\d ]+)\s+millioner kroner i kvartalet',text,re.I)
                if not hit or not re.search(r'Netto storskader i',text[max(0,hit.start()-400):hit.start()],re.I):continue
                value=int(hit[1].replace(' ',''))
                views=['group/'+market,'norway/'+market,'group/all','norway/all']
                msg=f'Fremtind oppgir netto storskader på {value} mill. kroner i '+label.lower()+' i kvartalet.'
                out.extend([insight(a,page,views,'large_claims',msg),insight(a,page,views,'large_claims','I siste kvartal: '+msg,'ytd')])
    elif c=='Tryg':
        for page,t in pages:
            text=norm(t)
            if re.search(r'Key figures\s*[-–]\s*Commercial',text,re.I) and re.search(r'Supreme Court ruling on Danish workers.{0,20}compensation insurance',text,re.I) and re.search(r'one-off provision of DKK 1\.2bn',text,re.I):
                out.append(insight(a,page,['group/bm','group/all'],'regulation','Tryg opplyser at HIÅ-resultatet i bedriftsmarkedet er påvirket av en engangsavsetning etter dansk høyesterettsdom om yrkesskadeforsikring.','ytd'))
    elif c=='Alm. Brand':
        qrows=parse_alm(pages,a['year'],a['quarter'],a['source_url'],a['source_sha256'])
        for seg,market,label in [('Private','pm','privatmarkedet'),('Commercial','bm','bedriftsmarkedet')]:
            page=next((r['source_page'] for r in qrows if r['segment']==seg),None)
            for p,t in pages:
                if p!=page:continue
                hits=[]
                for l in t.splitlines():
                    m=re.search(r'\bMajor claims, net of reinsurance\s+('+NUM+r')\s+('+NUM+r')\s+('+NUM+r')\s*$',norm(l),re.I)
                    if m:hits.append([float(x.replace(',','')) for x in m.groups()])
                if len(hits)==1:
                    now,prior,_=hits[0]
                    if abs(abs(now)-abs(prior))>=.5:
                        msg='Alm. Brand rapporterer '+('lavere' if abs(now)<abs(prior) else 'høyere')+' storskadebelastning i '+label+' i kvartalet enn året før.'
                        out.extend([insight(a,page,['group/'+market,'group/all'],'large_claims',msg),insight(a,page,['group/'+market,'group/all'],'large_claims','I siste kvartal: '+msg,'ytd')])
    return out

def extra_anchors(feed):
    rows=[r for r in feed.get('observations',[]) if r.get('company')=='Protector' and r.get('scope')=='group' and r.get('period_type')=='quarter' and r.get('metric')=='insurance_revenue' and r.get('source_type')=='official_quarterly_report' and re.fullmatch(r'[0-9a-f]{64}',r.get('source_sha256',''))]
    if rows:yield max(rows,key=lambda r:(r['year'],r['quarter']))
def fetch(a):
    if a['company']=='Protector':
        from ingest_official_pdf import download as get
        if urlsplit(a['source_url']).hostname!='storage.mfn.se':raise ValueError('Untrusted Protector source')
        return get(a['source_url'])
    return download(a)
def build(feed,comparison,previous=None,fetcher=fetch,reader=read_pages):
    previous=previous or {};out={'schema_version':VERSION,'observations':[],'insights':[],'status':{}}
    out['alm_report_sources']=dict(previous.get('alm_report_sources',{})) if previous.get('schema_version') in (4,5,6,7,VERSION) else {}
    for a in [*anchors(feed,comparison),*extra_anchors(feed)]:
        c,y,q=a['company'],a['year'],a['quarter'];period=f'Q{q} {y}'
        old=previous.get('status',{}).get(c,{})
        if previous.get('schema_version')==VERSION and old.get('period')==period and old.get('source_sha256')==a['source_sha256'] and old.get('source_url')==a['source_url'] and old.get('status')=='verified':
            out['observations'].extend(r for r in previous.get('observations',[]) if r.get('company')==c)
            out['insights'].extend(r for r in previous.get('insights',[]) if r.get('company')==c and r.get('period')==period and r.get('source_type')=='official_quarterly_report' and r.get('supplemental_document') is not True)
            out['status'][c]=old;continue
        state={'period':period,'source_url':a['source_url'],'source_sha256':a['source_sha256'],'status':'not_verified'}
        try:
            raw=fetcher(a)
            if hashlib.sha256(raw).hexdigest()!=a['source_sha256']:raise ValueError('Original report fingerprint changed')
            pages=reader(raw)
            if not pages:raise ValueError('Empty verified source document')
            state.update(document_verified=True,source_pages_examined=len(pages))
            try:
                # Review the whole original report in addition to the
                # issuer-specific market parsers; retain exact document pages.
                from market_commentary_documents import document_insights
                ev=dict(document_type='quarterly_report',status='verified_document',format='pdf',
                        issuer_verified=True,period_verified=True,source_sha256=a['source_sha256'],url=a['source_url'])
                from market_commentary_explanations import explain
                page_texts=[t for _,t in pages]
                generic=document_insights(c,y,q,ev,page_texts)+explain(c,y,q,ev,page_texts)
                for r in generic:r['supplemental_document']=False
                out['insights'].extend(generic)
            except Exception as exc:print('::warning::MARKET_REPORT_COMMENTARY_ERROR',c,type(exc).__name__,str(exc)[:160],flush=True)
            try:
                batch=alm_ytd(a,pages,out['alm_report_sources']) if c=='Alm. Brand' else {'Fremtind':fremtind_ytd,'Gjensidige':gj_ytd,'Tryg':tryg_ytd,'Protector':protector_ytd}[c](a,pages)
                out['observations'].extend(batch)
                scopes=sorted({(r['scope'],r.get('segment') or '') for r in batch if r['year']==y and r['metric']=='insurance_revenue'})
                expected=5 if c=='Gjensidige' else 3 if c=='Tryg' else 1 if c=='Protector' else 2
                state.update(status='verified' if len(scopes)==expected else 'partial',scopes=scopes,observations=len(batch))
                print('MARKET_CONTEXT_YTD',c,period,scopes,flush=True)
            except Exception as exc:print('::warning::MARKET_CONTEXT_YTD_ERROR',c,type(exc).__name__,str(exc)[:260],flush=True)
            try:out['insights'].extend(growth_drivers(a,pages))
            except Exception as exc:print('::warning::MARKET_GROWTH_DRIVER_ERROR',c,type(exc).__name__,str(exc)[:160],flush=True)
            try:out['insights'].extend(narratives(a,pages))
            except Exception as exc:print('::warning::MARKET_CONTEXT_NARRATIVE_ERROR',c,type(exc).__name__,str(exc)[:160],flush=True)
        except Exception as exc:print('::warning::MARKET_CONTEXT_SOURCE_ERROR',c,type(exc).__name__,str(exc)[:220],flush=True)
        out['status'][c]=state
    return out
def main():
    load=lambda n:json.loads((ROOT/'data'/n).read_text(encoding='utf-8'))
    feed=load('verified_financial_feed.json');comparison=load('nine_insurer_comparison.json')
    previous=load(TARGET.name) if TARGET.exists() else {}
    result=build(feed,comparison,previous)
    extended=load('extended_insurer_financials.json')
    from market_commentary_documents import enrich
    enrich(result,feed,comparison,extended,load('report_candidates.json'),previous)
    from market_profitability_history import build_history
    result['profitability_history']=build_history(extended,result['alm_report_sources'],previous.get('profitability_history',{}))
    from company_comparison_history import build as build_comparisons
    result['company_comparisons']=build_comparisons(feed,previous.get('company_comparisons',{}))
    from publish_geographic_workbooks import atomic_write
    atomic_write(TARGET,result)
    print('MARKET_CONTEXT',result['status'],'insights',len(result['insights']),flush=True)
if __name__=='__main__':main()
