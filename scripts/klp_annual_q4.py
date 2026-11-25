#!/usr/bin/env python3
"""KLP Q4 residual: audited annual flows minus the same fiscal year's Q3 HIÅ.

Owner-approved Q4-only exception. Never subtract ratios, solvency or ROE.
Both documents must be official company reports, with explicitly identified
periods, comparable accounting policies and matching prior full-year amounts.
All arithmetic is reproducible from two source documents and saved inputs.
"""
from decimal import Decimal
from itertools import product
import hashlib
import math
import re
from import_extended_pdfs import approved
from klp_ratio_reconciliation import ratios
from klp_q2q3_reconcile import AMOUNTS, RATIOS

COMPANY='KLP Skadeforsikring'
METHOD='annual_minus_q3_ytd'
BASIS='KLP Skadeforsikring AS; company; IFRS insurance accounting; NOK million'
LABELS={**AMOUNTS,'profit_before_tax':'Resultat før skattekostnad'}
CELL=r'[-−]?(?:\d{1,3}(?:[ \u00a0]\d{3})+|\d+)(?:,\d+)?'
NUM=re.compile(CELL)
NOTE_PREFIX=r'(?:\d+(?:,\s*\d+)*\s+)?'
TOL=Decimal('0.25')
RATIO_TOL=Decimal('0.16')

def dec(x):
    if type(x) not in (int,float,str,Decimal):
        raise ValueError('Invalid KLP amount')
    d=Decimal(str(x).replace('\u00a0',' ').replace(' ','').replace(',','.').replace('−','-'))
    if not d.is_finite():raise ValueError('Nonfinite KLP amount')
    return d

def values(tail,count,percent=False):
    tail=tail.strip()
    if percent:
        m=re.fullmatch(r'\s*'+r'\s+'.join('('+CELL+r')\s*%' for _ in range(count))+r'\s*',tail)
        if not m:raise ValueError('Invalid KLP percentage columns: '+tail[:160])
        return [dec(v) for v in m.groups()]
    tokens=tail.split()
    def parse(start,found):
        if len(found)==count:
            if start==len(tokens):yield tuple(found)
            return
        for end in range(start+1,len(tokens)+1):
            candidate=' '.join(tokens[start:end])
            if NUM.fullmatch(candidate):yield from parse(end,found+[dec(candidate)])
    matches=set(parse(0,[]))
    if len(matches)!=1:raise ValueError('Ambiguous KLP numeric columns: '+tail[:180])
    return list(matches.pop())

def row(text,label,count,percent=False):
    pattern=re.compile(r'^\s*'+NOTE_PREFIX+label+r'\s+(.+?)\s*$',re.I)
    hits=[m.group(1) for line in text.splitlines() if (m:=pattern.fullmatch(line))]
    if len(hits)!=1:raise ValueError('Missing or ambiguous KLP row: '+label+'; '+repr([l for l in text.splitlines() if re.search(label,l,re.I)][:3]))
    return values(hits[0],count,percent)

def amount_rows(text,count):
    return {key:row(text,re.escape(label),count) for key,label in LABELS.items()}

def components(a,*,tolerance=TOL):
    a={k:dec(a[k]) for k in LABELS}
    rev=a['insurance_revenue'];gross=-a['gross_claims_cost'];expense=-a['operating_expenses'];reins=-a['reinsurance_result']
    if min(rev,gross,expense)<=0:
        raise ValueError('KLP revenue or expense sign invalid')
    if abs(rev-gross-expense-reins-a['insurance_service_result'])>tolerance:
        raise ValueError('KLP insurance accounting reconciliation failed')
    return dict(insurance_revenue=rev,gross_claims_cost=gross,operating_expenses=expense,reinsurance_effect=reins)

def check_ratios(amounts,reported):
    calculated=ratios(components(amounts))
    if set(reported) not in (set(RATIOS),set(RATIOS)-{'combined_ratio'}):
        raise ValueError('Incomplete KLP issuer ratio evidence')
    for k,v in reported.items():
        if abs(calculated[k]-dec(v))>RATIO_TOL:
            raise ValueError('KLP cumulative ratio reconciliation failed: '+k)
    if 'combined_ratio' not in reported and abs(calculated['combined_ratio']-dec(reported['loss_ratio'])-dec(reported['expense_ratio']))>RATIO_TOL:
        raise ValueError('KLP annual total ratio reconciliation failed')
    return calculated

def as_floats(data):
    return {k:float(v) for k,v in data.items()}

def policy_pages(texts,annual,views=None,year=None):
    """Read Note 2, allowing separate PDF columns on the same note page.

    Never infer continuity merely from an IFRS reference or a matching ratio.
    Both the accounting framework and the issuer's explicit no-material-change
    statement must be found. Preserve the original physical page references.
    """
    variants=views or {}
    base_pattern=r'IFRS\s+Accounting\s+Standards?'
    law_pattern=r'årsregnskap(?:s)?forskriften|Forskrift om årsregnskap for skadeforsikringsforetak'
    if annual:
        period=rf'\s+{year}\s+årsregnskapet' if year else r'\s+20\d{2}\s+årsregnskapet'
        no_change=r'ingen\s+nye\s+eller\s+endrede\s+IFRS\s+Accounting\s+Standards?\s+eller\s+IFRIC[\s-]+fortolkninger\s+som\s+er\s+trådt\s+i\s+kraft\s+for'+period+r'\s+som\s+påvirker\s+(?:foretakets|konsernets)\s+årsregnskap\s+i\s+vesentlig\s+grad'
    else:
        period=rf'\s+per\s+30\.09\.{year}' if year else r'\s+per\s+30\.09\.20\d{2}'
        no_change=r'ikke\s+foretatt\s+(?:andre\s+)?endringer\s+i\s+regnskapsprinsippene\s+som\s+har\s+hatt\s+betydning\s+for\s+delårsregnskapet'+period
    basis_pages=set();change_pages=set();diagnostics=[]
    for i,t in enumerate(texts):
        # The policy heading and IFRS disclosure can be in different columns.
        # Only examine Note 2 pages (and a possible immediately following page).
        context=' '.join(texts[max(0,i-1):i+1])
        if not re.search(r'Note\s+2\b.{0,160}?regnskapsprinsipp', ' '.join(context.split()),re.I):
            continue
        candidates=[' '.join(v.replace('\u00ad','').split()) for v in [t,*variants.get(i,[])]]
        for compact in candidates:
            if re.search(base_pattern,compact,re.I) and re.search(law_pattern,compact,re.I) and (annual or re.search(r'IAS\s*34\b',compact,re.I)):
                basis_pages.add(i+1)
            if re.search(no_change,compact,re.I):
                change_pages.add(i+1)
            if re.search(r'ingen\s+nye|ikke\s+foretatt|vesentlig\s+grad|IFRIC',compact,re.I):
                matches=[m.group()[:400] for m in re.finditer(r'.{0,30}(?:ingen\s+nye|ikke\s+foretatt|IFRIC).{0,320}',compact,re.I)]
                diagnostics.extend((i+1,m) for m in matches[:3])
    pairs=[(a,b) for a in basis_pages for b in change_pages if abs(a-b)<=1]
    if not pairs:
        raise ValueError('KLP explicit comparable accounting policy disclosure missing; basis pages='+repr(sorted(basis_pages))+'; change pages='+repr(sorted(change_pages))+'; excerpts='+repr(list(dict.fromkeys(diagnostics))[:8]))
    return sorted({p for pair in pairs for p in pair})

def source(url,digest,statement_page,ratios_page,policy,year,quarter):
    if not approved(url,COMPANY) or not url.startswith('https://www.klp.no/') or not re.fullmatch(r'[0-9a-f]{64}',digest):
        raise ValueError('Invalid KLP official source provenance')
    return dict(source_url=url,source_sha256=digest,source_pages=sorted(set([statement_page,ratios_page,*policy])),
                statement_page=statement_page,ratio_page=ratios_page,policy_pages=policy,
                year=year,quarter=quarter,scope='company',currency='NOK',unit='NOK million',basis=BASIS)

def is_annual(texts,year):
    cover=' '.join(texts[:3])
    return bool(re.search(r'\bÅrs(?:rapport|regnskap)\b',cover,re.I) and str(year) in cover and re.search(r'KLP\s+Skadeforsikring',cover,re.I))

def parse_annual(texts,year,url,digest,views=None):
    if not is_annual(texts,year):
        raise ValueError('KLP annual report cover/period not verified')
    statements=[]
    ratio_tables=[]
    diagnostics=[]
    for i,t in enumerate(texts):
        variants=[t,*((views or {}).get(i,[]))]
        for v in variants:
            if re.search(r'(?m)^\s*Resultatregnskap\s*$',v,re.I) and re.search(rf'(?m)^\s*NOTE\s+MILLIONER KRONER\s+{year}\s+{year-1}\s*$',v,re.I):
                try:
                    amounts=amount_rows(v,2)
                    statements.append((i+1,amounts))
                except ValueError:continue
            if not re.search(rf'Hovedtall\s+{year}\b',v,re.I) or not re.search(rf'MILLIONER KRONER\s+{year}\s+{year-1}\b',v,re.I):
                continue
            try:
                reported={k:row(v,r'Skadeprosent[- ]brutto' if k=='gross_loss_ratio' else re.escape(label),2,True)
                          for k,label in RATIOS.items() if k!='combined_ratio'}
                # Some annual highlights report combined ratio, some omit it.
                if re.search(r'(?m)^\s*Totalskadeprosent\s+',v):
                    reported['combined_ratio']=row(v,'Totalskadeprosent',2,True)
                revenue=row(v,'Forsikringsinntekter',2)
                profit=row(v,'Resultat før skattekostnad',2)
                solvency=row(v,r'Solvenskapitaldekning(?:\s*\(%\))?',2,True)
                ratio_tables.append((i+1,reported,revenue,profit,solvency))
            except ValueError as exc:
                diagnostics.append((i+1,str(exc),v[:1800]))
                continue
    def unique(items,what):
        result=[]
        for x in items:
            if x not in result:result.append(x)
        if len(result)!=1:
            diagnostic=[(i+1,[l[:200] for l in t.splitlines() if re.search(r'Hovedtall|Solvenskapitaldekning|Skadeprosent[- ]brutto|NOTE MILLIONER KRONER|Forsikringsinntekter',l,re.I)][:8])
                        for i,t in enumerate(texts) if re.search(r'Hovedtall|^Resultatregnskap$',t,re.I|re.M)][:5]
            raise ValueError('Unique annual '+what+' not found: '+repr(diagnostic)+'; table diagnostics: '+repr(diagnostics[:5]))
        return result[0]
    sp,amounts=unique(statements,'income statement')
    rp,reported,rev,pbt,solvency=unique(ratio_tables,'key figures')
    current={k:v[0] for k,v in amounts.items()}
    prior={k:v[1] for k,v in amounts.items()}
    for idx,a in enumerate((current,prior)):
        if abs(a['insurance_revenue']-rev[idx])>Decimal('0.1') or abs(a['profit_before_tax']-pbt[idx])>Decimal('0.1'):
            raise ValueError('Annual headline and income statement disagree')
        check_ratios(a,{k:v[idx] for k,v in reported.items()})
    if not 0<solvency[0]<1000:raise ValueError('Invalid KLP year-end solvency')
    return dict(document=source(url,digest,sp,rp,policy_pages(texts,True,views=views,year=year),year,4),
                current=as_floats(current),prior=as_floats(prior),
                reported_ratios=as_floats({k:v[0] for k,v in reported.items()}),
                prior_reported_ratios=as_floats({k:v[1] for k,v in reported.items()}),
                solvency=float(solvency[0]))

def parse_q3(texts,year,url,digest,views=None):
    cover=' '.join(texts[:3])
    if not re.search(r'KLP\s+Skadeforsikring',cover,re.I) or not re.search(rf'3\.\s*kvartal(?:sregnskap)?\s+{year}',cover,re.I):
        raise ValueError('KLP Q3 report issuer/period mismatch')
    results=[];notes=[]
    for i,t in enumerate(texts):
        if re.search(r'(?m)^\s*Resultatregnskap\s*$',t,re.I):
            # The historical report may wrap 01.01- and 30.09 across physical lines.
            before=re.split(r'(?m)^\s*'+NOTE_PREFIX+r'Forsikringsinntekter\s+',t,maxsplit=1)[0]
            compact=' '.join(before.split())
            compact=re.sub(rf'01\.01\.(?:{year}|{year-1})\s*[-–]\s*','',compact)
            expected=rf'NOTE\s+MILLIONER KRONER\s+3\.\s*kvartal\s+{year}\s+3\.\s*kvartal\s+{year-1}\s+30\.09\.{year}\s+30\.09\.{year-1}\s+31\.12\.{year-1}\b'
            if re.search(expected,compact,re.I):
                results.append((i+1,amount_rows(t,5)))
        if re.search(r'Note\s+\d+\s+Nøkkeltall\s*[-–]\s*akkumulert',t,re.I) and 'Totalskadeprosent' in t:
            if re.search(rf'MILLIONER KRONER\s+3\.\s*kvartal\s+{year}\b',t,re.I):
                notes.append((i+1,t))
    if len(results)!=1 or len(notes)!=1:
        raise ValueError('Unique KLP Q3 current/prior HIÅ and prior FY columns not verified')
    sp,amounts=results[0];rp,note=notes[0]
    def first(label,percent=False):
        for n in (3,4,5,6,7,8):
            try:return row(note,re.escape(label),n,percent)[0]
            except ValueError:continue
        raise ValueError('Missing Q3 note value: '+label)
    current={k:v[2] for k,v in amounts.items()}
    prior={k:v[3] for k,v in amounts.items()}
    prior_fy={k:v[4] for k,v in amounts.items()}
    if abs(first('Forsikringsinntekter')-current['insurance_revenue'])>Decimal('0.1') or abs(first('Resultat før skatt')-current['profit_before_tax'])>Decimal('0.15'):
        raise ValueError('KLP Q3 headline and income statement disagree')
    reported={k:first(label,True) for k,label in RATIOS.items()}
    check_ratios(current,reported)
    components(prior);components(prior_fy)
    return dict(document=source(url,digest,sp,rp,policy_pages(texts,False,views=views,year=year),year,3),
                current=as_floats(current),prior=as_floats(prior),prior_full_year=as_floats(prior_fy),
                reported_ratios=as_floats(reported))

def derive(annual,q3):
    a=annual['document'];b=q3['document']
    for doc in (a,b):
        if (doc.get('basis')!=BASIS or doc.get('scope')!='company' or doc.get('currency')!='NOK'
            or doc.get('unit')!='NOK million' or not doc.get('policy_pages')
            or not approved(doc.get('source_url',''),COMPANY) or not str(doc['source_url']).startswith('https://www.klp.no/')
            or not re.fullmatch(r'[0-9a-f]{64}',str(doc.get('source_sha256','')))
            or not all(type(p) is int and p>0 for p in doc.get('source_pages',[]))
            or not doc.get('source_pages') or not {doc['statement_page'],doc['ratio_page'],*doc['policy_pages']}.issubset(doc['source_pages'])):
            raise ValueError('Invalid KLP Q4 source basis')
    if a['year']!=b['year'] or a['quarter']!=4 or b['quarter']!=3 or a['source_sha256']==b['source_sha256'] or a['source_url']==b['source_url']:
        raise ValueError('KLP Q4 requires distinct matching-year annual and Q3 documents')
    if any(set(x)!=set(LABELS) for x in (annual['current'],annual['prior'],q3['current'],q3['prior'],q3['prior_full_year'])):
        raise ValueError('KLP Q4 incomplete flow inputs')
    for k in LABELS:
        if abs(dec(annual['prior'][k])-dec(q3['prior_full_year'][k]))>Decimal('0.1'):
            raise ValueError('KLP previous full-year comparator changed: '+k)
    annual_ratios=check_ratios(annual['current'],annual['reported_ratios'])
    check_ratios(annual['prior'],annual['prior_reported_ratios'])
    check_ratios(q3['current'],q3['reported_ratios'])
    components(q3['prior']);components(q3['prior_full_year'])
    current={k:dec(annual['current'][k])-dec(q3['current'][k]) for k in LABELS}
    prior={k:dec(annual['prior'][k])-dec(q3['prior'][k]) for k in LABELS}
    # Each independently reconciled statement is rounded to NOK 0.1m.
    # The residual may accumulate BOTH statements' maximum rounding error.
    # Do not relax the checks on the original annual and Q3 amounts.
    quarter_ratios=ratios(components(current,tolerance=2*TOL))
    components(prior,tolerance=2*TOL)
    solvency=dec(annual['solvency'])
    if not 0<solvency<1000:raise ValueError('Invalid KLP year-end solvency')
    def metrics(amounts,ratio_values,prior_amounts):
        return dict(insurance_revenue=float(amounts['insurance_revenue']),
                    insurance_service_result=float(amounts['insurance_service_result']),
                    profit_before_tax=float(amounts['profit_before_tax']),
                    insurance_revenue_growth=float((dec(amounts['insurance_revenue'])/dec(prior_amounts['insurance_revenue'])-1)*100),
                    **{k:float(ratio_values[k]) for k in ('combined_ratio','loss_ratio','expense_ratio')},
                    solvency_ratio=float(solvency))
    ytd_ratios={**as_floats(annual_ratios),**annual['reported_ratios']}
    # If a combined ratio is absent from the annual highlights, compute it from
    # the actual full-year cost components; do not pretend it was reported.
    result=metrics(current,quarter_ratios,prior)
    ytd=metrics(annual['current'],ytd_ratios,annual['prior'])
    methods={k:'calculated' for k in result};methods['solvency_ratio']='reported_quarter_end'
    return dict(company=COMPANY,year=a['year'],quarter=4,scope='company',currency='NOK',
                unit='NOK million for financial amounts; percent for ratios',
                status='verified_official_pdf_reconciled',source_type='official_annual_report',
                source_url=a['source_url'],source_sha256=a['source_sha256'],
                source_pages={'quarter':a['source_pages'],'ytd':a['source_pages']},
                metrics=result,ytd_metrics=ytd,metric_methods=methods,
                quarter_calculation={'method':METHOD,'basis':BASIS,'annual':annual,'q3_ytd':q3,
                    'quarter_amounts':as_floats(current),'prior_year_quarter_amounts':as_floats(prior),
                    'annual_combined_ratio_reported':'combined_ratio' in annual['reported_ratios']},
                source_documents=[a,b],
                reported_ytd_ratios=annual['reported_ratios'],
                management_kpi_evidence={'source_page':a['ratio_page'],'source_sha256':a['source_sha256'],
                    'period_basis':{'profit_before_tax':'annual_minus_q3_ytd','profit_before_tax_ytd':'ytd','solvency_ratio':'quarter_end'},
                    'profit_before_tax_ytd':annual['current']['profit_before_tax'],'source_metric':'derived_pre_tax_reported_solvency'},
                revenue_growth_evidence={'quarter':{'year':a['year'],'quarter':4,'current':result['insurance_revenue'],
                        'prior_year':float(prior['insurance_revenue']),'growth_percent':result['insurance_revenue_growth'],'source_page':a['statement_page']},
                    'ytd':{'year':a['year'],'quarter':4,'current':ytd['insurance_revenue'],
                        'prior_year':annual['prior']['insurance_revenue'],'growth_percent':ytd['insurance_revenue_growth'],'source_page':a['statement_page']},
                    'previous_year':a['year']-1,'source_sha256':a['source_sha256'],'revenue_definition':BASIS})

def validate_derived(row,previous=None):
    try:
        evidence=row['quarter_calculation']
        if evidence['method']!=METHOD:raise ValueError('Unknown Q4 calculation')
        rebuilt=derive(evidence['annual'],evidence['q3_ytd'])
        if row!=rebuilt:raise ValueError('KLP stored Q4 metrics do not reproduce source calculation')
        if previous is not None:
            src=evidence['q3_ytd']['document']
            if (previous.get('year'),previous.get('quarter'))!=(row['year'],3) or previous.get('source_sha256')!=src['source_sha256'] or previous.get('source_url')!=src['source_url']:
                raise ValueError('KLP Q3 source differs from previously approved snapshot')
            current=evidence['q3_ytd']['current']
            management=previous.get('management_kpi_evidence',{})
            growth=previous.get('revenue_growth_evidence',{}).get('ytd',{})
            if abs(dec(current['insurance_revenue'])-dec(growth['current']))>Decimal('0.1') or abs(dec(current['profit_before_tax'])-dec(management['profit_before_tax_ytd']))>Decimal('0.1'):
                raise ValueError('KLP Q3 HIÅ amounts differ from previous approved snapshot')
        return []
    except (KeyError,TypeError,ValueError,ArithmeticError) as exc:
        return ['KLP derived Q4 evidence invalid: '+str(exc)]

def annual_views(raw,texts):
    """Use half-page crops only for annual highlights with interleaved prose."""
    import io,pdfplumber
    result={}
    with pdfplumber.open(io.BytesIO(raw)) as pdf:
        for i,t in enumerate(texts):
            if re.search(r'Hovedtall\s+20\d{2}|regnskapsprinsipp|IFRS\s+Accounting|IFRIC',t,re.I):
                p=pdf.pages[i]
                views=[]
                # The annual report uses three text columns; the highlights
                # table can sit in the middle column between two prose blocks.
                for x0,x1 in ((0,.52),(.48,1),(0,.35),(.32,.68),(.65,1),(.30,.70),(.03,.33),(.34,.66),(.67,.98),(.02,.36),(.31,.69),(.64,.99)):
                    views.append(p.crop((p.width*x0,0,p.width*x1,p.height)).extract_text() or '')
                words=p.extract_words()
                for heading in (w for w in words if w['text'].lower()=='hovedtall'):
                    nearby=[w for w in words if heading['top']<=w['top']<=heading['top']+70
                            and heading['x0']-15<=w['x0']<=heading['x0']+p.width*.40]
                    # Determine the table bounds using its printed title and
                    # two year column labels; never infer data from location alone.
                    for first in (w for w in nearby if re.fullmatch(r'20\d{2}',w['text'])):
                        for second in (w for w in nearby if abs(w['top']-first['top'])<3
                            and w['x0']>first['x0'] and w['text']==str(int(first['text'])-1)):
                            end_rows=[w for w in words if w['text'].startswith('Solvenskapitaldekning')
                                      and w['top']>first['top'] and abs(w['x0']-heading['x0'])<25]
                            for end in end_rows:
                                for margin in (3,7,12):
                                    x0=max(0,min(heading['x0'],end['x0'])-margin)
                                    x1=min(p.width,second['x1']+margin)
                                    if x1>x0:
                                        views.append(p.crop((x0,max(0,heading['top']-3),x1,min(p.height,end['bottom']+5))).extract_text() or '')
                result[i]=list(dict.fromkeys(views))
    return result
