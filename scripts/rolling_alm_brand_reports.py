#!/usr/bin/env python3
"""Rolling Alm. Brand Group report admission after the verified Q3 2026 baseline.

Future periods use explicit quarter and HIÅ headers, report arithmetic, and
independently downloaded issuer presentation solvency evidence. Unknown
layouts are rejected, never substituted with the previous quarter's values.
"""
from datetime import date
from decimal import Decimal
from html.parser import HTMLParser
from urllib.parse import urljoin,unquote
import hashlib
import io
import math
import re
from alm_brand_live_pdf import ARCHIVE, trusted_pdf_link, download_report, fetch_html, LABELS, PERCENT, NUM
from alm_brand_pdf import extract_table

BASELINE=(2026,3)
REQUIRED=('insurance_revenue','insurance_service_result','insurance_revenue_growth',
          'combined_ratio','loss_ratio','expense_ratio','return_on_equity','solvency_ratio','profit_before_tax')

def next_period(year,quarter):
    return (year+1,1) if quarter==4 else (year,quarter+1)

def discover(html,year,quarter):
    class Links(HTMLParser):
        def __init__(self):
            super().__init__();self.anchor=None;self.links=[]
        def handle_starttag(self,tag,attrs):
            if tag=='a':
                attrs=dict(attrs);self.anchor=(attrs.get('href',''),[attrs.get('title','')])
        def handle_data(self,data):
            if self.anchor is not None:self.anchor[1].append(data)
        def handle_endtag(self,tag):
            if tag=='a' and self.anchor is not None:
                href,label=self.anchor;self.anchor=None
                url=urljoin(ARCHIVE,href)
                if trusted_pdf_link(url):self.links.append((url,' '.join(label)))
    parser=Links();parser.feed(html)
    reports=set();presentations=set()
    period=re.compile(rf'(?:\bQ\s*{quarter}\b|\b{quarter}\s*Q\b)[\s_/-]*{year}\b|{year}[\s_/-]*(?:Q\s*{quarter}\b|{quarter}\s*Q\b)',re.I)
    for url,label in parser.links:
        text=unquote(label+' '+url)
        if not period.search(text):continue
        if re.search(r'presentation|slides',text,re.I):
            presentations.add(url)
        elif re.search(r'\bAB[\s_-]*GROUP\b|interim[\s_-]*report|quarterly[\s_-]*report|financial[\s_-]*report',text,re.I) and not re.search(r'solvency|SFCR|sustainability|parent.company',text,re.I):
            reports.add(url)
    return sorted(reports),sorted(presentations)

def column_layout(text,year,q):
    # Distinct current and prior quarter; Q1 is also HIÅ. For Q4,
    # accept explicitly labelled current/prior annual columns, not an annual-only report.
    current=f'Q{q} {year}';prior=f'Q{q} {year-1}'
    # The actual issuer PDF prints period labels and years on two
    # consecutive rows (Q3 Q3 Q1-Q3 Q1-Q3 FY / DKKm 2026 ...).
    # Verify the paired rows, rather than assuming the first numeric column.
    normalized=text.replace('–','-')
    line_pairs=[]
    for a,b in zip(normalized.splitlines(),normalized.splitlines()[1:]):
        years=re.search(r'\bDKKm\s+((?:20\d{2}(?:\s+|$))+)',b,re.I)
        if not years:continue
        ys=[int(v) for v in years.group(1).split()]
        labels=re.findall(r'\bQ1-Q[1-4]\b|\bQ[1-4]\b|\bFY\b',a,re.I)
        labels=[v.upper() for v in labels]
        if len(labels)!=len(ys):continue
        if q==1 and labels[:2]==['Q1','Q1'] and ys[:2]==[year,year-1]:
            if len(ys)==2 or (len(ys)==3 and labels[-1]=='FY' and ys[-1]==year-1):
                line_pairs.append((len(ys),0,1))
        elif q>1:
            prefix=[f'Q{q}',f'Q{q}']
            cumulative=[f'Q1-Q{q}',f'Q1-Q{q}']
            if q==4 and labels[2:4]==['FY','FY']:cumulative=['FY','FY']
            if labels[:4]==prefix+cumulative and ys[:4]==[year,year-1,year,year-1]:
                if len(ys)==4 or (len(ys)==5 and labels[-1]=='FY' and ys[-1]==year-1):
                    line_pairs.append((len(ys),2,3))
    if len(set(line_pairs))==1:return line_pairs[0]
    if line_pairs:raise ValueError('Ambiguous issuer period column headers')
    text=' '.join(normalized.split())
    base=re.escape(current+' '+prior)
    if q==1:
        if re.search(base+r'\s+'+str(year-1)+r'\b',text):return (3,0,1)
        if re.search(base+r'\b',text):return (2,0,1)
    else:
        ytd=rf'Q1\s*-\s*Q{q}\s+{year}\s+Q1\s*-\s*Q{q}\s+{year-1}'
        if re.search(base+r'\s+'+ytd+r'\s+'+str(year-1)+r'\b',text):return (5,2,3)
        if re.search(base+r'\s+'+ytd,text):return (4,2,3)
        if q==4 and re.search(base+rf'\s+{year}\s+{year-1}\b',text):return (4,2,3)
    raise ValueError('Explicit Alm. Brand quarter/prior/HIÅ column header not verified')

def numeric_values(tail,count):
    tail=re.sub(r'(?<=\d),(?=\d{1,2}(?:\s|$))','.',tail)
    values=tail.split()
    if len(values)!=count or not all(re.fullmatch(r'-?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?',x) for x in values):
        raise ValueError('Unexpected Alm. Brand numeric columns')
    return [Decimal(x.replace(',','')) for x in values]

def row(text,label,count):
    pattern=re.compile(r'^\s*(?:(?:INCOME|STATEMENT)\s+)?'+re.escape(label)+r'\s+(?=-?\d)(.+?)\s*$',re.I)
    matches=[m.group(1) for line in text.splitlines() if (m:=pattern.fullmatch(line))]
    if len(matches)!=1:raise ValueError('Missing or ambiguous Alm. Brand group row: '+label)
    # The half-page crop occasionally retains a fragment of the adjacent
    # balance sheet/financial-ratios heading, as in the original Q3 PDF.
    # Strip only the known fragments, never extra numeric cells.
    tail=re.sub(r'\s+(?:BA|SH|FIN|RA)\s*$','',matches[0])
    return numeric_values(tail,count)

def verify_report(texts,url,raw,year,quarter,regions=None):
    if not trusted_pdf_link(url) or not raw.startswith(b'%PDF-'):
        raise ValueError('Untrusted Alm. Brand report')
    cover=' '.join(texts[:2])
    if not re.search(r'Alm[.\s]+Brand',cover,re.I) or not re.search(rf'\bQ{quarter}\b',cover,re.I) or str(year) not in cover:
        raise ValueError('Alm. Brand issuer/period cover mismatch')
    regions=regions or {}
    eligible=[(i,t) for i,t in enumerate(texts) if all(x in t for x in
        ('Gross expense ratio','Net reinsurance ratio','Insurance service result',
         'Return on equity after tax','INCOME Insurance revenue',f'Q{quarter} {year}'))]
    if len(eligible)!=1:raise ValueError('Unique Alm. Brand group highlights not found')
    i,t=eligible[0]
    left=regions.get(i,{}).get('left') or t
    right=regions.get(i,{}).get('right') or t
    count,yi,pi=column_layout(left,year,quarter)
    rows={k:row(left,label,count) for k,label in LABELS.items()}
    pretax=re.search(r'Profit/loss before tax, continuing\s*\n\s*([-\d,.\s]+?)\s*\n\s*operations',left,re.I)
    if not pretax:raise ValueError('Missing consolidated result before tax row')
    pbt=numeric_values(pretax.group(1),count)
    roe=re.search(r'Return on equity after tax\s*\n\s*([-\d,.\s]+?)(?:\n|$)',right,re.I)
    if not roe:raise ValueError('Missing reported ROE')
    roe_count=len(roe.group(1).split())
    if roe_count not in ((2,3) if quarter==1 else (4,5)):
        raise ValueError('Unknown ROE period columns')
    # Independently identify the ratio-table header before assigning ROE periods.
    column_layout(right,year,quarter)
    return_vals=numeric_values(roe.group(1),roe_count)
    if any(not math.isfinite(float(v)) for v in return_vals):
        raise ValueError('Nonfinite ROE')
    solvent=[(j,s) for j,s in enumerate(texts) if 'Total capital as a percentage of solvency capital' in s]
    if len(solvent)!=1:raise ValueError('Missing group solvency table')
    j,s=solvent[0]
    st=regions.get(j,{}).get('right') or s
    coverage=re.search(r'Total capital as a percentage of solvency capital[\s\S]{0,160}?(\d{2,3})\s+(\d{2,3})\s*\n\s*requirement',st,re.I)
    if not coverage:coverage=re.search(r'Total capital as a percentage of solvency capital\s+requirement\s+(\d{2,3})\s+(\d{2,3})',st,re.I)
    if not coverage:raise ValueError('Missing reported group solvency ratio')
    solvency=float(coverage.group(1))
    def at(idx,prior):
        rev=rows['insurance_revenue'][idx]
        claims=abs(rows['claims_expenses'][idx]);cost=abs(rows['operating_expenses'][idx])
        reins=-rows['reinsurance'][idx];service=rows['insurance_service_result'][idx]
        if min(rev,rows['insurance_revenue'][prior],claims,cost)<=0 or abs(rev-claims-cost-reins-service)>Decimal('1.5'):
            raise ValueError('Alm. Brand income statement arithmetic mismatch')
        check={'gross_claims_ratio':claims/rev*100,'reinsurance_ratio':reins/rev*100,
               'loss_ratio':(claims+reins)/rev*100,'expense_ratio':cost/rev*100,
               'combined_ratio':(claims+reins+cost)/rev*100}
        if any(abs(value-rows[k][idx])>Decimal('0.20') for k,value in check.items()):
            raise ValueError('Alm. Brand issuer-ratio reconciliation failed')
        return dict(insurance_revenue=float(rev),insurance_service_result=float(service),
            insurance_revenue_growth=float((rev/rows['insurance_revenue'][prior]-1)*100),
            combined_ratio=float(rows['combined_ratio'][idx]),loss_ratio=float(rows['loss_ratio'][idx]),
            expense_ratio=float(rows['expense_ratio'][idx]),return_on_equity=float(return_vals[idx]),
            solvency_ratio=solvency,profit_before_tax=float(pbt[idx]))
    current=at(0,1);ytd=at(yi,pi)
    table_rows=[dict(page=i+1,label=label,period=f'Q{quarter} {year}',value=current[k],
                unit='%' if k.endswith('ratio') else 'DKK million')
                for k,label in [('insurance_revenue','Insurance revenue'),
                    ('insurance_service_result','Insurance service result'),
                    ('combined_ratio','Combined ratio'),('loss_ratio','Claims ratio'),('expense_ratio','Expense ratio')]]
    result=extract_table(raw,url,year,quarter,table_rows)
    result.update(status='verified_official_pdf_reconciled',metrics=current,ytd_metrics=ytd,
        source_pages={k:j+1 if k=='solvency_ratio' else i+1 for k in current},
        return_on_equity_definition='Annualised Group return on equity after tax (% p.a.), issuer definition',
        return_on_equity_ytd=ytd['return_on_equity'],profit_before_tax_ytd=ytd['profit_before_tax'],
        issuer_page_url=ARCHIVE,
        growth_evidence={'quarter_prior':float(rows['insurance_revenue'][1]),'ytd_prior':float(rows['insurance_revenue'][pi])},
        ratio_evidence={'quarter':{k:float(v[0]) for k,v in rows.items()},'ytd':{k:float(v[yi]) for k,v in rows.items()}})
    return result

def presentation_evidence(texts,url,raw,year,quarter,solvency):
    if not trusted_pdf_link(url) or not raw.startswith(b'%PDF-'):raise ValueError('Untrusted presentation')
    cover=' '.join(texts[:3]).lower()
    if str(year) not in cover or f'q{quarter}' not in cover or 'insurance' not in cover:
        raise ValueError('Wrong Alm. Brand presentation period')
    candidates=[]
    for i,t in enumerate(texts):
        compact=' '.join(t.split())
        if not re.search(rf'DKKm\s+Q{quarter}\s+{year}\b',compact,re.I):continue
        if not all(x in compact for x in ('Total capital','Solvency capital requirement','Total capital ratio')):continue
        ratio=re.search(r'Total capital ratio\s+(\d{2,3})\s*%',compact,re.I)
        own=re.search(r'Total capital for the group(?: for SCR)?\s+([\d,]+)',compact,re.I)
        scr=re.search(r'Solvency capital requirement\s*\(SCR\)\s+([\d,]+)',compact,re.I)
        if not (ratio and own and scr):continue
        amount=int(own.group(1).replace(',',''));required=int(scr.group(1).replace(',',''))
        if required<=0 or int(ratio.group(1))!=solvency or round(amount/required*100)!=solvency:
            raise ValueError('Independent Alm. Brand SCR ratio mismatch')
        candidates.append(dict(source_url=url,source_sha256=hashlib.sha256(raw).hexdigest(),source_page=i+1,
            source_type='official_results_presentation',year=year,quarter=quarter,scope='group',currency='DKK',
            metrics={'solvency_ratio':solvency,'own_funds':amount,'solvency_capital_requirement':required}))
    if len(candidates)!=1:raise ValueError('Unique issuer presentation capital table not found')
    return candidates[0]

def read_report(raw):
    import pdfplumber
    with pdfplumber.open(io.BytesIO(raw)) as pdf:
        texts=[];regions={}
        for i,p in enumerate(pdf.pages):
            t=p.extract_text(layout=False) or '';texts.append(t)
            if 'Return on equity after tax' in t or 'Total capital as a percentage of solvency capital' in t:
                regions[i]={'left':p.crop((0,0,p.width*.52,p.height)).extract_text(layout=False) or '',
                            'right':p.crop((p.width*.48,0,p.width,p.height)).extract_text(layout=False) or ''}
    return texts,regions

def validate_rolling(row):
    errors=[];metrics=row.get('metrics',{});ytd=row.get('ytd_metrics',{});ev=row.get('presentation_evidence',{})
    period=(row.get('year'),row.get('quarter'))
    sha=str(row.get('source_sha256') or '')
    if (row.get('status')!='verified_official_pdf_reconciled' or row.get('scope')!='group'
        or row.get('currency')!='DKK' or row.get('source_type')!='official_quarterly_report'
        or not trusted_pdf_link(row.get('source_url') or '') or not re.fullmatch(r'[0-9a-f]{64}',sha)
        or set(metrics)!=set(REQUIRED) or set(ytd)!=set(REQUIRED)
        or not all(type(x) in (int,float) and math.isfinite(x) for x in [*metrics.values(),*ytd.values()])
        or any(type(row.get('source_pages',{}).get(k)) is not int or row['source_pages'][k]<1 for k in REQUIRED)):
        errors.append('Alm. Brand rolling report evidence incomplete')
    em=ev.get('metrics',{})
    if (ev.get('source_type')!='official_results_presentation' or not trusted_pdf_link(ev.get('source_url') or '')
        or not re.fullmatch(r'[0-9a-f]{64}',str(ev.get('source_sha256') or ''))
        or ev.get('source_sha256')==sha or type(ev.get('source_page')) is not int or ev.get('source_page',0)<1
        or (ev.get('year'),ev.get('quarter'))!=period or ev.get('scope')!='group' or ev.get('currency')!='DKK'
        or em.get('solvency_ratio')!=metrics.get('solvency_ratio') or ytd.get('solvency_ratio')!=metrics.get('solvency_ratio')
        or type(em.get('own_funds')) not in (int,float) or type(em.get('solvency_capital_requirement')) not in (int,float)
        or em.get('solvency_capital_requirement',0)<=0 or round(em['own_funds']/em['solvency_capital_requirement']*100)!=em.get('solvency_ratio')):
        errors.append('Alm. Brand rolling independent presentation evidence invalid')
    evidence=row.get('ratio_evidence',{});growth=row.get('growth_evidence',{})
    for period_kind,values,prior_key in (('quarter',metrics,'quarter_prior'),('ytd',ytd,'ytd_prior')):
        e=evidence.get(period_kind,{})
        try:
            rev=e['insurance_revenue'];claims=abs(e['claims_expenses']);cost=abs(e['operating_expenses']);reins=-e['reinsurance'];prior=growth[prior_key]
            if (rev<=0 or prior<=0 or abs(rev-claims-cost-reins-e['insurance_service_result'])>1.5
                or any(values[k]!=e[k] for k in ('insurance_revenue','insurance_service_result','combined_ratio','loss_ratio','expense_ratio'))
                or abs((claims+reins)/rev*100-values['loss_ratio'])>0.20
                or abs(cost/rev*100-values['expense_ratio'])>0.20
                or abs((claims+reins+cost)/rev*100-values['combined_ratio'])>0.20
                or abs((rev/prior-1)*100-values['insurance_revenue_growth'])>1e-6):
                raise ValueError('Mismatch')
        except (TypeError,KeyError,ValueError,ZeroDivisionError):
            errors.append('Alm. Brand rolling '+period_kind+' metric reconciliation invalid')
    history=row.get('periods')
    if history is not None:
        try:
            periods=[(p['year'],p['quarter']) for p in history]
            if (not periods or periods[0]!=BASELINE or periods[-1]!=period
                or any(next_period(*a)!=b for a,b in zip(periods,periods[1:]))
                or {k:v for k,v in row.items() if k!='periods'}!=history[-1]
                or any(validate_rolling(p) for p in history[1:])):
                errors.append('Alm. Brand rolling history is incomplete or changed')
        except (TypeError,KeyError,ValueError):
            errors.append('Alm. Brand rolling history is invalid')
    return errors

def advance(existing,*,today=None,fetcher=fetch_html,downloader=download_report,reader=read_report):
    today=today or date.today()
    year,q=next_period(existing['year'],existing['quarter'])
    current=(today.year,(today.month-1)//3+1)
    if (year,q)>=current:return existing
    html=fetcher(ARCHIVE)
    history=list(existing.get('periods',[]))
    if not history:
        history=[{k:v for k,v in existing.items() if k!='periods'}]
    while (year,q)<current:
        reports,presentations=discover(html,year,q)
        if not reports and not presentations:
            print('ALM_NEXT_REPORT_NOT_YET_FOUND',year,q,flush=True);break
        if len(reports)!=1 or len(presentations)!=1:
            raise ValueError(f'Incomplete or ambiguous Alm. Brand report/presentation Q{q} {year}')
        report,presentation=reports[0],presentations[0]
        raw=downloader(report);texts,regions=reader(raw)
        new=verify_report(texts,report,raw,year,q,regions)
        p_raw=downloader(presentation);p_texts,_=reader(p_raw)
        new['presentation_evidence']=presentation_evidence(p_texts,presentation,p_raw,year,q,new['metrics']['solvency_ratio'])
        errors=validate_rolling(new)
        if errors:raise ValueError('; '.join(errors))
        history.append(new);year,q=next_period(year,q)
    if (history[-1]['year'],history[-1]['quarter'])==(existing['year'],existing['quarter']):return existing
    return {**history[-1],'periods':history}
