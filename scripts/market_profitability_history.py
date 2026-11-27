"""Isolated-quarter profitability history for the two supplemental insurers.

Keep each verified original report and the exact period columns used.
For KLP and Alm. Brand the previous year's full-year and HIÅ amounts may
supply Q4; ratios are NEVER subtracted. No estimates or static chart values.
"""
import hashlib, math, re
from decimal import Decimal
from concurrent.futures import ThreadPoolExecutor

SCHEMA=1
ALM='Alm. Brand'
KLP='KLP Skadeforsikring'
RATIOS=('combined_ratio','loss_ratio','expense_ratio')

def finite(x):
    return type(x) in (float,int) and math.isfinite(x)
def period(y,q):return f'Q{q} {y}'
def source_ok(url,sha):
    return isinstance(url,str) and url.startswith('https://') and bool(re.fullmatch(r'[0-9a-f]{64}',sha or ''))
def checked_point(company,y,q,metrics,url,sha,page,method,source_period,roe=None):
    if not source_ok(url,sha) or type(page) is not int or page<=0 or q not in (1,2,3,4):raise ValueError('Invalid historical report provenance')
    if not all(finite(metrics.get(k)) and metrics[k]>=0 for k in RATIOS) or abs(metrics['combined_ratio']-metrics['loss_ratio']-metrics['expense_ratio'])>.25:
        raise ValueError('Invalid historical profitability ratios')
    return dict(company=company,period=period(y,q),year=y,quarter=q,period_type='quarter',scope='company' if company==KLP else 'group',
        cr=metrics['combined_ratio'],loss=metrics['loss_ratio'],cost=metrics['expense_ratio'],
        roe=roe if finite(roe) else None,source_url=url,source_sha256=sha,source_page=page,
        source_document_period=source_period,method=method,status='verified')

def amounts_ratios(revenue,claims,cost,reinsurance,service,tolerance):
    # claims/cost/reinsurance are positive signed expense components, with
    # reinsurance allowed to be a net income (negative expense).
    if min(revenue,claims,cost)<=0 or abs(revenue-claims-cost-reinsurance-service)>tolerance:
        raise ValueError('Quarter income/expense reconciliation failed')
    return dict(combined_ratio=float((claims+cost+reinsurance)/revenue*100),
        loss_ratio=float((claims+reinsurance)/revenue*100),expense_ratio=float(cost/revenue*100))

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
    count,yi,pi=column_layout(left,y,q)
    rows={k:row(left,label,count) for k,label in LABELS.items()}
    def amounts(idx):
        return (rows['insurance_revenue'][idx],abs(rows['claims_expenses'][idx]),abs(rows['operating_expenses'][idx]),-rows['reinsurance'][idx],rows['insurance_service_result'][idx])
    def verified(idx):
        m=amounts_ratios(*amounts(idx),Decimal('1.5'))
        actual={k:float(rows[k][idx]) for k in RATIOS}
        if any(abs(m[k]-actual[k])>.20 for k in RATIOS):raise ValueError('Alm historical ratio mismatch')
        return actual
    out=[checked_point(ALM,y,q,verified(0),url,sha,i+1,'reported',period(y,q)),checked_point(ALM,y-1,q,verified(1),url,sha,i+1,'reported_comparative',period(y,q))]
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
    result=verify_report(texts,y,q,url,sha)
    page=result['source_documents'][0]['source_pages'][0]
    def amounts(a):return tuple(Decimal(str(a[k]))*sign for k,sign in [('insurance_revenue',1),('gross_claims_cost',-1),('operating_expenses',-1),('reinsurance_result',-1),('insurance_service_result',1)])
    def at(a):return amounts_ratios(*amounts(a),Decimal('.25'))
    out=[checked_point(KLP,y,q,result['ratios'],url,sha,page,'calculated_from_quarter_amounts',period(y,q)),
         checked_point(KLP,y-1,q,at(result['reported_prior_year_quarter_amounts']),url,sha,page,'calculated_comparative',period(y,q))]
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
    docs={};records=[];sources={}
    for company in (ALM,KLP):
        issuer=extended.get('insurers',{}).get(company,{})
        for item in [*issuer.get('periods',[]),issuer]:
            y,q=item.get('year'),item.get('quarter')
            url,sha=item.get('source_url'),item.get('source_sha256')
            if item.get('status')!='verified_official_pdf_reconciled' or not source_ok(url,sha) or type(y) is not int or q not in (1,2,3,4):continue
            page=item.get('source_pages',{}).get('combined_ratio') if company==ALM else next(iter(item.get('source_pages',{}).get('quarter',[])),None)
            try:
                row=checked_point(company,y,q,item['metrics'],url,sha,page,'reported' if company==ALM else 'calculated_from_quarter_amounts',period(y,q),item['metrics'].get('return_on_equity'))
                records.append(row)
            except (ValueError,KeyError,TypeError):pass
            if item.get('source_type')=='official_quarterly_report':sources[sha]=(company,y,q,url)
    for label,src in registry.items():
        m=re.fullmatch(r'Q([1-4]) (20\d{2})',label)
        if m and source_ok(src.get('source_url'),src.get('source_sha256')):
            sources[src['source_sha256']]=(ALM,int(m[2]),int(m[1]),src['source_url'])
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
    return dict(schema_version=SCHEMA,documents=docs,points=sorted(points.values(),key=lambda r:(r['company'],r['year'],r['quarter'])))
