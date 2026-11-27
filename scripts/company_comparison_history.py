"""Fill explicit prior-period group comparison gaps from the original PDFs.

The primary verified financial feed remains authoritative. Supplementary
rows are used only in the company view and are never hardcoded estimates.
"""
import hashlib,re
from concurrent.futures import ThreadPoolExecutor

SCHEMA=2
TARGETS=('Fremtind','Gjensidige','Tryg','Protector','Sampo')
CORE=('insurance_revenue','insurance_service_result','combined_ratio','loss_ratio','expense_ratio')
def key(r):return tuple(r.get(k) for k in ('company','year','quarter','period_type','scope','metric'))
def return_comparatives(pages,a,quarter_values):
    """Explicit period columns; never compare an isolated return with HIÅ."""
    from import_group_ytd import obs,ytd_header,parse_values,check_quarter
    company,y,q=a['company'],a['year'],a['quarter']
    hits=[]
    for page,t in pages:
        lines=t.splitlines()
        if company=='Fremtind':
            if not re.search(r'Resultatutvikling og nøkkeltall',t,re.I):continue
            for i,line in enumerate(lines):
                if not re.search(r'annualisert\s+egenkapitalavkastning\s+justert\s+for',' '.join(lines[max(0,i-5):i+1]),re.I):continue
                m=re.search(r'transaksjonen\s+med\s+Eika\s*Forsikring\s+AS\s+((?:-?\d+(?:,\d+)?\s*%\s*)+)',line,re.I)
                if not m:continue
                header=ytd_header(lines[:i],y,q)
                if not header:continue
                count,qcol,ycol,pcol=header
                vals=parse_values(m[1],count,norwegian=True)
                if vals is None:continue
                check_quarter('return_on_equity',vals[qcol],quarter_values)
                hits.append((page,vals[ycol],vals[pcol]))
        elif company=='Gjensidige':
            # The APM table has empty quarter cells on this ROE row.
            # Require the group-specific table title, period header and
            # precisely three annualised YTD/prior/FY values.
            if not re.search(r'Other alternative performance measures and key figures',t,re.I):continue
            group=re.split(r'(?im)^\s*Gjensidige Forsikring ASA\s*$',t,maxsplit=1)[0]
            if not re.search(r'Gjensidige Forsikring Group',group,re.I):continue
            compact=' '.join(group.split())
            if not re.search(rf'Q{q}\s+{y}\s+Q{q}\s+{y-1}\s+(?:YTD|HIÅ)\s+{y}\s+(?:YTD|HIÅ)\s+{y-1}\s+(?:FY\s+)?{y-1}',compact,re.I):continue
            for line in group.splitlines():
                m=re.fullmatch(r'\s*Return on equity,\s*annualis(?:ed|z)(?:\s*[¹²³⁴⁵*]+)?\s*%\s+(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)\s*',line,re.I)
                if m:hits.append((page,float(m[1]),float(m[2])))
    if len({(a,b) for _,a,b in hits})!=1:raise ValueError('Explicit return comparison table not unique')
    page,current,prior=hits[0]
    if not all(-100<=x<=200 for x in (current,prior)):raise ValueError('Invalid annualised return')
    definition='Annualisert egenkapitalavkastning justert for transaksjonen med Eika Forsikring AS; HIÅ' if company=='Fremtind' else 'ROE annualised; issuer explicitly reports year-to-date'
    return [obs(a,'return_on_equity',y,current,page,definition),obs(a,'return_on_equity',y-1,prior,page,definition+' (explicit prior-year HIÅ comparative)')]

def build(feed,previous):
    from ingest_official_pdf import download
    from build_market_overview_segments import read_pages
    from import_group_ytd import returns,sampo,protector,obs
    from import_group_solvency_pdf import extract as solvency
    from sampo_group_kpis import parse_overview
    from urllib.parse import urlsplit
    rows=[r for r in feed.get('observations',[]) if r.get('scope')=='group' and r.get('source_type')=='official_quarterly_report' and r.get('status') in ('reported','calculated') and re.fullmatch(r'[0-9a-f]{64}',r.get('source_sha256','')) and isinstance(r.get('value'),(int,float))]
    hosts={'Fremtind':('cdn.sanity.io','live.euronext.com','fremtind.no','www.fremtind.no'),
           'Gjensidige':('gjensidige.no','gjensidige.com','www.gjensidige.no','www.gjensidige.com','www.gjensidige.se','mb.cision.com','live.euronext.com'),
           'Tryg':('tryg.com','www.tryg.com'),
           'Protector':('storage.mfn.se','investor.protectorforsikring.no'),
           'Sampo':('sampo.com','www.sampo.com','attachment.news.eu.nasdaq.com')}
    cache=dict(previous.get('documents',{})) if previous.get('schema_version')==SCHEMA else {}
    tasks=[]
    for c in TARGETS:
        periods=[(r['year'],r['quarter']) for r in rows if r['company']==c and r['period_type']=='quarter' and r['metric']=='insurance_revenue']
        if not periods:continue
        year,q=max(periods)
        for y in (year,year-1):
            label=f'Q{q} {y}'
            candidates=[r for r in rows if r['company']==c and r['quarter']==q and r['metric'] in CORE and urlsplit(r.get('source_url','')).hostname in hosts[c] and r['source_url'].startswith('https://') and (r.get('source_document_period')==label or not r.get('source_document_period') and r['year']==y)]
            candidates.sort(key=lambda r:(r['metric']!='insurance_revenue',r['year']!=y))
            if not candidates:continue
            a={**candidates[0],'year':y,'quarter':q,'unit':next((r['unit'] for r in rows if r['company']==c and r['metric']=='insurance_revenue' and r['year']==y and r['quarter']==q),'EURm' if c=='Sampo' else 'MNOK')}
            tasks.append(a)
    def collect(a):
        c,y,q=a['company'],a['year'],a['quarter'];sha=a['source_sha256'];cachekey=f'{c}/Q{q} {y}/{sha}'
        existing=cache.get(cachekey)
        if existing and existing.get('observations'):return cachekey,existing
        out=[]
        try:
            raw=download(a['source_url'])
            if hashlib.sha256(raw).hexdigest()!=sha:raise ValueError('Original comparison PDF fingerprint changed')
            pages=read_pages(raw)
            # The hash was bound to the original reporting period by the
            # primary feed. Check the cover independently as well.
            head=' '.join(t for _,t in pages[:2]).lower()
            if str(y) not in head:raise ValueError('Original report year absent')
            # Same issuer and period: cross-check reported quarter columns
            # against verified quarter data before admitting HIÅ.
            quarter_values={r['metric']:r['value'] for r in rows if r['company']==c and r['year']==y and r['quarter']==q and r['period_type']=='quarter'}
            tasks=[]
            if c=='Sampo':
                tasks.extend([('core',lambda:sampo(pages,a,quarter_values)),('return',lambda:parse_overview(pages,a['source_url'],y,q,sha))])
            elif c=='Protector':
                tasks.extend([('core',lambda:protector(pages,a,quarter_values)),('return',lambda:returns(pages,a,quarter_values))])
            else:tasks.append(('return',lambda:returns(pages,a,quarter_values)))
            if c in ('Fremtind','Gjensidige'):
                tasks.append(('return_comparative',lambda:return_comparatives(pages,a,quarter_values)))
            if c in ('Tryg','Gjensidige','Protector','Sampo'):
                def sol():
                    page,val=solvency(raw,c,y,q)
                    return [obs(a,'solvency_ratio',y,val,page,'Reported quarter-end Group solvency ratio','quarter')]
                tasks.append(('solvency',sol))
            for name,run in tasks:
                try:out.extend(run())
                except Exception as exc:print('::warning::COMPANY_COMPARISON_SOURCE',c,f'Q{q} {y}',name,str(exc)[:180],flush=True)
        except Exception as exc:print('::warning::COMPANY_COMPARISON_SOURCE',c,f'Q{q} {y}',str(exc)[:180],flush=True)
        print('COMPANY_COMPARISON_REPORT',c,f'Q{q} {y}',[(r['year'],r['period_type'],r['metric'],r['value']) for r in out],flush=True)
        return cachekey,dict(observations=out)
    with ThreadPoolExecutor(max_workers=4) as pool:
        for k,v in pool.map(collect,tasks):
            if v['observations']:cache[k]=v
    observed={key(r) for r in rows}
    extra={}
    for d in cache.values():
        for r in d.get('observations',[]):
            k=key(r)
            if k not in observed:extra[k]=r
    return dict(schema_version=SCHEMA,documents=cache,observations=list(extra.values()))
