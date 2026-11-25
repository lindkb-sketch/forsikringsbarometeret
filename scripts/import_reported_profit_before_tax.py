#!/usr/bin/env python3
"""Supplement the verified group feed with explicitly reported pre-tax profit.

Never substitute net income, operating profit, segment profit or tax expense.
Use the source already verified by the issuer importer, its report period and
document fingerprint. A changed/ambiguous layout leaves the metric missing.
"""
import hashlib
import io
import json
import math
import re
from urllib.parse import urlsplit

import pdfplumber
from audit_financials import DATA, audit
from ingest_official_pdf import download
from import_frende_holding import read as read_frende, TableReader, number as frende_number
from publish_geographic_workbooks import atomic_write

COMPANIES = ('Fremtind','Gjensidige','Tryg','Frende','Protector','Storebrand')
LABELS = {
    'Fremtind': r'Resultat før skatt(?:ekostnad)?',
    'Gjensidige': r'Profit or loss before tax expense',
    'Tryg': r'(?:Profit/loss|Profit|Result) before tax(?:es)?',
    'Protector': r'Profit\s*/\s*\(loss\) before tax',
    'Storebrand': r'Profit before income tax',
}
GROUP_MARKERS = {
    'Fremtind': ('Resultatutvikling og nøkkeltall','Inntekter fra forsikringstjenester'),
    'Gjensidige': ('Insurance revenue from general insurance','Insurance service result general insurance','NOK millions'),
    'Tryg': ('Income overview','Insurance revenue','Insurance service result'),
    'Protector': ('Income overview','Insurance revenue','Insurance service result','NOKm'),
}
UNITS = {'Fremtind':'NOKm','Gjensidige':'MNOK','Tryg':'MDKK','Protector':'MNOK','Storebrand':'MNOK','Frende':'NOKm'}
ENTITIES = {'Fremtind':'Fremtind Holding konsern','Gjensidige':'Gjensidige Group',
            'Tryg':'Tryg Group','Protector':'Protector Forsikring ASA',
            'Storebrand':'Storebrand ASA / consolidated Group','Frende':'Frende Holding AS konsern'}
ENG_CELL = re.compile(r'\(?[-\u2212]?\d[\d,]*(?:\.\d+)?\)?')
NOR_CELL = re.compile(r'-?(?:\d{1,3}(?: \d{3})+|\d+)(?:,\d+)?')
FOOT = r'(?:[¹²³⁴⁵⁶⁷⁸⁹⁰*]+|[a-z]\))?'

def _value(token, norwegian=False):
    token=token.replace('\u2212','-')
    negative=token.startswith('(') and token.endswith(')')
    token=token.strip('()').replace(' ','')
    val=float(token.replace(',','.') if norwegian else token.replace(',',''))
    return -val if negative else val

def _cells(tail,count,norwegian=False):
    tokens=tail.replace('\u00a0',' ').split()
    if not norwegian:
        if len(tokens)!=count or not all(ENG_CELL.fullmatch(t) for t in tokens):
            return None
        return tuple(_value(t) for t in tokens)
    def partitions(start,values):
        if len(values)==count:
            if start==len(tokens):yield tuple(values)
            return
        for stop in range(start+1,len(tokens)+1):
            candidate=' '.join(tokens[start:stop])
            if NOR_CELL.fullmatch(candidate):
                yield from partitions(stop,values+[_value(candidate,True)])
    options=set(partitions(0,[]))
    return next(iter(options)) if len(options)==1 else None

def _row(lines,label,count,norwegian=False):
    matches=[]
    for line in lines:
        m=re.fullmatch(r'\s*'+label+FOOT+r'\s+(.+?)\s*',line,re.I)
        if m:
            vals=_cells(m.group(1),count,norwegian)
            if vals is not None:matches.append((vals,line.strip()))
    if len(matches)!=1:
        raise ValueError('Missing or ambiguous '+label+'; candidates='+repr(
            [x.strip()[:200] for x in lines if re.search(label,x,re.I)][:5]))
    return matches[0]

def _period_header(lines,year,quarter):
    """Only the current quarter then prior-year quarter, then cumulative period."""
    normalized=' '.join(lines).replace('–','-').replace('−','-')
    # Header may place years on a separate physical line (Tryg).
    if not (re.search(r'\bQ\s*'+str(quarter)+r'\b',normalized,re.I)
            and str(year) in normalized and str(year-1) in normalized):
        return False
    if quarter==1:return True
    return bool(re.search(r'Q1\s*-\s*Q'+str(quarter)+r'\b|'
        r'\b(?:YTD|HIÅ|Hittil i år|H1|9M|FY)\b|'
        r'\b(?:01\.01|1\.1)\s*-\s*|'
        r'\b(?:30\.06|30\.09|31\.12)\b',normalized,re.I))

def _observation(anchor,period,value,page,digest,label,source_url=None):
    return dict(company=anchor['company'],year=anchor['year'],quarter=anchor['quarter'],
        scope='group',source_scope='group',period_type=period,metric='profit_before_tax',
        value=value,unit=UNITS[anchor['company']],status='reported',
        source_type='official_quarterly_report',source_url=source_url or anchor['source_url'],
        source_page=page,source_sha256=digest,source_document_period=f"Q{anchor['quarter']} {anchor['year']}",
        source_definition=label,source_entity=ENTITIES[anchor['company']])

def parse_pdf(pages,anchor,digest):
    company=anchor['company'];year=anchor['year'];q=anchor['quarter']
    if company not in LABELS:raise ValueError('Unsupported issuer')
    if digest!=anchor.get('source_sha256'):
        raise ValueError('Document digest differs from verified source')
    if company=='Storebrand':
        return parse_storebrand(pages,anchor,digest)
    page=anchor['source_page']
    texts=[text for p,text in pages if p==page]
    if len(texts)!=1 or not all(m in texts[0] for m in GROUP_MARKERS[company]):
        raise ValueError('Verified group table not found on source page')
    lines=texts[0].splitlines()
    # The header must appear above the pre-tax row, not in a footer/narrative.
    # The extracted Gjensidige page includes a neighbouring Pension row;
    # only accept a numeric group row immediately following the exact label.
    indexes=[i for i,l in enumerate(lines) if re.match(r'^\s*'+LABELS[company]+FOOT+r'\s+(?=[-\u2212\d(])',l,re.I)]
    if len(indexes)!=1:raise ValueError('Pre-tax row missing or ambiguous on verified group table: '+repr([l for l in lines if re.search('before tax|før skatt',l,re.I)][:8]))
    index=indexes[0]
    if not _period_header(lines[:index],year,q):
        raise ValueError('Current quarter and HIÅ columns not explicitly verified')
    counts=(3,2) if q==1 else ((4,5) if q==4 else (5,))
    candidates=[]
    for count in counts:
        try:
            # Fremtind's neighbouring two-column graphic can append its label.
            source_line=lines[index]
            if company=='Fremtind':
                source_line=re.sub(r'\s+segment\s*\(%\)\s*$','',source_line,flags=re.I)
            vals,label=_row([source_line],LABELS[company],count,company=='Fremtind')
            candidates.append((vals,label))
        except ValueError:continue
    if len(candidates)!=1:raise ValueError('Pre-tax financial columns ambiguous: '+repr(lines[index]))
    vals,label=candidates[0]
    return [_observation(anchor,'quarter',vals[0],page,digest,'Reported group profit before tax'),
            _observation(anchor,'ytd',vals[0] if q==1 else vals[2],page,digest,'Reported group profit before tax; year-to-date')]

def parse_storebrand(pages,anchor,digest):
    """Storebrand's consolidated Group income statement, not insurance APM."""
    year=anchor['year'];q=anchor['quarter']; hits=[]
    for page,text in pages:
        # Require consolidated group statement markers, excluding the parent-only
        # Storebrand ASA statement and the insurance segment APM table.
        if not (re.search(r'Storebrand Group',text,re.I) and re.search(r'Income statement',text,re.I)
                and 'Net insurance service result' in text and 'Tax expenses' in text
                and 'NOK million' in text):
            continue
        lines=text.splitlines()
        indexes=[i for i,l in enumerate(lines) if re.match(r'^\s*'+LABELS['Storebrand']+FOOT+r'\s+',l,re.I)]
        if len(indexes)!=1:continue
        i=indexes[0]
        if not _period_header(lines[:i],year,q):continue
        for count in ((3,2) if q==1 else ((4,5) if q==4 else (5,))):
            try:
                vals,_=_row([lines[i]],LABELS['Storebrand'],count)
                hits.append((page,vals))
            except ValueError:continue
    if len(hits)!=1:
        diagnostic=[(p,[l.strip()[:200] for l in t.splitlines() if re.search(r'profit before (?:income )?tax|result before tax|income statement',l,re.I)][:7]) for p,t in pages if re.search(r'profit before (?:income )?tax|result before tax',t,re.I)]
        raise ValueError('Consolidated Storebrand Group pre-tax quarter/HIÅ table not uniquely verified: '+repr(diagnostic[:5]))
    page,vals=hits[0]
    return [_observation(anchor,'quarter',vals[0],page,digest,'Storebrand Group consolidated profit before tax (not insurance segment)'),
            _observation(anchor,'ytd',vals[0] if q==1 else vals[2],page,digest,'Storebrand Group consolidated profit before tax; HIÅ (not insurance segment)')]

def parse_frende(html,anchor):
    year=anchor['year'];q=anchor['quarter']
    if 'Nøkkeltall konsern' not in html:raise ValueError('Wrong Frende group report section')
    parser=TableReader();parser.feed(html)
    if not parser.rows:raise ValueError('Missing Frende group KPI table')
    header=parser.rows[0]
    if header[:2]!=['Tall i 1000',f'Q{q} {year}']:raise ValueError('Wrong Frende KPI header')
    matches=[r for r in parser.rows[1:] if r and r[0]=='Resultat før skatt']
    if len(matches)!=1:raise ValueError('Missing or ambiguous Frende group profit before tax row')
    row=matches[0]
    cols=[('quarter',1)]
    if q==1:cols.append(('ytd',1))
    else:
        labels=(f'Pr Q{q} {year}',str(year)) if q==4 else (f'Pr Q{q} {year}',)
        matches=[i for i,h in enumerate(header) if h in labels]
        if len(matches)!=1:raise ValueError('Missing or ambiguous Frende HIÅ column')
        cols.append(('ytd',matches[0]))
    base=anchor['source_url'].rsplit('/sec/',1)[0]
    return [_observation(anchor,period,frende_number(row[col])/1000,6,
            hashlib.sha256(html.encode('utf-8')).hexdigest(),'Resultat før skatt; konsern, NOK 1 000 omregnet til millioner',base+'/sec/6')
            for period,col in cols]

def choose_anchors(rows):
    candidates={}
    latest_by_url={}
    for r in rows:
        if r.get('scope')=='group' and r.get('metric')=='insurance_revenue' and r.get('period_type')=='quarter' and r.get('source_url'):
            key=(r['company'],r['source_url'])
            latest_by_url[key]=max(latest_by_url.get(key,(0,0)),(r['year'],r['quarter']))
    for r in rows:
        if (r.get('company') not in COMPANIES or r.get('scope')!='group'
            or r.get('metric')!='insurance_revenue' or r.get('period_type')!='quarter'
            or r.get('status') not in ('reported','calculated')
            or r.get('source_type')!='official_quarterly_report' or r.get('year',0)<2025):
            continue
        # Avoid assigning comparatives from a more recent document to earlier periods.
        period=r.get('source_document_period')
        if period and period!=f"Q{r['quarter']} {r['year']}":continue
        if not period and latest_by_url.get((r['company'],r['source_url']))!=(r['year'],r['quarter']):continue
        key=(r['company'],r['year'],r['quarter'])
        candidates.setdefault(key,[]).append(r)
    return [v[0] for _,v in sorted(candidates.items()) if len(v)==1]

def ingest(anchor):
    company=anchor['company'];url=anchor['source_url']
    if company=='Frende':
        return parse_frende(read_frende(url.rsplit('/sec/',1)[0],6),anchor)
    if not url.startswith('https://'):raise ValueError('Untrusted report source')
    blob=download(url)
    digest=hashlib.sha256(blob).hexdigest()
    with pdfplumber.open(io.BytesIO(blob)) as pdf:
        pages=[(i+1,p.extract_text() or '') for i,p in enumerate(pdf.pages)]
    return parse_pdf(pages,anchor,digest)

def run(path=DATA, historical=False):
    data=json.loads(path.read_text(encoding='utf-8'))
    rows=data['observations']
    if not audit(data)['ok']:raise ValueError('Baseline financial audit failed')
    existing={(r['company'],r['year'],r['quarter'],r['period_type']) for r in rows
              if r.get('scope')=='group' and r.get('metric')=='profit_before_tax'}
    added=[];missing=[]
    anchors=choose_anchors(rows)
    if not historical:
        latest={}
        for anchor in anchors:
            c=anchor['company']
            if c not in latest or (anchor['year'],anchor['quarter'])>(latest[c]['year'],latest[c]['quarter']):latest[c]=anchor
        anchors=list(latest.values())
    for anchor in anchors:
        key=(anchor['company'],anchor['year'],anchor['quarter'])
        if all((*key,p) in existing for p in ('quarter','ytd')):continue
        try:
            for row in ingest(anchor):
                k=(*key,row['period_type'])
                if k not in existing:
                    added.append(row);existing.add(k)
        except (ValueError,OSError,TimeoutError) as exc:
            missing.append({'company':key[0],'period':f'Q{key[2]} {key[1]}','error':str(exc)[:500]})
            print('::warning::PRETAX_UNVERIFIED',key,str(exc)[:500],flush=True)
    if added:
        result={**data,'observations':rows+added,'metrics':list(dict.fromkeys([*data.get('metrics',[]),'profit_before_tax']))}
        checked=audit(result)
        if not checked['ok']:raise ValueError('Pre-tax financial audit failed: '+repr(checked['errors'][:5]))
        atomic_write(path,result)
    print('PRETAX_IMPORT',json.dumps({'added':len(added),'unverified':missing},ensure_ascii=False),flush=True)
    return added

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument('--historical',action='store_true')
    args=parser.parse_args()
    run(historical=args.historical)
