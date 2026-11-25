#!/usr/bin/env python3
"""Discover the next KLP Skadeforsikring report and admit only reconciled periods.

No dates or amounts are filled in from the calendar. A missing report is a
no-op; an ambiguous or changed published PDF blocks the next period.
"""
from datetime import date
from decimal import Decimal
import hashlib
import re
import urllib.request
from import_extended_pdfs import download,pages,approved
from klp_q2_q3_discovery import INDEX_URL,discover
from klp_q2q3_reconcile import AMOUNTS,RATIOS,columns
from klp_ratio_reconciliation import reconcile

def next_period(year,quarter):
    return (year+1,1) if quarter==4 else (year,quarter+1)

def fetch_archive():
    req=urllib.request.Request(INDEX_URL,headers={'User-Agent':'Mozilla/5.0 Forsikringsbarometeret'})
    with urllib.request.urlopen(req,timeout=25) as response:
        from urllib.parse import urlsplit
        if urlsplit(response.geturl()).hostname not in ('www.klp.no','klp.no'):
            raise ValueError('Unexpected KLP archive redirect')
        return response.read(4_000_000).decode('utf-8','replace')

def verify_report(texts,year,quarter,url,digest):
    """Strict isolated and cumulative column mapping for future issuer PDFs."""
    if quarter not in (1,2,3,4) or type(year) is not int or year<2026:
        raise ValueError('Invalid target period')
    if not approved(url,'KLP Skadeforsikring'):
        raise ValueError('Unexpected KLP source')
    if not re.search(r'KLP\s+Skadeforsikring', ' '.join(texts[:5]),re.I):
        raise ValueError('PDF does not identify KLP Skadeforsikring')
    current=f'{quarter}. kvartal {year}'
    prior=f'{quarter}. kvartal {year-1}'
    end={1:'31.03.',2:'30.06.',3:'30.09.',4:'31.12.'}[quarter]
    date_label=end+str(year)
    previous_date=end+str(year-1)
    result_candidates=[]
    note_candidates=[]
    for i,t in enumerate(texts):
        if re.search(r'^Resultatregnskap$',t,re.M):
            header=re.search(r'(?:NOTE\s+)?MILLIONER KRONER\s+([^\n]+)',t)
            if header and header.group(1).startswith(current+' '+prior):
                # Read only explicitly ordered current/prior quarter + current/prior HIÅ.
                h=header.group(1)
                rest=h[len(current+' '+prior):].strip()
                if quarter==1 and rest==f'31.12.{year-1}':
                    result_candidates.append((i,t,3,0,1))
                elif quarter>1:
                    suffixes={f'{date_label} {previous_date} 31.12.{year-1}':5,
                              f'{date_label} {previous_date}':4}
                    if rest in suffixes:
                        result_candidates.append((i,t,suffixes[rest],2,3))
        if re.search(r'Note\s+\d+\s+Nøkkeltall\s*[-–]\s*akkumulert',t,re.I) and 'Totalskadeprosent' in t:
            h=re.search(r'MILLIONER KRONER\s+([^\n]+)',t)
            if h and h.group(1).startswith(current+' '):
                note_candidates.append((i,t))
    if len(result_candidates)!=1 or len(note_candidates)!=1:
        raise ValueError('Unique issuer quarter/HIÅ result and cumulative KPI note not found')
    rp,result,count,yidx,pidx=result_candidates[0]
    np,note=note_candidates[0]
    rows={k:columns(result,label,expected=count) for k,label in AMOUNTS.items()}
    def note_values(label,percent=False):
        # Note history grows over the year. Its first column must be explicitly
        # current quarter as verified above; require a unique matching row.
        for n in (3,4,5,6,7,8):
            try:return columns(note,label,expected=n,percent=percent)
            except ValueError:continue
        raise ValueError('Unverified KLP cumulative note row: '+label)
    ratios={k:float(note_values(label,True)[0]) for k,label in RATIOS.items()}
    def components(i):
        rev=rows['insurance_revenue'][i]
        gross=-rows['gross_claims_cost'][i]
        expenses=-rows['operating_expenses'][i]
        reinsurance=-rows['reinsurance_result'][i]
        service=rows['insurance_service_result'][i]
        if min(rev,gross,expenses)<=0 or abs(rev-gross-expenses-reinsurance-service)>Decimal('0.25'):
            raise ValueError('KLP source accounting reconciliation failed')
        return dict(insurance_revenue=float(rev),gross_claims_cost=float(gross),
                    operating_expenses=float(expenses),reinsurance_effect=float(reinsurance))
    base=dict(company='KLP Skadeforsikring',year=year,quarter=quarter,scope='company',
              currency='NOK',unit='NOK million',source_url=url,source_sha256=digest,
              issuer_definition_verified=True)
    q={**base,'period_type':'quarter','source_pages':[rp+1],'ratio_components':components(0)}
    y={**base,'period_type':'ytd','source_pages':[rp+1,np+1],'ratio_components':components(yidx),'reported_ratios':ratios}
    pre_tax=columns(result,'Resultat før skattekostnad',expected=count)
    if abs(pre_tax[yidx]-note_values('Resultat før skatt')[0])>Decimal('0.15'):
        raise ValueError('KLP HIÅ result disagrees with independently reported KPI note')
    solvency=note_values('Solvenskapitaldekning',True)[0]
    if not 0<solvency<1000:raise ValueError('Invalid KLP solvency')
    out=reconcile(q,y)
    out.update(reported_management_metrics={'profit_before_tax':float(pre_tax[0]),
        'profit_before_tax_ytd':float(pre_tax[yidx]),'solvency_ratio':float(solvency),
        'source_page':np+1,'period_basis':{'profit_before_tax':'quarter','profit_before_tax_ytd':'ytd','solvency_ratio':'quarter_end'}},
        reported_quarter_amounts={k:float(v[0]) for k,v in rows.items()},
        reported_ytd_amounts={k:float(v[yidx]) for k,v in rows.items()},
        reported_prior_year_quarter_amounts={k:float(v[1]) for k,v in rows.items()},
        reported_prior_year_ytd_amounts={k:float(v[pidx]) for k,v in rows.items()},
        reported_ytd_ratios=ratios,status='issuer_pdf_quarter_and_ytd_reconciled_not_published')
    return out

def advance(existing,*,today=None,fetcher=fetch_archive,downloader=download,extractor=pages):
    from import_klp_production import row_from_reconciliation,snapshot_from_rows,verify_latest
    today=today or date.today()
    latest=(existing['year'],existing['quarter'])
    year,q=next_period(*latest)
    current=(today.year,(today.month-1)//3+1)
    if (year,q)>=current:return existing
    html=fetcher()
    rows=list(existing['periods'])
    while (year,q)<current:
        links=discover(html,year=year,periods=(q,))[q]
        if not links:
            print('KLP_NEXT_REPORT_NOT_YET_FOUND',year,q,flush=True)
            break
        if len(links)!=1:
            raise ValueError(f'Ambiguous KLP issuer PDF Q{q} {year}')
        url=links[0]
        raw=downloader(url,'KLP Skadeforsikring')
        if not raw.startswith(b'%PDF-'):raise ValueError('Not an issuer PDF')
        item=verify_report(extractor(raw),year,q,url,hashlib.sha256(raw).hexdigest())
        rows.append(row_from_reconciliation(item))
        print('KLP_ROLLING_REPORT_VERIFIED',year,q,flush=True)
        year,q=next_period(year,q)
    if len(rows)==len(existing['periods']):return existing
    updated=snapshot_from_rows(rows)
    verify_latest(existing,updated)
    return updated
