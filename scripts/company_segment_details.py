"""Official same-scope company detail comparisons and missing reported ROE.

This is a supplement to the public market context, never the ranking or the
primary financial feed. Missing/ambiguous table columns are not estimates.
"""
import hashlib, math, re
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlsplit

SCHEMA=1
ALM='Alm. Brand'
TARGETS=('Gjensidige','Tryg','Sampo')
CORE=('insurance_revenue','combined_ratio','loss_ratio','expense_ratio')
HOSTS={
    'Gjensidige':{'gjensidige.com','www.gjensidige.com','gjensidige.se','www.gjensidige.se','mb.cision.com','gjensidige.no','www.gjensidige.no'},
    'Tryg':{'tryg.com','www.tryg.com'},
    'Sampo':{'sampo.com','www.sampo.com','attachment.news.eu.nasdaq.com'},
}
def finite(v):return type(v) in (int,float) and math.isfinite(v)
def period(y,q):return f'Q{q} {y}'
def key(r):return tuple(r.get(k) for k in ('company','year','quarter','period_type','scope','segment','metric'))
def trusted(company,url):
    if not isinstance(url,str) or not url.startswith('https://'):return False
    if company==ALM:
        from alm_brand_live_pdf import trusted_pdf_link
        return trusted_pdf_link(url)
    return urlsplit(url).hostname in HOSTS.get(company,set())

def observation(a,year,seg,metric,value,page,kind='quarter',scope='reported_segment',definition=None):
    if not finite(value) or not isinstance(page,int) or page<1:raise ValueError('Invalid company observation')
    if metric=='insurance_revenue' and value<=0:raise ValueError('Invalid segment revenue')
    if metric in CORE[1:] and not 0<=value<=250:raise ValueError('Invalid segment ratio')
    c=a['company']
    unit={'Gjensidige':'MNOK','Tryg':'MDKK','Sampo':'EURm',ALM:'MDKK'}[c] if metric in ('insurance_revenue','insurance_service_result') else 'percent'
    return dict(company=c,year=year,quarter=a['quarter'],period_type=kind,scope=scope,segment=seg,
        metric=metric,value=value,unit=unit,status='reported',source_type='official_quarterly_report',
        source_url=a['source_url'],source_sha256=a['source_sha256'],source_page=page,
        source_document_period=period(a['year'],a['quarter']),
        source_definition=definition or ('Sampo interim statement; '+seg+' reported financial table' if c=='Sampo' else 'Original report; same-scope financial table'))

def amount_row(lines,label,count,allow_extra=False):
    from build_market_overview_segments import norm
    from import_group_ytd import parse_values
    found=[]
    for raw in lines:
        line=norm(raw)
        hit=re.search(r'(?<![\w])'+re.escape(label)+r'(?:[¹²³⁴⁵⁶⁷⁸⁹⁰*]+)?\s+(?=[\d−(-])',line,re.I)
        if not hit:continue
        tail=line[hit.end():]
        vals=parse_values(tail,count)
        if vals is None and allow_extra:
            cells=tail.split()
            if len(cells)>=count:vals=parse_values(' '.join(cells[:count]),count)
        if vals is not None:found.append(tuple(vals))
    return list(found[0]) if len(set(found))==1 and found else None

def result_matches(revenue,cr,result):
    return finite(result) and abs(revenue*(1-cr/100)-result)<=max(3,revenue*.0025)

def gj_rows(a,pages):
    from build_market_overview_context import gj_blocks
    out=[];y,q=a['year'],a['quarter']
    for seg,page,lines,v,pos in gj_blocks(a,pages):
        service=amount_row(lines,'Insurance service result',len(v['insurance_revenue']),seg.endswith('Norway'))
        for kind,columns in (('quarter',(0,1)),('ytd',pos)):
            for yr,i in zip((y,y-1),columns):
                for metric in CORE:out.append(observation(a,yr,seg,metric,v[metric][i],page,kind))
                if service and result_matches(v['insurance_revenue'][i],v['combined_ratio'][i],service[i]):
                    out.append(observation(a,yr,seg,'insurance_service_result',service[i],page,kind))
    return out

def tryg_rows(a,pages):
    from build_market_overview_segments import parse_tryg,norm,tryg_header,SEGMENTS
    from build_market_overview_context import tryg_ytd,table_values
    y,q=a['year'],a['quarter']
    out=parse_tryg(pages,y,q,a['source_url'],a['source_sha256'])
    try:out+=tryg_ytd(a,pages)
    except ValueError:pass
    for page,t in pages:
        lines=[norm(l) for l in t.splitlines()]
        if any(re.fullmatch(r'Quarterly outline\s*[-–]\s*Segments',l,re.I) for l in lines):
            for seg in SEGMENTS:
                starts=[i for i,l in enumerate(lines) if l==seg]
                if len(starts)!=1:continue
                pos=starts[0];pairs=tryg_header(lines[:pos],y,q)
                if not pairs:continue
                end=next((i for i in range(pos+1,len(lines)) if re.fullmatch(r'Private|Commercial',lines[i],re.I) or re.match(r'^(?:IFRS 3 adjustment|Group items|Tryg total|Quarterly outline)',lines[i],re.I)),len(lines))
                service=amount_row(lines[pos+1:end],'Insurance service result',len(pairs))
                if not service:continue
                for yr in (y,y-1):
                    idx=pairs.index((str(q),str(yr))) if (str(q),str(yr)) in pairs else None
                    vals={r['metric']:r['value'] for r in out if r['segment']==seg and r['year']==yr and r['period_type']=='quarter'}
                    if idx is not None and all(k in vals for k in ('insurance_revenue','combined_ratio')) and result_matches(vals['insurance_revenue'],vals['combined_ratio'],service[idx]):
                        out.append(observation(a,yr,seg,'insurance_service_result',service[idx],page))
        if q==1:continue
        header=' '.join(lines[:45])
        if not re.search(r'\bQ'+str(q)+r'\s+Q'+str(q)+r'\s+Q1\s*[-–]\s*Q'+str(q)+r'\s+Q1\s*[-–]\s*Q'+str(q)+r'\b',header):continue
        if not re.search(str(y)+r'\s+'+str(y-1)+r'\s+'+str(y)+r'\s+'+str(y-1),header):continue
        for seg in SEGMENTS:
            if not any(re.fullmatch(r'Key figures\s*[-–]\s*'+seg,l,re.I) for l in lines):continue
            try:v=table_values(lines,'Tryg',5)
            except ValueError:continue
            service=amount_row(lines,'Insurance service result',5)
            if not service:continue
            for yr,i in ((y,2),(y-1,3)):
                if result_matches(v['insurance_revenue'][i],v['combined_ratio'][i],service[i]):
                    out.append(observation(a,yr,seg,'insurance_service_result',service[i],page,'ytd'))
    return out

def sampo_rows(a,pages,known):
    """Read the shared financial overview header before the named segment.
    The current quarter must match the independently verified source page.
    """
    from sampo_group_kpis import PERIOD,DASHES
    from import_group_ytd import parse_values
    y,q=a['year'],a['quarter'];out=[]
    for seg in ('Private Nordic','Nordic Commercial'):
        expected=[r for r in known if r.get('company')=='Sampo' and r.get('year')==y and r.get('quarter')==q and r.get('period_type')=='quarter' and r.get('segment')==seg and r.get('metric')=='insurance_revenue' and r.get('source_sha256')==a['source_sha256']]
        if len(expected)!=1:continue
        candidates=[]
        current=(3*q-2,3*q,y);prior=(3*q-2,3*q,y-1)
        for page,t in pages:
            if page!=expected[0].get('source_page'):continue
            lines=t.splitlines()
            starts=[i for i,l in enumerate(lines) if re.fullmatch(re.escape(seg),l.strip(),re.I)]
            if len(starts)!=1:continue
            start=starts[0]
            end=next((i for i in range(start+1,len(lines)) if re.fullmatch(r'Private UK|Private Nordic|Nordic Commercial|Nordic Industrial|Premium development|Underwriting performance',lines[i].strip(),re.I)),len(lines))
            for i in range(start+1,end):
                hit=re.fullmatch(r'\s*Insurance revenue,\s*net(?:\s*\([^)]*\))?\s+EURm\s+(.+?)\s*',lines[i],re.I)
                if not hit:continue
                for label in lines[:i]:
                    tokens=[tuple(map(int,m.group(1,2,3))) if m.group(1) else int(m.group(4)) for m in PERIOD.finditer(label.translate(str.maketrans(DASHES,'-'*len(DASHES))))]
                    if tokens.count(current)!=1 or tokens.count(prior)!=1:continue
                    vals=parse_values(hit[1],len(tokens))
                    if not vals or abs(vals[tokens.index(current)]-expected[0]['value'])>.11:continue
                    batch=[]
                    for yr in (y,y-1):
                        token=(3*q-2,3*q,yr)
                        if vals[tokens.index(token)]<=0:break
                        batch.append(observation(a,yr,seg,'insurance_revenue',vals[tokens.index(token)],page))
                        cum=yr if q==4 else (1,3*q,yr)
                        if tokens.count(cum)==1 and vals[tokens.index(cum)]>0:
                            batch.append(observation(a,yr,seg,'insurance_revenue',vals[tokens.index(cum)],page,'ytd'))
                    if all(any(r['year']==yr and r['period_type']=='quarter' for r in batch) for yr in (y,y-1)):candidates.append(batch)
        unique={tuple((key(r),r['value']) for r in b):b for b in candidates}
        if len(unique)==1:out.extend(next(iter(unique.values())))
        else:print('::warning::COMPANY_SAMPO_COMPARATIVE',period(y,q),seg,'verified overview page',expected[0].get('source_page'),'candidate tables',len(unique),flush=True)
    return out

def alm_roe_layout(text,y,q):
    """The right-hand crop may contain part of the left-hand FY header.
    Use only period labels adjacent to the rightmost DKKm year header;
    require explicit Q4/FY distinction and correct comparative years.
    """
    text=text.replace('–','-').replace('—','-')
    text=re.sub(r'\bQ1\s*-\s*Q([1-4])\b',r'Q1-Q\1',text,flags=re.I)
    if q==2:text=re.sub(r'\b(?:H1|HY1|HY|6M)\b','Q1-Q2',text,flags=re.I)
    if q==3:text=re.sub(r'\b9M\b','Q1-Q3',text,flags=re.I)
    hits=set()
    lines=text.splitlines()
    for top,years in zip(lines,lines[1:]):
        matches=list(re.finditer(r'\bDKKm\s+((?:20\d{2}(?:\s+|$))+)',years,re.I))
        if not matches:continue
        ys=[int(v) for v in matches[-1].group(1).split()]
        labels=[v.upper() for v in re.findall(r'\bQ1-Q[1-4]\b|\bQ[1-4]\b|\bFY\b',top,re.I)]
        if len(labels)<len(ys):continue
        labels=labels[-len(ys):]
        if labels[:2]!=[f'Q{q}',f'Q{q}'] or ys[:2]!=[y,y-1]:continue
        if q==1 and (len(ys)==2 or len(ys)==3 and labels[2]=='FY' and ys[2]==y-1):
            hits.add((len(ys),0,1))
        elif q>1 and len(ys) in (4,5) and ys[2:4]==[y,y-1]:
            cumulative=['FY','FY'] if q==4 else [f'Q1-Q{q}']*2
            if labels[2:4]==cumulative and (len(ys)==4 or labels[4]=='FY' and ys[4]==y-1):
                hits.add((len(ys),2,3))
    if len(hits)==1:return next(iter(hits))
    if len(hits)>1:raise ValueError('Ambiguous ROE column headers')
    from rolling_alm_brand_reports import column_layout
    return column_layout(text,y,q)

def alm_roe_rows(a,raw):
    from rolling_alm_brand_reports import read_report,numeric_values
    y,q=a['year'],a['quarter'];texts,regions=read_report(raw)
    cover=' '.join(texts[:2])
    if not re.search(r'Alm[.\s]+Brand',cover,re.I) or str(y) not in cover or not re.search(rf'\bQ\s*{q}\b',cover,re.I):
        raise ValueError('Wrong Alm ROE report')
    found=[]
    for i,t in enumerate(texts):
        if 'Return on equity after tax' not in t or not re.search(r'Financial highlights and key ratios',t,re.I) or 'Technical provisions' not in t or 'Insurance revenue' not in t:continue
        right=regions.get(i,{}).get('right') or t
        for txt in (right,t):
            try:count,yi,pi=alm_roe_layout(txt,y,q)
            except ValueError:continue
            # Both inline (% p.a.) **) rows and older wrapped rows.
            pattern=r'Return on equity after tax(?:[ \t]*\(\s*%\s*p\.\s*a\.\s*\))?[ \t]*(?:\*+\))?[ \t]*(?:\n[ \t]*)?([-−\d,.% \t]+)(?=\n|$)'
            for hit in re.findall(pattern,txt,re.I):
                try:vals=numeric_values(hit.replace('−','-').replace('%',''),count)
                except ValueError:continue
                if not all(finite(float(v)) and abs(float(v))<1000 for v in vals):continue
                batch=[observation(a,yr,None,'return_on_equity',float(vals[j]),i+1,'quarter','group','Reported annualised return on equity after tax; explicitly labelled quarter') for yr,j in ((y,0),(y-1,1))]
                for yr,j in ((y,yi),(y-1,pi)):
                    if j is not None:batch.append(observation(a,yr,None,'return_on_equity',float(vals[j]),i+1,'ytd','group','Reported annualised return on equity after tax; explicitly labelled cumulative period'))
                found.append(batch)
    unique={tuple((key(r),r['value']) for r in b):b for b in found}
    return next(iter(unique.values())) if len(unique)==1 else []

def alm_rows(a,pages,raw):
    from build_market_overview_context import verify_alm_market_quarter
    from build_market_overview_segments import parse_alm
    y,q=a['year'],a['quarter'];out=[]
    try:
        rows=verify_alm_market_quarter(pages,y,q,a['source_url'],a['source_sha256']) if q<4 else parse_alm(pages,y,q,a['source_url'],a['source_sha256'])
        out.extend(rows)
        by_page=dict(pages)
        for seg in ('Private','Commercial'):
            subset=[r for r in rows if r['segment']==seg]
            page=subset[0]['source_page'];service=amount_row(by_page[page].splitlines(),'Insurance service result',3)
            for yr,idx in ((y,0),(y-1,1)):
                m={r['metric']:r['value'] for r in subset if r['year']==yr}
                if service and result_matches(m['insurance_revenue'],m['combined_ratio'],service[idx]):
                    out.append(observation(a,yr,seg,'insurance_service_result',service[idx],page))
    except Exception as exc:print('::warning::COMPANY_ALM_SEGMENT',period(y,q),str(exc)[:180],flush=True)
    try:out.extend(alm_roe_rows(a,raw))
    except Exception as exc:print('::warning::COMPANY_ALM_ROE',period(y,q),str(exc)[:180],flush=True)
    return out

def preferred(rows):
    # Latest verified comparative wins; conflicting same-document values
    # are never admitted. Direct published growth must compare the two
    # explicitly labelled columns from the very same source.
    groups={}
    for r in rows:
        groups.setdefault(key(r),[]).append(r)
    out=[]
    for rr in groups.values():
        latest=max(rr,key=lambda r:(int(r['source_document_period'][3:]),int(r['source_document_period'][1])))
        same=[r for r in rr if r['source_document_period']==latest['source_document_period']]
        if len({(r['value'],r['unit']) for r in same})==1:out.append(latest)
    return out

def add_aggregates(rows):
    """Only additive amounts may be summed from a complete quarter series."""
    out=list(rows);index={key(r):r for r in rows}
    for c,y,scope,seg in sorted({(r['company'],r['year'],r['scope'],r.get('segment') or '') for r in rows}):
        for metric in ('insurance_revenue','insurance_service_result'):
            for q in (1,2,3,4):
                k=(c,y,q,'ytd',scope,seg or None,metric)
                if k in index:continue
                parts=[index.get((c,y,i,'quarter',scope,seg or None,metric)) for i in range(1,q+1)]
                if any(p is None for p in parts) or len({p['unit'] for p in parts})!=1:continue
                last=parts[-1]
                row={**last,'period_type':'ytd','value':sum(p['value'] for p in parts),'status':'calculated','calculation':'sum_of_complete_same_segment_quarters','source_documents':[{k:p[k] for k in ('source_url','source_sha256','source_page','value','year','quarter')} for p in parts]}
                out.append(row);index[k]=row
    # Same-document Norwegian total from the two named geographic segments.
    for y,q,kind,metric in {(r['year'],r['quarter'],r['period_type'],r['metric']) for r in out if r['company']=='Gjensidige' and r['segment'] in ('Private Norway','Commercial Norway') and r['metric'] in ('insurance_revenue','insurance_service_result')}:
        parts=[index.get(('Gjensidige',y,q,kind,'reported_segment',s,metric)) for s in ('Private Norway','Commercial Norway')]
        if any(p is None for p in parts) or len({p['unit'] for p in parts})!=1:continue
        row={**parts[0],'scope':'norway','segment':None,'value':sum(p['value'] for p in parts),'status':'calculated','calculation':'sum_of_reported_norway_pm_bm','source_documents':[{k:p[k] for k in ('source_url','source_sha256','source_page','value','year','quarter')} for p in parts]}
        out.append(row)
    return preferred(out)

def build(feed,extended,registry,history,previous):
    from ingest_official_pdf import download
    from build_market_overview_segments import read_pages
    known=feed.get('observations',[]);cache=dict(previous.get('documents',{})) if previous.get('schema_version')==SCHEMA else {}
    tasks={}
    for c in TARGETS:
        obs=[r for r in known if r.get('company')==c and r.get('scope')=='group' and r.get('period_type')=='quarter' and r.get('metric')=='insurance_revenue' and r.get('source_type')=='official_quarterly_report' and trusted(c,r.get('source_url')) and re.fullmatch(r'[0-9a-f]{64}',r.get('source_sha256',''))]
        if not obs:continue
        year,q=max((r['year'],r['quarter']) for r in obs)
        desired={(year,q),(year-1,q)}
        if c=='Sampo':desired|={(yr,i) for yr in (year,year-1) for i in range(1,q+1)}
        for y,quarter in desired:
            candidates=[r for r in obs if r.get('source_document_period',period(r['year'],r['quarter']))==period(y,quarter) or (not r.get('source_document_period') and (r['year'],r['quarter'])==(y,quarter))]
            candidates.sort(key=lambda r:(r['year']!=y,r['quarter']!=quarter))
            if not candidates:continue
            src=candidates[0]
            tasks[(c,y,quarter)]={**src,'year':y,'quarter':quarter}
    alm=extended.get('insurers',{}).get(ALM,{})
    if type(alm.get('year')) is int and alm.get('quarter') in (1,2,3,4):
        y,q=alm['year'],alm['quarter']
        sources={**registry,**{d['source_document_period']:d for d in history.get('documents',{}).values() if d.get('company')==ALM}}
        sources[period(y,q)]=alm
        # Historical report URL from the issuer's official exchange filing
        # (29 January 2026). This is a locator, not a stored financial value.
        # Subsequent reports continue to use normal issuer discovery.
        if not sources.get('Q4 2025'):
            sources['Q4 2025']={'source_url':'https://attachment.news.eu.nasdaq.com/a16543ea4df576c1160f6463fcbcc0837'}
        desired={(yr,i) for yr in (y,y-1) for i in range(1,q+1)}
        # The five-quarter chart also needs the preceding full-year report.
        desired.add((y-1,4))
        for yr,i in desired:
            src=sources.get(period(yr,i),{})
            # The history dictionary is keyed by hash; recover it when needed.
            if not src.get('source_sha256'):
                match=[sha for sha,d in history.get('documents',{}).items() if d.get('company')==ALM and d.get('source_document_period')==period(yr,i) and d.get('source_url')==src.get('source_url')]
                if len(match)==1:src={**src,'source_sha256':match[0]}
            tasks[(ALM,yr,i)]={**src,'company':ALM,'year':yr,'quarter':i}
    def collect(task):
        (company,y,q),a=task;label=period(y,q);cachekey=company+'/'+label
        old=cache.get(cachekey,{})
        if old.get('complete') and old.get('observations') and (not a.get('source_sha256') or old.get('source_sha256')==a['source_sha256']):return cachekey,old
        try:
            if company==ALM:
                from alm_brand_live_pdf import download_report
                fetch=download_report
                urls=[a['source_url']] if trusted(company,a.get('source_url')) else []
                if not urls:
                    from alm_brand_report_discovery import discover
                    urls=[d['url'] for d in discover(y,q) if d.get('document_type')=='quarterly_report' and trusted(company,d.get('url'))]
            else:
                fetch=download
                urls=[a['source_url']]
            results={}
            for url in list(dict.fromkeys(urls))[:5]:
                try:
                    raw=fetch(url);sha=hashlib.sha256(raw).hexdigest()
                    if not raw.startswith(b'%PDF-') or (a.get('source_sha256') and sha!=a['source_sha256']):raise ValueError('Official document fingerprint mismatch')
                    anchor={**a,'source_url':url,'source_sha256':sha}
                    pages=read_pages(raw)
                    if company=='Gjensidige':batch=gj_rows(anchor,pages)
                    elif company=='Tryg':batch=tryg_rows(anchor,pages)
                    elif company=='Sampo':batch=sampo_rows(anchor,pages,known)
                    else:batch=alm_rows(anchor,pages,raw)
                    batch=preferred(batch)
                    if batch:results[sha]={'source_url':url,'source_sha256':sha,'observations':batch}
                except Exception as exc:print('::warning::COMPANY_SEGMENT_SOURCE',company,label,str(exc)[:200],flush=True)
            if len(results)==1:
                entry=next(iter(results.values()))
                rows=entry['observations']
                # Incomplete ROE/segment extraction is retried, not silently
                # frozen. Keep original data from a previously verified entry.
                segments=('Private','Commercial') if company!= 'Sampo' else ('Private Nordic','Nordic Commercial')
                required=('insurance_revenue',) if company=='Sampo' else ('insurance_revenue','insurance_service_result')
                entry['complete']=all(any(r['year']==yr and r['segment']==seg and r['metric']==k and r['period_type']=='quarter' for r in rows) for yr in (y,y-1) for seg in segments for k in required) and (company!=ALM or any(r['metric']=='return_on_equity' and r['year']==y for r in rows))
                print('COMPANY_DETAIL_REPORT',company,label,[(r['year'],r['period_type'],r['segment'],r['metric'],r['value']) for r in rows if r['metric'] in ('insurance_revenue','insurance_service_result','return_on_equity')],flush=True)
                return cachekey,entry
        except Exception as exc:print('::warning::COMPANY_DETAIL_REPORT',company,label,str(exc)[:220],flush=True)
        return cachekey,old if old.get('observations') and (not a.get('source_sha256') or old.get('source_sha256')==a['source_sha256']) else None
    with ThreadPoolExecutor(max_workers=5) as pool:
        for k,v in pool.map(collect,tasks.items()):
            if v:cache[k]=v
            else:cache.pop(k,None)
    result=add_aggregates(preferred([r for d in cache.values() for r in d.get('observations',[])]))
    return {'schema_version':SCHEMA,'documents':cache,'observations':result}
