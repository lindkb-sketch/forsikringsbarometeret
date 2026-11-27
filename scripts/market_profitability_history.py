"""Isolated-quarter profitability history for the two supplemental insurers.

Keep each verified original report and the exact period columns used.
For KLP and Alm. Brand the previous year's full-year and HIÅ amounts may
supply Q4; ratios are NEVER subtracted. No estimates or static chart values.
"""
import hashlib, math, re
from decimal import Decimal
from concurrent.futures import ThreadPoolExecutor

SCHEMA=2
ALM='Alm. Brand'
KLP='KLP Skadeforsikring'
RATIOS=('combined_ratio','loss_ratio','expense_ratio')

def finite(x):
    return type(x) in (float,int) and math.isfinite(x)
def period(y,q):return f'Q{q} {y}'
def source_ok(url,sha):
    return isinstance(url,str) and url.startswith('https://') and bool(re.fullmatch(r'[0-9a-f]{64}',sha or ''))
def checked_point(company,y,q,metrics,url,sha,page,method,source_period,roe=None,ytd_metrics=None):
    if not source_ok(url,sha) or type(page) is not int or page<=0 or q not in (1,2,3,4):raise ValueError('Invalid historical report provenance')
    if not all(finite(metrics.get(k)) and metrics[k]>=0 for k in RATIOS) or abs(metrics['combined_ratio']-metrics['loss_ratio']-metrics['expense_ratio'])>.25:
        raise ValueError('Invalid historical profitability ratios')
    return dict(company=company,period=period(y,q),year=y,quarter=q,period_type='quarter',scope='company' if company==KLP else 'group',
        cr=metrics['combined_ratio'],loss=metrics['loss_ratio'],cost=metrics['expense_ratio'],
        metrics={k:v for k,v in metrics.items() if finite(v)},ytd_metrics={k:v for k,v in (ytd_metrics or {}).items() if finite(v)},
        roe=roe if finite(roe) else None,source_url=url,source_sha256=sha,source_page=page,
        source_document_period=source_period,method=method,status='verified')

def amounts_ratios(revenue,claims,cost,reinsurance,service,tolerance):
    # claims/cost/reinsurance are positive signed expense components, with
    # reinsurance allowed to be a net income (negative expense).
    if min(revenue,claims,cost)<=0 or abs(revenue-claims-cost-reinsurance-service)>tolerance:
        raise ValueError('Quarter income/expense reconciliation failed')
    return dict(combined_ratio=float((claims+cost+reinsurance)/revenue*100),
        loss_ratio=float((claims+reinsurance)/revenue*100),expense_ratio=float(cost/revenue*100))

def alm_isolated_layout(left,full,y,q):
    from rolling_alm_brand_reports import column_layout
    # H1, half-year and 6M are explicit cumulative Q1-Q2 labels, not
    # isolated Q2 labels. Normalise only these exact period headers.
    def normalize_header(text):
        text=text.replace('–','-').replace('—','-')
        text=re.sub(r'\bQ1\s*-\s*Q([1-4])\b',r'Q1-Q\1',text,flags=re.I)
        if q==2:
            text=re.sub(r'\b(?:H1|HY1|HY|6M|First half|Half.year)\b','Q1-Q2',text,flags=re.I)
        return text
    for text in (left,full):
        try:return column_layout(normalize_header(text),y,q)
        except ValueError:pass
    # For Q2, only the first two isolated-quarter columns are needed.
    # A distinct current/prior header and a complete, reconciled numeric
    # table are sufficient even when the publisher renames its H1 heading.
    if q==2:
        for text in (left,full):
            normalized=normalize_header(text)
            header=re.split(r'(?im)^\s*(?:INCOME\s+)?Insurance revenue\s+(?=-?\d)',normalized,maxsplit=1)[0]
            lines=header.splitlines()
            matches=set()
            for a,b in zip(lines,lines[1:]):
                year_line=re.search(r'\bDKKm\s+((?:20\d{2}(?:\s+|$))+)',b,re.I)
                if not year_line:continue
                years=[int(x) for x in year_line.group(1).split()]
                labels=re.findall(r'\bQ1-Q[1-4]\b|\bQ[1-4]\b|\bFY\b',a,re.I)
                if [x.upper() for x in labels[:2]]==['Q2','Q2'] and years[:2]==[y,y-1] and len(labels)==len(years) and len(years) in (2,3,4,5):
                    matches.add(len(years))
            for line in lines:
                h=re.search(rf'(?:^|\bDKKm\s+)Q2\s+{y}\s+Q2\s+{y-1}(?:\s|$)',line.strip(),re.I)
                if not h:continue
                years=re.findall(r'\b20\d{2}\b',line[h.start():])
                if len(years) in (2,3,4,5):matches.add(len(years))
            if len(matches)==1:
                return (next(iter(matches)),None,None)
            if matches:raise ValueError('Ambiguous Alm Q2 isolated-quarter header')
    print('MARKET_ALM_HISTORY_HEADER',period(y,q),repr(left.splitlines()[:18]),repr(full.splitlines()[:18]),flush=True)
    raise ValueError('Explicit Alm historical isolated-quarter column header not verified')

def alm_points(raw,url,sha,y,q):
    from rolling_alm_brand_reports import read_report,column_layout,row,LABELS
    from alm_brand_live_pdf import trusted_pdf_link
    if not trusted_pdf_link(url):raise ValueError('Untrusted Alm report')
    texts,regions=read_report(raw)
    cover=' '.join(texts[:2])
    if not re.search(r'Alm[.\s]+Brand',cover,re.I) or not re.search(rf'\bQ\s*{q}\b',cover,re.I) or str(y) not in cover:raise ValueError('Wrong Alm report cover')
    eligible=[(i,t) for i,t in enumerate(texts) if all(x in t for x in ('Gross expense ratio','Net reinsurance ratio','Insurance service result','INCOME Insurance revenue',f'Q{q} {y}'))]
    if len(eligible)!=1:raise ValueError('Unique Alm group financial highlights missing')
    i,t=eligible[0];left=regions.get(i,{}).get('left') or t
    count,yi,pi=alm_isolated_layout(left,t,y,q)
    rows={k:row(left,label,count) for k,label in LABELS.items()}
    def amounts(idx):
        return (rows['insurance_revenue'][idx],abs(rows['claims_expenses'][idx]),abs(rows['operating_expenses'][idx]),-rows['reinsurance'][idx],rows['insurance_service_result'][idx])
    def verified(idx):
        actual={k:float(rows[k][idx]) for k in RATIOS}
        try:
            m=amounts_ratios(*amounts(idx),Decimal('1.5'))
            if any(abs(m[k]-actual[k])>.20 for k in RATIOS):raise ValueError('Alm historical ratio mismatch')
        except ValueError as exc:
            # Older highlights sometimes include a rounding/presentation
            # discrepancy. Admit the explicitly reported quarter only when
            # the independently reconciled original Personal and Commercial
            # segment tables reproduce the Group ratios and total revenue.
            if idx not in (0,1):
                raise
            try:
                from build_market_overview_context import verify_alm_market_quarter
                sr=verify_alm_market_quarter(list(enumerate(texts,1)),y,q,url,sha)
                parts=[]
                for segment in ('Private','Commercial'):
                    v={r['metric']:r['value'] for r in sr if r['year']==y-idx and r['segment']==segment}
                    if set(v)!={'insurance_revenue',*RATIOS}:raise ValueError('Incomplete Alm segment concordance')
                    parts.append(v)
                total=sum(v['insurance_revenue'] for v in parts)
                if abs(total-float(rows['insurance_revenue'][idx]))>3 or any(abs(sum(v[k]*v['insurance_revenue'] for v in parts)/total-actual[k])>.25 for k in RATIOS):
                    raise ValueError('Group/segment ratios do not reconcile')
                print('MARKET_ALM_HISTORY_SEGMENT_CONCORDANCE',period(y-idx,q),actual,flush=True)
            except Exception as mismatch:
                print('MARKET_ALM_HISTORY_DIAGNOSTIC',period(y,q),'column',idx,'values',[(k,str(v[idx])) for k,v in rows.items()],str(exc),str(mismatch),flush=True)
                raise ValueError('Alm quarter highlights failed independent segment reconciliation') from mismatch
        return {**actual,'insurance_revenue':float(rows['insurance_revenue'][idx]),'insurance_service_result':float(rows['insurance_service_result'][idx])}
    def cumulative(idx):
        if idx is None:return {}
        try:return verified(idx)
        except ValueError:return {}
    current,prior=verified(0),verified(1)
    cytd,pytd=cumulative(yi),cumulative(pi)
    current['insurance_revenue_growth']=100*(current['insurance_revenue']/prior['insurance_revenue']-1)
    if cytd.get('insurance_revenue',0)>0 and pytd.get('insurance_revenue',0)>0:cytd['insurance_revenue_growth']=100*(cytd['insurance_revenue']/pytd['insurance_revenue']-1)
    # ROE is explicitly period-labelled on the adjacent financial ratios
    # table; do not use a trailing-twelve-month return as isolated-quarter ROE.
    right=regions.get(i,{}).get('right') or t
    try:
        from rolling_alm_brand_reports import numeric_values
        rcount,ry,rp=alm_isolated_layout(right,t,y,q)
        roe=re.search(r'Return on equity after tax\s*\n\s*([-\d,.\s]+?)(?:\n|$)',right,re.I)
        if roe:
            rv=numeric_values(roe.group(1),rcount)
            current['return_on_equity']=float(rv[0]);prior['return_on_equity']=float(rv[1])
            if ry is not None:cytd['return_on_equity']=float(rv[ry])
            if rp is not None:pytd['return_on_equity']=float(rv[rp])
    except (ValueError,IndexError):pass
    # Solvency is a quarter-end snapshot, never taken from a prior full-year column.
    try:
        from rolling_alm_brand_reports import verify_report
        full=verify_report(texts,url,raw,y,q,regions=regions)
        current['solvency_ratio']=full['metrics']['solvency_ratio'];cytd['solvency_ratio']=current['solvency_ratio']
    except (ValueError,KeyError,IndexError):pass
    out=[checked_point(ALM,y,q,current,url,sha,i+1,'reported',period(y,q),current.get('return_on_equity'),cytd),
         checked_point(ALM,y-1,q,prior,url,sha,i+1,'reported_comparative',period(y,q),prior.get('return_on_equity'),pytd)]
    # A Q3 table's fifth column is explicitly the prior full year. The
    # validated header must contain FY, not merely a fifth number.
    if q==3 and count==5 and re.search(r'\bFY\b',left,re.I):
        verified(pi);verified(4)
        a,b=amounts(4),amounts(pi)
        m=amounts_ratios(*(x-z for x,z in zip(a,b)),Decimal('3'))
        out.append(checked_point(ALM,y-1,4,m,url,sha,i+1,'calculated_fy_minus_ytd',period(y,q)))
    return out

def klp_points(raw,url,sha,y,q):
    from import_extended_pdfs import pages
    from rolling_klp_reports import verify_report
    from klp_q2q3_reconcile import AMOUNTS,columns
    texts=pages(raw)
    result=verify_report(texts,y,q,url,sha,historical=True)
    page=result['source_documents'][0]['source_pages'][0]
    def amounts(a):return tuple(Decimal(str(a[k]))*sign for k,sign in [('insurance_revenue',1),('gross_claims_cost',-1),('operating_expenses',-1),('reinsurance_result',-1),('insurance_service_result',1)])
    def at(a):return {**amounts_ratios(*amounts(a),Decimal('.25')),'insurance_revenue':float(a['insurance_revenue']),'insurance_service_result':float(a['insurance_service_result'])}
    current=at(result['reported_quarter_amounts']);current.update(result['ratios'])
    prior=at(result['reported_prior_year_quarter_amounts'])
    current['insurance_revenue_growth']=100*(current['insurance_revenue']/prior['insurance_revenue']-1)
    management=result.get('reported_management_metrics',{})
    if finite(management.get('solvency_ratio')):current['solvency_ratio']=management['solvency_ratio']
    def cumulative(a):
        try:return at(a)
        except (KeyError,ValueError):return {}
    cytd,pytd=cumulative(result['reported_ytd_amounts']),cumulative(result['reported_prior_year_ytd_amounts'])
    if cytd.get('insurance_revenue',0)>0 and pytd.get('insurance_revenue',0)>0:cytd['insurance_revenue_growth']=100*(cytd['insurance_revenue']/pytd['insurance_revenue']-1)
    if 'solvency_ratio' in current:cytd['solvency_ratio']=current['solvency_ratio']
    out=[checked_point(KLP,y,q,current,url,sha,page,'calculated_from_quarter_amounts',period(y,q),ytd_metrics=cytd),
         checked_point(KLP,y-1,q,prior,url,sha,page,'calculated_comparative',period(y,q),ytd_metrics=pytd)]
    if q==3:
        t=texts[page-1]
        header=re.search(r'(?:NOTE\s+)?MILLIONER KRONER\s+([^\n]+)',t)
        expected=f'3. kvartal {y} 3. kvartal {y-1} 30.09.{y} 30.09.{y-1} 31.12.{y-1}'
        if header and ' '.join(header[1].split())==expected:
            fy={k:columns(t,label,expected=5)[4] for k,label in AMOUNTS.items()}
            prior=result['reported_prior_year_ytd_amounts']
            at(fy);at(prior)
            m=amounts_ratios(*(a-b for a,b in zip(amounts(fy),amounts(prior))),Decimal('.5'))
            out.append(checked_point(KLP,y-1,4,m,url,sha,page,'calculated_fy_minus_ytd',period(y,q)))
    return out

def build_history(extended,registry,previous):
    old=previous.get('documents',{}) if previous.get('schema_version')==SCHEMA else {}
    docs=dict(old);records=[];sources={}
    for company in (ALM,KLP):
        issuer=extended.get('insurers',{}).get(company,{})
        for item in [*issuer.get('periods',[]),issuer]:
            y,q=item.get('year'),item.get('quarter')
            url,sha=item.get('source_url'),item.get('source_sha256')
            if item.get('status')!='verified_official_pdf_reconciled' or not source_ok(url,sha) or type(y) is not int or q not in (1,2,3,4):continue
            page=item.get('source_pages',{}).get('combined_ratio') if company==ALM else next(iter(item.get('source_pages',{}).get('quarter',[])),None)
            try:
                row=checked_point(company,y,q,item['metrics'],url,sha,page,'reported' if company==ALM else 'calculated_from_quarter_amounts',period(y,q),item['metrics'].get('return_on_equity'),item.get('ytd_metrics'))
                records.append(row)
            except (ValueError,KeyError,TypeError):pass
            if item.get('source_type')=='official_quarterly_report':sources[sha]=(company,y,q,url)
    for label,src in registry.items():
        m=re.fullmatch(r'Q([1-4]) (20\d{2})',label)
        if m and source_ok(src.get('source_url'),src.get('source_sha256')):
            sources[src['source_sha256']]=(ALM,int(m[2]),int(m[1]),src['source_url'])
    # Discover the previous year's original report independently of a
    # current-year comparative. It is needed for prior-year growth (y-1
    # versus y-2), solvency and returns. Reuse verified original PDFs.
    for company in (ALM,KLP):
        item=extended.get('insurers',{}).get(company,{})
        y,q=item.get('year'),item.get('quarter')
        if not isinstance(y,int) or q not in (1,2,3,4):continue
        target=(y-1,q)
        if any((c,sy,sq)==(company,*target) for c,sy,sq,_ in sources.values()):continue
        saved=[(sha,d) for sha,d in old.items() if d.get('company')==company and d.get('source_document_period')==period(*target)]
        for sha,d in saved:
            if source_ok(d.get('source_url'),sha):sources[sha]=(company,*target,d['source_url'])
        if saved:continue
        try:
            if company==ALM:
                from alm_brand_report_discovery import discover
                from alm_brand_live_pdf import download_report
                urls=[r['url'] for r in discover(*target) if r.get('document_type')=='quarterly_report']
                fetch=download_report
            else:
                from rolling_klp_reports import fetch_archive
                from klp_q2_q3_discovery import discover
                from import_extended_pdfs import download
                urls=discover(fetch_archive(),target[0],periods=(target[1],)).get(target[1],[])
                fetch=lambda url:download(url,KLP)
            verified={}
            for url in list(dict.fromkeys(urls))[:5]:
                try:
                    raw=fetch(url);sha=hashlib.sha256(raw).hexdigest()
                    pts=(alm_points if company==ALM else klp_points)(raw,url,sha,*target)
                    if not any(x.get('period')==period(*target) for x in pts):continue
                    verified[sha]=dict(company=company,source_url=url,source_document_period=period(*target),points=pts)
                except Exception as exc:print('::warning::MARKET_COMPARATIVE_PDF',company,period(*target),str(exc)[:160],flush=True)
            if len(verified)==1:docs.update(verified)
            else:print('::warning::MARKET_COMPARATIVE_PDF',company,period(*target),'unique source not verified',len(verified),flush=True)
        except Exception as exc:print('::warning::MARKET_COMPARATIVE_PDF',company,period(*target),str(exc)[:180],flush=True)
    def read(task):
        sha,(company,y,q,url)=task
        saved=old.get(sha)
        if saved and saved.get('company')==company and saved.get('source_url')==url and saved.get('source_document_period')==period(y,q) and saved.get('points'):
            return sha,saved
        try:
            if company==ALM:
                from alm_brand_live_pdf import download_report
                raw=download_report(url)
            else:
                from import_extended_pdfs import download
                raw=download(url,KLP)
            if hashlib.sha256(raw).hexdigest()!=sha:raise ValueError('Historical PDF fingerprint changed')
            points=(alm_points if company==ALM else klp_points)(raw,url,sha,y,q)
            print('MARKET_PROFITABILITY_DOCUMENT',company,period(y,q),[(x['period'],x['cr'],x['method']) for x in points],flush=True)
            return sha,dict(company=company,source_url=url,source_document_period=period(y,q),points=points)
        except Exception as exc:
            print('::warning::MARKET_PROFITABILITY_HISTORY',company,period(y,q),type(exc).__name__,str(exc)[:220],flush=True)
            return sha,None
    with ThreadPoolExecutor(max_workers=3) as pool:
        for sha,entry in pool.map(read,sources.items()):
            if entry:docs[sha]=entry
    # Prefer a directly verified current report over its subsequent
    # comparative; prefer reported comparatives over a residual calculation.
    points={}
    rank={'reported':4,'calculated_from_quarter_amounts':4,'reported_comparative':3,'calculated_comparative':3,'calculated_fy_minus_ytd':2}
    for r in [*records,*[p for d in docs.values() for p in d['points']]]:
        k=(r['company'],r['period'])
        if k not in points or rank[r['method']]>rank[points[k]['method']]:points[k]=r
        elif points[k]['source_sha256']==r['source_sha256']:
            old_point=points[k]
            points[k]={**old_point,'metrics':{**r.get('metrics',{}),**old_point.get('metrics',{})},
                       'ytd_metrics':{**r.get('ytd_metrics',{}),**old_point.get('ytd_metrics',{})}}
    return dict(schema_version=SCHEMA,documents=docs,points=sorted(points.values(),key=lambda r:(r['company'],r['year'],r['quarter'])))
