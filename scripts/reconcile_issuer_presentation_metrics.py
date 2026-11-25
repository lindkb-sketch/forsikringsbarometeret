"""Presentation extraction for observed issuer layouts, with no target-value searching.

Unknown or ambiguous layouts yield no evidence. Quarterly, YTD and point-in-time
metrics are never conflated with forecasts, TTM or underlying segment measures.
"""
import re
import io
from decimal import Decimal,ROUND_HALF_UP
from math import isfinite

NUM=r'-?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?'
KEYS={'Insurance revenue':'insurance_revenue','Insurance revenue, net':'insurance_revenue',
      'Insurance service result':'insurance_service_result','Underwriting result':'insurance_service_result',
      'Pre-tax profit':'profit_before_tax','Profit before taxes':'profit_before_tax',
      'Claims ratio':'loss_ratio','Risk ratio, %':'loss_ratio','Expense ratio':'expense_ratio',
      'Cost ratio, %':'expense_ratio','Combined ratio':'combined_ratio','Combined ratio, %':'combined_ratio',
      'Solvency ratio':'solvency_ratio','Solvency II ratio,%':'solvency_ratio'}
AMOUNTS={'insurance_revenue','insurance_service_result','profit_before_tax'}

def number_columns(tail,count):
    """Bounded numeric rows: grouping spaces are admitted only when unique."""
    tokens=tail.strip().replace('\u00a0',' ').split()
    def parse(start,values):
        if len(values)==count:
            if start==len(tokens):yield tuple(values)
            return
        for end in range(start+1,min(len(tokens),start+4)+1):
            token=' '.join(tokens[start:end])
            if not re.fullmatch(r'\(?[-−]?(?:\d{1,3}(?:[ ,]\d{3})+|\d+)(?:\.\d+)?\)?%?',token):continue
            if ('(' in token)!=(')' in token):continue
            negative=token.startswith('(')
            v=float(token.strip('()%').replace('−','-').replace(' ','').replace(',',''))
            yield from parse(end,values+[(-v if negative else v)])
    out=set(parse(0,[]))
    return next(iter(out)) if len(out)==1 else None

def extract(company,texts,y,q):
    evidence=[]
    def add(page,label,metric,value,period,unit,method):
        value=float(value.replace(',','')) if isinstance(value,str) else float(value)
        if isfinite(value):
            evidence.append(dict(metric=metric,period_type=period,scope='group',unit=unit,value=value,
                                 source_page=page,source_label=label,extraction_method=method))
    def row(lines,label,count):
        rows=[l for l in lines if re.fullmatch(re.escape(label)+rf' (?:{NUM})(?: (?:{NUM})){{{count-1}}}',l)]
        if len(rows)!=1:return None
        return rows[0][len(label)+1:].split()
    for page,t in enumerate(texts,1):
        lines=[' '.join(l.replace('–','-').replace('−','-').split()) for l in t.splitlines()]
        if company=='Tryg':
            title=f'Reported figures Q{q} {y} and Consensus {y}-{y+2}'
            head=f'Q{q} {y} Q{q} {y} {y} {y+1} {y+2}'
            if title in lines and head in lines and 'DKKm Reported Consensus Consensus Consensus Consensus' in lines:
                for label in ('Insurance revenue','Insurance service result','Pre-tax profit','Claims ratio','Expense ratio','Combined ratio','Solvency ratio'):
                    v=row(lines,label,5)
                    if v:
                        metric=KEYS[label];add(page,label,metric,v[0],'quarter','MDKK' if metric in AMOUNTS else 'percent','explicit_reported_column_not_consensus')
            if f'Financial highlights Q{q} {y}' in lines:
                text=' '.join(lines)
                vals=re.findall(rf'\(return on own funds\) was ({NUM})% in Q{q}\b',text,re.I)
                if len(vals)==1:add(page,'ROOF','return_on_equity',vals[0],'quarter','percent','explicit_current_quarter_issuer_statement')
        elif company=='Sampo':
            # Exact period labels are resolved before looking at any values.
            # Historical comparatives and different segments are excluded.
            if 'Group: results and key figures' in lines:
                headers=[l.split()[1:] for l in lines if l.startswith('EURm ') and f'Q{q}/{y}' in l]
                if len(headers)==1:
                    cols=re.findall(r'(?:1-\d{1,2}/20\d{2}|Q[1-4]/20\d{2}|FY 20\d{2})',' '.join(headers[0]))
                    if ' '.join(cols)==' '.join(headers[0]) and cols.count(f'Q{q}/{y}')==1:
                        for label in ('Insurance revenue, net','Underwriting result','Profit before taxes','Risk ratio, %','Cost ratio, %','Combined ratio, %'):
                            v=row(lines,label,len(cols))
                            if not v:continue
                            metric=KEYS[label];unit='EURm' if metric in AMOUNTS else 'percent'
                            for period,column in [('quarter',f'Q{q}/{y}'),('ytd',f'1-{3*q}/{y}' if q<4 else f'FY {y}')]:
                                if cols.count(column)==1:add(page,label,metric,v[cols.index(column)],period,unit,'explicit_group_period_column')
            if 'Solvency II SCR and own funds' in lines:
                headers=[l for l in lines if l.startswith('EURm ') and f'Q{q}/{y}' in l]
                if len(headers)==1:
                    cols=re.findall(r'(?:Q[1-4]/20\d{2}|FY 20\d{2})',headers[0][5:])
                    if ' '.join(cols)==headers[0][5:] and cols.count(f'Q{q}/{y}')==1:
                        v=row(lines,'Solvency II ratio,%',len(cols))
                        if v:add(page,'Solvency II ratio','solvency_ratio',v[cols.index(f'Q{q}/{y}')],'quarter','percent','explicit_group_solvency_period_column')
        elif company=='Protector':
            compact=' '.join(lines)
            # The issuer's consolidated income statement has explicitly ordered
            # quarter and cumulative columns; use the net (not gross) claims row.
            from import_group_ytd import ytd_header
            if 'Income statement' in lines and 'Insurance service result' in compact and 'Net result from reinsurance contracts held' in compact and re.search(r'(?:NOKm|NOK million)',compact,re.I):
                header=ytd_header(lines[:15],y,q)
                if header:
                    count,qcol,ycol,pcol=header
                    labels={'Insurance revenue':'insurance_revenue','Insurance service result':'insurance_service_result',
                        'Profit/(loss) before tax':'profit_before_tax','Loss ratio, net of reinsurance':'loss_ratio',
                        'Cost ratio':'expense_ratio','Combined ratio':'combined_ratio'}
                    for label,key in labels.items():
                        found=[]
                        for l in lines:
                            m=re.fullmatch(re.escape(label)+r'(?:\s*[¹²³*]+)?\s+(.+)',l,re.I)
                            if not m:continue
                            vals=number_columns(m.group(1),count)
                            if vals is not None:found.append(vals)
                        if len(found)!=1:continue
                        vals=found[0];unit='MNOK' if key in AMOUNTS else 'percent'
                        add(page,label,key,vals[qcol],'quarter',unit,'explicit_issuer_income_statement')
                        add(page,label,key,vals[ycol],'ytd',unit,'explicit_issuer_income_statement')
            if 'Capital development' in lines and re.search(r'Eligible Own Funds',compact,re.I) and re.search(r'SCR ratio\s+(\d+(?:\.\d+)?)\s*%',compact,re.I):
                vals=re.findall(r'\bSCR ratio\s+(\d+(?:\.\d+)?)\s*%',compact,re.I)
                if len(set(vals))==1:add(page,'SCR ratio','solvency_ratio',vals[0],'quarter','percent','issuer_capital_development_heading')
        elif company=='Alm. Brand':
            compact=' '.join(lines)
            if f'Financial highlights, Q{q}' in lines and 'Financial results' in lines and f'Q{q} {y} Q{q} {y-1}' in lines and 'DKKm' in compact:
                labels={'Insurance revenue':'insurance_revenue','Insurance service result':'insurance_service_result','Combined ratio':'combined_ratio'}
                for label,key in labels.items():
                    # Left prose and right table can share the same extracted
                    # line. Require a unique exact label and the two table cells.
                    values=[]
                    for l in lines:
                        m=re.search(r'(?<![\w])'+re.escape(label)+rf' ({NUM}) ({NUM})(?![\d.,])',l)
                        if m:values.append((m.group(1),m.group(2)))
                    if len(set(values))==1:
                        add(page,label,key,values[0][0],'quarter','MDKK' if key in AMOUNTS else 'percent','explicit_financial_results_columns')
            # Q3 highlights use an unambiguous group-level prose statement.
            if f'Q{q} highlights' in lines and f'Q{q} {y-1} Q{q} {y}' in compact:
                vals=re.findall(rf'The expense ratio increased slightly to ({NUM}) \(({NUM})\)',compact,re.I)
                if len(set(vals))==1:add(page,'Expense ratio','expense_ratio',vals[0][0],'quarter','percent','issuer_group_highlights')
                # Charts are excluded here unless physically mapped to period.
        elif company=='Storebrand':
            # Do not read TTM combined ratio or annualised ROE from chart positions.
            if f'Solvency position and sensitivities Q{q} {y}' in lines and any('Storebrand Group' in l for l in lines):
                vals=re.findall(rf'SII-margin Q{q} ({NUM})%', ' '.join(lines))
                if len(set(vals))==1:
                    for period in ('quarter','ytd'):
                        add(page,'SII-margin','solvency_ratio',vals[0],period,'percent','explicit_group_period_end_point')
    # Multiple inconsistent extracts are not silently resolved.
    grouped={}
    for e in evidence:grouped.setdefault((e['metric'],e['period_type'],e['unit']),[]).append(e)
    return [v[0] for v in grouped.values() if len({e['value'] for e in v})==1]

def storebrand_flow_tables(raw,y,q):
    """Insurance APM table with rotated text: use reading order plus physical header check."""
    import pdfplumber
    out=[]
    with pdfplumber.open(io.BytesIO(raw)) as pdf:
        for page,p in enumerate(pdf.pages,1):
            text=p.extract_text(use_text_flow=True) or ''
            lines=[' '.join(l.split()) for l in text.splitlines()]
            if not all(x in text for x in ('Insurance premiums f.o.a.','Cash equivalent earnings from operations','Profit per business line','Insurance profit')):continue
            # Confirm header positions from the PDF itself, not text flow.
            # A three-way header (Qn, Year to date, Full year) must sit above
            # five year values in the same x-order.
            words=p.extract_words(use_text_flow=True,keep_blank_chars=False)
            ywords=sorted([w for w in words if w['text'] in (str(y),str(y-1))],key=lambda w:(w['top'],w['x0']))
            heads=[]
            for word in ywords:
                same=sorted([w for w in ywords if abs(w['top']-word['top'])<2],key=lambda w:w['x0'])
                if [w['text'] for w in same]==[str(y),str(y-1),str(y),str(y-1),str(y-1)]:
                    above=[w for w in words if 0<word['top']-w['top']<20]
                    quarter=[w for w in above if w['text']==f'Q{q}']
                    ytd=[w for w in above if w['text']=='Year']
                    fy=[w for w in above if w['text']=='Full']
                    if quarter and ytd and fy and min(w['x0'] for w in quarter)<min(w['x0'] for w in ytd)<min(w['x0'] for w in fy):heads.append(word['top'])
            if not heads:continue
            for label,key in [('Insurance premiums f.o.a.','insurance_revenue'),('Cash equivalent earnings from operations','insurance_service_result')]:
                matches=[number_columns(l[len(label):],5) for l in lines if l.startswith(label+' ')]
                matches=[v for v in matches if v is not None]
                if len(matches)!=1:continue
                for period,col in [('quarter',0),('ytd',2)]:
                    out.append(dict(metric=key,period_type=period,scope='group',unit='MNOK',value=matches[0][col],
                        source_page=page,source_label=label,extraction_method='insurance_apm_physical_period_header_and_text_flow'))
    return out

def gjensidige_positioned_metrics(raw,y,q):
    """Read labelled group capital / annualised ROE from physical chart regions."""
    import pdfplumber
    out=[]
    with pdfplumber.open(io.BytesIO(raw)) as pdf:
        for page,p in enumerate(pdf.pages,1):
            text=p.extract_text() or ''
            if not ('Gjensidige Forsikring Group' in text and f'Q{q} {y}' in text and 'Annualised, YTD' in text):continue
            if not ('Highlights of the quarter' in text and 'Solvency ratio' in text and 'Return on equity' in text):continue
            words=p.extract_words()
            for label,metric,period in [('Solvency ratio','solvency_ratio','quarter'),('Return on equity','return_on_equity','ytd')]:
                phrase=label.split()
                candidates=[]
                for i,w in enumerate(words):
                    if [x['text'].rstrip('¹*') for x in words[i:i+len(phrase)]]!=phrase:continue
                    group=words[i:i+len(phrase)]
                    x=(group[0]['x0']+group[-1]['x1'])/2;top=min(a['top'] for a in group)
                    # The KPI is immediately above its own caption in the
                    # same circular indicator; neighbouring ratio not eligible.
                    near=[a for a in words if re.fullmatch(r'\d+(?:\.\d+)?%',a['text']) and
                          0<top-a['bottom']<p.height*.20 and abs((a['x0']+a['x1'])/2-x)<p.width*.045]
                    if len(near)==1:candidates.append(float(near[0]['text'][:-1]))
                if len(set(candidates))==1:
                    out.append(dict(metric=metric,period_type=period,scope='group',unit='percent',value=candidates[0],
                                    source_page=page,source_label=label,extraction_method='physically_labelled_group_kpi_and_explicit_ytd_footnote'))
    return out

def reconcile(company,y,q,feed,report_docs,presentation,texts,*,additional=()):
    """Compare independently extracted presentation values with fingerprint-rechecked report observations."""
    result=[]
    for p in [*extract(company,texts,y,q),*additional]:
        candidates=[r for r in feed.get('observations',[]) if
                    (r.get('company'),r.get('year'),r.get('quarter'),r.get('scope'),
                     r.get('metric'),r.get('period_type'),r.get('unit'))==
                    (company,y,q,'group',p['metric'],p['period_type'],p['unit']) and
                    any(d['expected_fingerprint_matches'] and d['source_sha256']==r.get('source_sha256')
                        and d['requested_url']==r.get('source_url') and d['source_sha256']!=presentation['source_sha256']
                        for d in report_docs)]
        if len(candidates)!=1:continue
        r=candidates[0]
        delta=abs(Decimal(str(r['value']))-Decimal(str(p['value'])))
        # Same reported precision, no broad numerical tolerance.
        result.append(dict(metric=p['metric'],period_type=p['period_type'],scope='group',unit=p['unit'],
                           status='match' if delta==0 else 'conflict',value=p['value'],report_value=r['value'],
                           method='independent_presentation_extraction_and_report_fingerprint_recheck',
                           report={k:r[k] for k in ('source_url','source_sha256','source_page')},
                           presentation=dict(source_url=presentation['url'],source_sha256=presentation['source_sha256'],
                                             source_page=p['source_page'],source_label=p['source_label'],extraction_method=p['extraction_method'])))
    return result
