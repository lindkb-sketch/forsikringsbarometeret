#!/usr/bin/env python3
"""Fremtind PM/BM market series on the issuer's management APM basis.

Use the official quarter's *reported* CR (including its latest comparative
column), not a substitute IFRS-note CR. Isolate APM segment revenue from
cumulative tables. Prefer explicitly reported quarterly revenue growth.
Keep the claims/expense split missing. Do not invent comparative income.
"""
import calendar
import hashlib
import math
import re
from fremtind_market_segments import identity,normalize,triple,trusted

SEGMENTS=('Private','Commercial')
METHOD='fremtind_reported_apm_segment'
BASIS='Fremtind APM: adjusted insurance service revenue and reported net combined ratio'
PERCENT=r'\d{1,3}(?:[,.]\d+)?'
def n(v):return float(v.replace(',','.'))

def doc(page,url,sha,y,q):
    return dict(source_url=url,source_sha256=sha,source_page=page,year=y,quarter=q)

def parse_income(pages,y,q,url,sha):
    if identity(pages)!=(y,q) or not trusted(url):raise ValueError('Wrong APM report identity')
    dates=f'{calendar.monthrange(y,q*3)[1]:02d}.{q*3:02d}.{y}'
    found=[]
    for page,text in pages:
        body='\n'.join(normalize(l) for l in text.splitlines())
        # The APM table is in the board report, not the IFRS 8 note.
        if not re.search(r'Segmentresultater?\s*(?:[-–]\s*'+re.escape(dates)+r'|\(\s*per\s+Q'+str(q)+r'\s+'+str(y)+r'\s*\))',body,re.I):continue
        if not (re.search(r'\bMNOK\s+PM\s+BM\s+Totalt\b',body,re.I)
                or re.search(r'Privat-\s+Bedrifts-\s+MNOK\s+markedet\s+markedet\s+Totalt',body,re.I)):continue
        values=[]
        for l in body.splitlines():
            m=re.fullmatch(r'Inntekter fra forsikringstjenester\s+([0-9 ]+)',l,re.I)
            if m:values.append(triple(m[1]))
        if len(values)!=1:raise ValueError('Missing/ambiguous APM segment revenue row')
        a,b,total=values[0]
        if min(a,b,total)<=0 or abs(a+b-total)>2:raise ValueError('APM segment total does not reconcile')
        found.append({**doc(page,url,sha,y,q),'basis':BASIS,'unit':'MNOK',
                      'income':{'Private':a,'Commercial':b},'total':total})
    if len(found)!=1:raise ValueError('Unique cumulative APM segment income table not found')
    return found[0]

def parse_cr(pages,y,q,url,sha):
    if identity(pages)!=(y,q):raise ValueError('Wrong APM CR report period')
    found=[]
    for page,text in pages:
        body=normalize(text)
        if not re.search(r'\bMNOK\s+Q'+str(q)+r'\s+'+str(y)+r'\s+Q'+str(q)+r'\s+'+str(y-1)+r'\b',body,re.I):continue
        if not re.search(r'Combined ratio.{0,200}?per.{0,100}?segment\s*\(%\)',body,re.I):continue
        values={}
        for seg,label in zip(SEGMENTS,('PM','BM')):
            matches=[]
            for line in text.splitlines():
                hit=re.search(r'\b'+label+r'\s+((?:'+PERCENT+r'\s*%\s*){2,5})',normalize(line))
                if hit:
                    vals=re.findall(r'('+PERCENT+r')\s*%',hit[1])
                    if len(vals)==(3 if q==1 else 4 if q==4 else 5):matches.append([n(v) for v in vals])
            if len(matches)!=1:break
            values[seg]={'current':matches[0][0],'prior':matches[0][1]}
        if set(values)==set(SEGMENTS) and all(0<=v<=250 for row in values.values() for v in row.values()):
            found.append({**doc(page,url,sha,y,q),'basis':BASIS,'values':values})
    if len(found)!=1:raise ValueError('Unique reported quarterly PM/BM combined ratio not found')
    return found[0]

def parse_growth(pages,y,q,url,sha):
    # Scope to the board's isolated-quarter development paragraph. PDF
    # extraction can interleave neighbouring columns; only accept an
    # explicit PM and BM directional growth statement in that section.
    found=[]
    for page,text in pages:
        body=normalize(text)
        starts=list(re.finditer(r'\bResultatutvikling i kvartalet\b',body,re.I))
        for h in starts:
            tail=body[h.end():h.end()+1800]
            if not re.search(r'Inntekter fra forsikringstjenester ble',tail,re.I):continue
            pm=re.search(r'privatmarkedet har en (økning|nedgang|reduksjon) i.{0,250}?inntekter fra forsikringstjenester på\s+('+PERCENT+r')\s+prosent',tail,re.I)
            if not pm:continue
            bm=re.search(r'bedriftsmarkedet har en.{0,250}?\b(økning|nedgang|reduksjon)\s+på\s+('+PERCENT+r')\s+prosent',tail[pm.end():],re.I)
            if not bm:continue
            vals={seg:n(m[2])*(1 if m[1].lower()=='økning' else -1) for seg,m in zip(SEGMENTS,(pm,bm))}
            found.append({**doc(page,url,sha,y,q),'basis':BASIS,'values':vals})
    if len(found)>1:raise ValueError('Ambiguous reported isolated segment growth')
    return found[0] if found else None

def isolate(end,before):
    if end['basis']!=BASIS or end['unit']!='MNOK':raise ValueError('Wrong revenue basis')
    if end['quarter']==1:
        if before is not None:raise ValueError('Q1 opening flow is zero')
    elif not before or (before['year'],before['quarter'],before['basis'],before['unit'])!=(end['year'],end['quarter']-1,BASIS,'MNOK'):
        raise ValueError('Wrong preceding APM cumulative period')
    values={s:end['income'][s]-(before['income'][s] if before else 0) for s in SEGMENTS}
    if min(values.values())<=0:raise ValueError('Nonpositive isolated segment revenue')
    return values

def emit(anchor,end,before,cr,growth,old_end=None,old_before=None):
    y,q=anchor['year'],anchor['quarter']
    revenue=isolate(end,before)
    if (end['year'],end['quarter'],end['source_url'],end['source_sha256'])!=(y,q,anchor['source_url'],anchor['source_sha256']):raise ValueError('Wrong current APM report anchor')
    if (cr['year'],cr['quarter'],cr['source_url'],cr['source_sha256'])!=(y,q,anchor['source_url'],anchor['source_sha256']):raise ValueError('Wrong reported CR anchor')
    if 'value' in anchor and abs(sum(revenue.values())-anchor['value'])>3:raise ValueError('Isolated APM segment revenue differs from group income')
    prior_revenue=isolate(old_end,old_before) if old_end else None
    if old_end and (old_end['year'],old_end['quarter'])!=(y-1,q):raise ValueError('Wrong prior segment income period')
    if growth and (growth['year'],growth['quarter'],growth['source_url'],growth['source_sha256'])!=(y,q,anchor['source_url'],anchor['source_sha256']):raise ValueError('Wrong reported growth anchor')
    ev={'end':end,'before':before,'cr':cr,'growth':growth,'old_end':old_end,'old_before':old_before}
    rows=[]
    for s in SEGMENTS:
        def row(metric,val,yr,src,status,section,documents):
            rows.append(dict(company='Fremtind',year=yr,quarter=q,scope='reported_segment',segment=s,period_type='quarter',metric=metric,
                value=val,unit='NOKm' if metric=='insurance_revenue' else 'percent',status=status,source_type='official_quarterly_report',
                source_url=src['source_url'],source_sha256=src['source_sha256'],source_page=src['source_page'],
                source_document_period=f"Q{src['quarter']} {src['year']}",source_definition=BASIS,source_section=section,
                calculation=METHOD,market_period=f'Q{q} {y}',market_anchor={'source_url':anchor['source_url'],'source_sha256':anchor['source_sha256']},
                source_documents=documents,apm_evidence=ev))
        row('insurance_revenue',revenue[s],y,end,'calculated','Styrets beretning / Segmentresultater (isolert differanse)',[end]+([before] if before else []))
        for yr,key in ((y,'current'),(y-1,'prior')):
            row('combined_ratio',cr['values'][s][key],yr,cr,'reported','Resultatutvikling og nøkkeltall / Combined ratio per segment',[cr])
        if growth:
            row('insurance_revenue_growth',growth['values'][s],y,growth,'reported','Styrets beretning / Resultatutvikling i kvartalet',[growth])
        elif prior_revenue:
            row('insurance_revenue_growth',(revenue[s]/prior_revenue[s]-1)*100,y,end,'calculated','APM isolerte kvartalsinntekter; samme kvartal året før',[end]+([before] if before else [])+[old_end]+([old_before] if old_before else []))
        if prior_revenue:
            row('insurance_revenue',prior_revenue[s],y-1,old_end,'calculated','Styrets beretning / Segmentresultater (isolert differanse)',[old_end]+([old_before] if old_before else []))
    return rows

def check_apm_batch(batch,anchor):
    try:
        if not batch:return False
        evidence=batch[0]['apm_evidence']
        for name,d in evidence.items():
            if d is None:continue
            if not trusted(d['source_url']) or not re.fullmatch(r'[0-9a-f]{64}',d['source_sha256']) or type(d['source_page']) is not int or d['source_page']<1 or d['basis']!=BASIS:return False
            if name in ('end','before','old_end','old_before'):
                if set(d['income'])!=set(SEGMENTS) or any(type(v) is not int or v<=0 for v in d['income'].values()) or abs(sum(d['income'].values())-d['total'])>2:return False
            elif name=='cr':
                if set(d['values'])!=set(SEGMENTS) or any(set(v)!={'current','prior'} or any(type(x) not in (int,float) or not math.isfinite(x) or not 0<=x<=250 for x in v.values()) for v in d['values'].values()):return False
            elif name=='growth':
                if set(d['values'])!=set(SEGMENTS) or any(type(v) not in (int,float) or not math.isfinite(v) or v<=-100 for v in d['values'].values()):return False
        expected=emit(anchor,**evidence)
        key=lambda r:(r['year'],r['segment'],r['metric'])
        return sorted(expected,key=key)==sorted(batch,key=key)
    except (ValueError,KeyError,TypeError,IndexError):return False

def build_apm(feed,anchor,candidates,fetcher,reader):
    y,q=anchor['year'],anchor['quarter']
    def read(a):
        raw=fetcher(a);sha=hashlib.sha256(raw).hexdigest()
        if a.get('source_sha256') and sha!=a['source_sha256']:raise ValueError('Original Fremtind report fingerprint changed')
        pages=reader(raw)
        return pages,a['source_url'],sha
    pages,url,sha=read(anchor)
    end=parse_income(pages,y,q,url,sha)
    cr=parse_cr(pages,y,q,url,sha)
    growth=parse_growth(pages,y,q,url,sha)
    group=[r for r in feed.get('observations',[]) if r.get('company')=='Fremtind' and r.get('scope')=='group' and r.get('metric')=='insurance_revenue' and r.get('period_type')=='quarter']
    def income_for(yr,quarter):
        exact=[r for r in group if (r['year'],r['quarter'])==(yr,quarter) and r.get('source_document_period')==f'Q{quarter} {yr}' and re.fullmatch(r'[0-9a-f]{64}',r.get('source_sha256',''))]
        if len(exact)>1:raise ValueError('Ambiguous APM report anchor')
        if exact:
            pp,u,h=read(exact[0])
            return parse_income(pp,yr,quarter,u,h)
        # Prior-year original report may no longer be the main-feed source
        # after a comparative is refreshed. Use issuer archive discovery.
        for c in candidates:
            if c.get('company')!='Fremtind' or c.get('source_entity')!='Fremtind Holding' or c.get('year')!=yr or c.get('archive_url')!='https://www.fremtind.no/finansiell-informasjon' or not trusted(c.get('document_url','')):continue
            try:
                pp,u,h=read(dict(company='Fremtind',quarter=quarter,source_url=c['document_url']))
                if identity(pp)==(yr,quarter):return parse_income(pp,yr,quarter,u,h)
            except (ValueError,OSError):continue
        raise ValueError('Original APM income table unavailable')
    before=income_for(y,q-1) if q>1 else None
    old_end=old_before=None
    if growth is None:
        try:
            old_end=income_for(y-1,q)
            old_before=income_for(y-1,q-1) if q>1 else None
        except (ValueError,OSError):
            old_end=old_before=None
    batch=emit(anchor,end,before,cr,growth,old_end,old_before)
    if not check_apm_batch(batch,anchor):raise ValueError('APM segment evidence failed')
    return batch
