#!/usr/bin/env python3
"""Extract business-line rows for the market view from existing official PDFs.

This supplementary view never mutates the verified financial feed. Each row
must be from a period-specific section with an exact current/prior-year header.
A failure leaves the segment unavailable instead of borrowing a group value.
"""
import hashlib
import io
import json
import math
import re
from pathlib import Path
from urllib.parse import urlsplit

ROOT=Path(__file__).resolve().parents[1]
TARGET=ROOT/'data/market_overview_segments.json'
COMPANIES=('Tryg','Gjensidige')
SEGMENTS=('Private','Commercial')
METRICS=('insurance_revenue','combined_ratio','loss_ratio','expense_ratio')
LABELS={
    'Tryg':{'insurance_revenue':'Insurance revenue','combined_ratio':'Combined ratio',
            'loss_ratio':'Claims ratio, net of reinsurance','expense_ratio':'Expense ratio'},
    'Gjensidige':{'insurance_revenue':'Insurance revenue','combined_ratio':'Combined ratio',
                  'loss_ratio':'Loss ratio, net of reinsurance','expense_ratio':'Cost ratio'}
}
NUMBER=r'[-−]?\d[\d,]*(?:\.\d+)?'
HOSTS={'Tryg':{'tryg.com','www.tryg.com'},
       'Gjensidige':{'mb.cision.com','www.gjensidige.com','gjensidige.com','www.gjensidige.se'}}

def norm(s):
    return ' '.join(s.replace('\u00a0',' ').replace('−','-').split())

def read_pages(blob):
    import pdfplumber
    if not blob.startswith(b'%PDF-') or len(blob)>60_000_000:raise ValueError('Invalid report PDF')
    with pdfplumber.open(io.BytesIO(blob)) as pdf:
        if len(pdf.pages)>400:raise ValueError('Report page limit exceeded')
        return [(i+1,p.extract_text(layout=False) or '') for i,p in enumerate(pdf.pages)]

def values(lines,company,count):
    result={}
    for metric,label in LABELS[company].items():
        pattern=r'^'+re.escape(label)+r'(?:[¹²³⁴⁵⁶⁷⁸⁹⁰*]+|[a-z]\))?\s+(.+)$'
        found=[]
        for line in lines:
            m=re.fullmatch(pattern,norm(line),re.I)
            if not m:continue
            tail=m[1]
            # No nearby narrative, chart labels or alternative ratio rows.
            if not re.fullmatch(r'(?:'+NUMBER+r'\s*%?\s*){'+str(count)+r'}',tail):continue
            parts=re.findall(NUMBER,tail)
            if len(parts)==count:found.append([float(v.replace(',','').replace('−','-')) for v in parts])
        if len(found)!=1:raise ValueError('Missing/ambiguous '+company+' '+metric)
        result[metric]=found[0]
    return result

def tryg_header(lines,year,quarter):
    for i,line in enumerate(lines):
        pairs=re.findall(r'\bQ([1-4])\s+(20\d{2})\b',line)
        if not pairs and i+1<len(lines):
            qs=re.findall(r'\bQ([1-4])\b',line)
            ys=re.findall(r'\b20\d{2}\b',lines[i+1])
            if len(qs)==len(ys) and len(qs)>=5:pairs=list(zip(qs,ys))
        if len(pairs)>=5 and len(set(pairs))==len(pairs) and (str(quarter),str(year)) in pairs and (str(quarter),str(year-1)) in pairs:
            return pairs
    return []

def emit(company,segment,values_,year,quarter,url,digest,page,positions):
    out=[]
    for yr,idx in positions:
        v={k:x[idx] for k,x in values_.items()}
        if not all(math.isfinite(x) for x in v.values()) or v['insurance_revenue']<=0:
            raise ValueError('Invalid segment income')
        if min(v[k] for k in METRICS[1:])<0 or v['combined_ratio']>250 or v['expense_ratio']>100 or abs(v['combined_ratio']-v['loss_ratio']-v['expense_ratio'])>.21:
            raise ValueError('Segment ratio reconciliation failed')
        for metric in METRICS:
            out.append(dict(company=company,year=yr,quarter=quarter,scope='reported_segment',segment=segment,
                period_type='quarter',metric=metric,value=v[metric],
                unit=('MDKK' if company=='Tryg' else 'MNOK') if metric=='insurance_revenue' else 'percent',
                status='reported',source_type='official_quarterly_report',source_url=url,source_sha256=digest,
                source_page=page,source_document_period=f'Q{quarter} {year}',
                source_section=('Quarterly outline - Segments / ' if company=='Tryg' else 'General Insurance ')+segment))
    return out

def parse_tryg(pages,year,quarter,url,digest):
    candidates=[]
    for page,text in pages:
        lines=[norm(l) for l in text.splitlines()]
        if not any(re.fullmatch(r'Quarterly outline\s*[-–]\s*Segments',l,re.I) for l in lines):continue
        if not any(re.search(r'\bDKKm\b',l) for l in lines):continue
        positions={seg:[i for i,l in enumerate(lines) if l.casefold()==seg.casefold()] for seg in SEGMENTS}
        if any(len(x)!=1 for x in positions.values()):continue
        private,commercial=(positions[s][0] for s in SEGMENTS)
        if private>=commercial:continue
        pairs=tryg_header(lines[:private],year,quarter)
        if not pairs:continue
        stop=next((i for i in range(commercial+1,len(lines)) if re.match(r'^(?:IFRS 3 adjustment|Group items|Tryg total|Quarterly outline)',lines[i],re.I)),len(lines))
        blocks={'Private':lines[private+1:commercial],'Commercial':lines[commercial+1:stop]}
        parsed=[]
        for seg in SEGMENTS:
            v=values(blocks[seg],'Tryg',len(pairs))
            parsed.extend(emit('Tryg',seg,v,year,quarter,url,digest,page,
                [(year,pairs.index((str(quarter),str(year)))),(year-1,pairs.index((str(quarter),str(year-1))))]))
        candidates.append(parsed)
    if len(candidates)!=1:raise ValueError('Unique Tryg Private/Commercial quarterly outline not found')
    return candidates[0]

def gjensidige_header(lines,year,quarter):
    # First two columns must be the explicitly dated, isolated quarter.
    # Q1 reports may omit separate YTD columns; otherwise allow 4 or 5.
    for i,line in enumerate(lines):
        joined=' '.join(lines[i:i+2])
        pairs=re.findall(r'\bQ([1-4])\s+(20\d{2})\b',joined,re.I)
        if not pairs:
            qs=re.findall(r'\bQ([1-4])\b',line)
            ys=re.findall(r'\b20\d{2}\b',lines[i+1]) if i+1<len(lines) else []
            if len(qs)==len(ys):pairs=list(zip(qs,ys))
        if pairs[:2]==[(str(quarter),str(year)),(str(quarter),str(year-1))]:
            return True
    return False

def parse_gjensidige(pages,year,quarter,url,digest):
    found={seg:[] for seg in SEGMENTS}
    active=None
    for page,text in pages:
        lines=[norm(l) for l in text.splitlines()]
        # The report may place the financial table on the page immediately
        # following the segment heading. Geography headings reset the scope.
        headers=[m.group(1).strip() for l in lines
            if (m:=re.fullmatch(r'General Insurance (Private(?: Norway| Denmark)?|Commercial(?: Norway| Denmark)?|Sweden)',l,re.I))]
        if len(set(headers))>1:active=None;continue
        if headers:active=headers[0].title()
        elif any(re.fullmatch(r'(?:Pension|Management of the investment portfolio|Group highlights|Consolidated financial statement|Notes and key figures)',l,re.I) for l in lines):
            active=None
        if active not in SEGMENTS:continue
        if not gjensidige_header(lines,year,quarter):continue
        if not any(re.search(r'\bNOK millions\b',l,re.I) for l in lines):continue
        options=[]
        for count in ((2,3,4,5) if quarter==1 else (4,5)):
            try:options.append(values(lines,'Gjensidige',count))
            except ValueError:pass
        if len(options)!=1:continue
        found[active].append(emit('Gjensidige',active,options[0],year,quarter,url,digest,page,[(year,0),(year-1,1)]))
    if any(len(found[s])!=1 for s in SEGMENTS):
        raise ValueError('Unique Gjensidige group PM/BM tables not found: '+repr({k:len(v) for k,v in found.items()}))
    return [r for s in SEGMENTS for r in found[s][0]]

def anchors(feed):
    rows=feed.get('observations',[])
    for company in COMPANIES:
        current=[r for r in rows if r.get('company')==company and r.get('scope')=='group'
            and r.get('period_type')=='quarter' and r.get('metric')=='insurance_revenue'
            and r.get('source_type')=='official_quarterly_report' and r.get('status') in ('reported','calculated')
            and re.fullmatch(r'[0-9a-f]{64}',r.get('source_sha256',''))]
        if not current:continue
        y,q=max((r['year'],r['quarter']) for r in current)
        candidates=[r for r in current if (r['year'],r['quarter'])==(y,q)]
        if len(candidates)!=1:raise ValueError('Ambiguous original report anchor: '+company)
        yield candidates[0]

def valid_batch(batch,anchor):
    if not isinstance(batch,list) or len(batch)!=16:return False
    year,q=anchor['year'],anchor['quarter']
    keys=set()
    for r in batch:
        if (r.get('company')!=anchor['company'] or r.get('source_url')!=anchor['source_url']
            or r.get('source_sha256')!=anchor['source_sha256'] or r.get('source_document_period')!=f'Q{q} {year}'
            or r.get('year') not in (year,year-1) or r.get('quarter')!=q or r.get('segment') not in SEGMENTS
            or r.get('scope')!='reported_segment' or r.get('source_type')!='official_quarterly_report'
            or r.get('period_type')!='quarter' or r.get('status')!='reported' or type(r.get('source_page')) is not int
            or r['source_page']<1 or r.get('metric') not in METRICS or type(r.get('value')) not in (int,float)
            or not math.isfinite(r['value'])):return False
        k=(r['year'],r['segment'],r['metric'])
        if k in keys:return False
        keys.add(k)
    for yr in (year,year-1):
        for seg in SEGMENTS:
            v={r['metric']:r['value'] for r in batch if r['year']==yr and r['segment']==seg}
            if set(v)!=set(METRICS) or v['insurance_revenue']<=0 or abs(v['combined_ratio']-v['loss_ratio']-v['expense_ratio'])>.21:return False
    return True

def download(anchor):
    url=anchor['source_url'];host=urlsplit(url).hostname
    if urlsplit(url).scheme!='https' or host not in HOSTS[anchor['company']]:raise ValueError('Unapproved original report host')
    if anchor['company']=='Tryg':
        from import_tryg import download_tryg_report
        return download_tryg_report(url,anchor['quarter'])
    from ingest_official_pdf import download as get
    return get(url)

def build(feed,previous=None,fetcher=download,reader=read_pages):
    old=(previous or {}).get('observations',[])
    out={'schema_version':1,'observations':[],'status':{}}
    for a in anchors(feed):
        c,y,q=a['company'],a['year'],a['quarter']
        batch=[r for r in old if r.get('company')==c and r.get('source_document_period')==f'Q{q} {y}']
        if not valid_batch(batch,a):
            try:
                raw=fetcher(a)
                if hashlib.sha256(raw).hexdigest()!=a['source_sha256']:raise ValueError('Original PDF fingerprint differs from verified feed')
                parser=parse_tryg if c=='Tryg' else parse_gjensidige
                batch=parser(reader(raw),y,q,a['source_url'],a['source_sha256'])
                if not valid_batch(batch,a):raise ValueError('Segment provenance not complete')
            except Exception as exc:
                print('::warning::MARKET_SEGMENTS_UNAVAILABLE',c,y,q,type(exc).__name__,str(exc)[:220],flush=True)
                out['status'][c]={'period':f'Q{q} {y}','status':'not_verified'}
                continue
        out['observations'].extend(batch)
        out['status'][c]={'period':f'Q{q} {y}','status':'verified','observations':len(batch)}
        print('MARKET_SEGMENTS_VERIFIED',c,y,q,[(s,next(r['value'] for r in batch if r['segment']==s and r['year']==y and r['metric']=='combined_ratio')) for s in SEGMENTS],flush=True)
    return out

def main():
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument('--require-baseline',action='store_true')
    args=parser.parse_args()
    feed=json.loads((ROOT/'data/verified_financial_feed.json').read_text(encoding='utf-8'))
    previous=json.loads(TARGET.read_text(encoding='utf-8')) if TARGET.exists() else {}
    result=build(feed,previous)
    from publish_geographic_workbooks import atomic_write
    atomic_write(TARGET,result)
    if args.require_baseline and any(result['status'].get(c,{}).get('status')!='verified' for c in COMPANIES):
        raise SystemExit('Current official Tryg/Gjensidige group segments must be verified before merge')

if __name__=='__main__':main()
