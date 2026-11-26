#!/usr/bin/env python3
"""Fremtind Holding IFRS note PM/BM: isolate amounts, not percentages.

The note only reports aggregate service expenses. It cannot identify the
loss/expense components. Keep the two missing ratios absent. Use the actual
note for each year/quarter, including the original prior-year report when
the group feed's comparison is taken from a later document.
"""
import calendar
import hashlib
import re
from pathlib import Path
from urllib.parse import urlsplit

FIELDS={'revenue':'Inntekter fra forsikringstjenester',
        'expenses':'Kostnader fra forsikringstjenester',
        'reinsurance':'Netto resultat fra gjenforsikringskontrakter',
        'result':'Resultat av forsikringstjenester'}
HOSTS={'cdn.sanity.io','www.fremtind.no','fremtind.no'}
SEGMENTS=('Private','Commercial')
METHOD='fremtind_ifrs_note_ytd_difference'

def normalize(text):
    return ' '.join(text.replace('\u00a0',' ').replace('\u202f',' ').replace('−','-').split())

def trusted(url):
    p=urlsplit(url)
    return p.scheme=='https' and p.hostname in HOSTS and not p.username and not p.password and p.path.lower().endswith('.pdf')

def identity(pages):
    heading=normalize(' '.join(t for _,t in pages[:2]))
    if not re.search(r'\bFremtind Holding\b',heading,re.I):raise ValueError('Wrong Fremtind entity')
    periods=set(re.findall(r'\bQ([1-4])\s+(20\d{2})\b',heading,re.I))
    periods.update(re.findall(r'(?:delårsrapport|kvartalsrapport)\s+([1-4])\.?\s*kvartal\s+(20\d{2})',heading,re.I))
    if len(periods)!=1:raise ValueError('Ambiguous Fremtind report period')
    q,y=next(iter(periods))
    return int(y),int(q)

def triple(tail):
    tokens=tail.split()
    found=set()
    def walk(pos,vals):
        if len(vals)==3:
            if pos==len(tokens) and abs(vals[0]+vals[1]-vals[2])<=2:found.add(tuple(vals))
            return
        for end in range(pos+1,len(tokens)+1):
            candidate=' '.join(tokens[pos:end])
            if re.fullmatch(r'-?(?:\d{1,3}(?: \d{3})+|\d+)',candidate):
                walk(end,vals+[int(candidate.replace(' ',''))])
    walk(0,[])
    if len(found)!=1:raise ValueError('Ambiguous PM/BM/total thousand-NOK columns')
    return next(iter(found))

def parse_note(pages,year,q,url,sha):
    if not trusted(url) or not re.fullmatch(r'[0-9a-f]{64}',sha):raise ValueError('Invalid note provenance')
    if identity(pages)!=(year,q):raise ValueError('Wrong Fremtind note period')
    found=[]
    for page,text in pages:
        lines=[normalize(l) for l in text.splitlines()]
        body='\n'.join(lines)
        if not re.search(r'(?im)^Note\s+\d+[a-z]?\s*(?:\n\s*)?Segmentopplysninger\s*$',body):continue
        if not any(re.fullmatch(r'NOK\s+1\s+000\s+PM\s+BM\s+Totalt',l,re.I) for l in lines):continue
        dates=re.findall(r'\b(\d{2})\.(\d{2})\.(20\d{2})\b',body)
        expected=(str(calendar.monthrange(year,q*3)[1]).zfill(2),str(q*3).zfill(2),str(year))
        if dates and expected not in dates:continue
        raw={}
        for key,label in FIELDS.items():
            matches=[l[len(label):].strip() for l in lines if l.startswith(label+' ')]
            if len(matches)!=1:raise ValueError('Missing/ambiguous segment note row: '+label)
            raw[key]=triple(matches[0])
        for i in range(3):
            if raw['revenue'][i]<=0 or raw['expenses'][i]>0 or abs(raw['revenue'][i]+raw['expenses'][i]+raw['reinsurance'][i]-raw['result'][i])>3:
                raise ValueError('Segment note accounting does not reconcile')
        found.append({'source_url':url,'source_sha256':sha,'source_page':page,
                      'year':year,'quarter':q,'unit':'NOK 1000','basis':'IFRS 8 segment note',
                      'amounts':{seg:{k:v[i] for k,v in raw.items()} for i,seg in enumerate(SEGMENTS)}})
    if len(found)!=1:raise ValueError('Unique Fremtind cumulative segment note not found')
    return found[0]

def derive(end,before,seg):
    if end['basis']!='IFRS 8 segment note' or end['unit']!='NOK 1000':raise ValueError('Invalid end basis')
    if end['quarter']==1:
        if before is not None:raise ValueError('Q1 has zero opening flow')
    elif not before or (before['year'],before['quarter'],before['unit'],before['basis'])!=(end['year'],end['quarter']-1,end['unit'],end['basis']):
        raise ValueError('Wrong preceding cumulative quarter')
    v={k:end['amounts'][seg][k]-(before['amounts'][seg][k] if before else 0) for k in FIELDS}
    if v['revenue']<=0 or v['expenses']>0 or abs(v['revenue']+v['expenses']+v['reinsurance']-v['result'])>6:
        raise ValueError('Quarter segment amounts do not reconcile')
    cr=-(v['expenses']+v['reinsurance'])/v['revenue']*100
    if not 0<=cr<=250:raise ValueError('Invalid CR')
    return v['revenue']/1000,cr

def records(end,before,anchor):
    out=[]
    for seg in SEGMENTS:
        revenue,cr=derive(end,before,seg)
        for metric,value,unit in [('insurance_revenue',revenue,'NOKm'),('combined_ratio',cr,'percent')]:
            out.append(dict(company='Fremtind',year=end['year'],quarter=end['quarter'],scope='reported_segment',
                segment=seg,period_type='quarter',metric=metric,value=value,unit=unit,status='calculated',
                source_type='official_quarterly_report',source_url=end['source_url'],source_sha256=end['source_sha256'],
                source_page=end['source_page'],source_document_period=f"Q{end['quarter']} {end['year']}",
                source_section='Note 2 Segmentopplysninger (IFRS 8)',source_definition='IFRS 8 segment note; net CR from isolated service expenses and reinsurance',
                calculation=METHOD,market_period=f"Q{anchor['quarter']} {anchor['year']}",market_anchor={
                    'source_url':anchor['source_url'],'source_sha256':anchor['source_sha256']},
                source_documents=[end]+([before] if before else [])))
    return out

def check_batch(batch,anchor):
    if len(batch)!=8:return False
    try:
        expected=[]
        for y in (anchor['year'],anchor['year']-1):
            rows=[r for r in batch if r['year']==y]
            docs=rows[0]['source_documents']
            if len(docs)!=(1 if anchor['quarter']==1 else 2):return False
            if (docs[0]['year'],docs[0]['quarter'])!=(y,anchor['quarter']):return False
            if y==anchor['year'] and (docs[0]['source_url'],docs[0]['source_sha256'])!=(anchor['source_url'],anchor['source_sha256']):return False
            for d in docs:
                if not trusted(d['source_url']) or not re.fullmatch(r'[0-9a-f]{64}',d['source_sha256']) or type(d['source_page']) is not int or d['source_page']<1:return False
                for seg in SEGMENTS:
                    a=d['amounts'][seg]
                    if set(a)!=set(FIELDS) or any(type(v) is not int for v in a.values()) or a['revenue']<=0 or a['expenses']>0 or abs(a['revenue']+a['expenses']+a['reinsurance']-a['result'])>3:return False
            expected.extend(records(docs[0],docs[1] if len(docs)>1 else None,anchor))
        return sorted(batch,key=lambda r:(r['year'],r['segment'],r['metric']))==sorted(expected,key=lambda r:(r['year'],r['segment'],r['metric']))
    except (ValueError,KeyError,TypeError,IndexError):return False

def build_notes(feed,anchor,candidates,fetcher,reader):
    y,q=anchor['year'],anchor['quarter']
    need={(y,q),(y-1,q)}
    if q>1:need.update({(y,q-1),(y-1,q-1)})
    docs={}
    group=[r for r in feed.get('observations',[]) if r.get('company')=='Fremtind' and r.get('scope')=='group' and r.get('metric')=='insurance_revenue' and r.get('period_type')=='quarter']
    exact={a['source_url']:a for a in group if (a['year'],a['quarter']) in need and a.get('source_document_period')==f"Q{a['quarter']} {a['year']}" and re.fullmatch(r'[0-9a-f]{64}',a.get('source_sha256',''))}
    # The exact current group anchor is mandatory; a comparative PDF cannot
    # masquerade as the prior year's original note.
    exact[anchor['source_url']]=anchor
    for url,a in exact.items():
        raw=fetcher(a);sha=hashlib.sha256(raw).hexdigest()
        if sha!=a['source_sha256']:raise ValueError('Fremtind note fingerprint changed')
        pages=reader(raw);period=identity(pages)
        if period!=(a['year'],a['quarter']):raise ValueError('Fremtind group anchor has wrong note period')
        docs[period]=parse_note(pages,*period,url,sha)
    # Discovery is the existing official Holding archive, not guessed URLs.
    # Candidate year labels may be broad; verify the actual PDF cover/date.
    for c in candidates:
        if need.issubset(docs):break
        if c.get('company')!='Fremtind' or c.get('source_entity')!='Fremtind Holding' or c.get('year') not in {a for a,b in need}:continue
        url=c.get('document_url','')
        if url in exact or not trusted(url):continue
        if c.get('archive_url')!='https://www.fremtind.no/finansiell-informasjon':continue
        try:
            raw=fetcher({'company':'Fremtind','source_url':url,'quarter':q});pages=reader(raw);period=identity(pages)
            if period not in need or period in docs:continue
            docs[period]=parse_note(pages,*period,url,hashlib.sha256(raw).hexdigest())
        except (ValueError,OSError):continue
    if not need.issubset(docs):raise ValueError('Missing original cumulative segment reports: '+repr(sorted(need-set(docs))))
    batch=[]
    for yr in (y,y-1):batch.extend(records(docs[(yr,q)],docs[(yr,q-1)] if q>1 else None,anchor))
    if not check_batch(batch,anchor):raise ValueError('Fremtind note calculation evidence invalid')
    return batch
