#!/usr/bin/env python3
"""Read missing group HIÅ KPIs from the already verified issuer PDFs.

Do not derive return on equity from quarterly averages, or treat a prior
quarter's solvency as the current balance-sheet snapshot. For revenue growth
the comparison layer uses the same-scope current and previous HIÅ amounts.
"""
import hashlib
import io
import json
import re
import math
import pdfplumber
from audit_financials import DATA,audit
from ingest_official_pdf import download
from publish_geographic_workbooks import atomic_write
from sampo_group_kpis import _columns as sampo_columns,CELL as SAMPO_CELL

TARGETS=('Fremtind','Gjensidige','Tryg','Protector','Sampo')
CORE={'insurance_revenue','insurance_service_result','combined_ratio','loss_ratio','expense_ratio'}
FOOT=r'(?:\s*[¹²³⁴⁵⁶⁷⁸⁹⁰*]+|\s*[a-z]\))?'
NUM=r'[-−]?\d{1,3}(?:,\d{3})*(?:\.\d+)?|[-−]?\d+(?:\.\d+)?'
DASH_TRANS=str.maketrans('‐‑‒–—−','------')

def ytd_header(lines,year,q):
    """Explicit current/prior isolated and current/prior cumulative columns."""
    # Normalize only whitespace/dashes, not the dates or column ordering.
    end={1:'31.03',2:'30.06',3:'30.09',4:'31.12'}[q]
    for i in range(len(lines)):
        for n in (1,2,3):
            text=' '.join(' '.join(lines[i:i+n]).translate(DASH_TRANS).split())
            cq=rf'Q\s*{q}\s+{year}'
            pq=rf'Q\s*{q}\s+{year-1}'
            if q==1:
                if re.search(cq+r'\s+'+pq+r'\s+(?:FY\s+)?'+str(year-1)+r'\b',text,re.I):
                    return 3,0,0,1
                if re.search(cq+r'\s+'+pq+r'\b',text,re.I):
                    return 2,0,0,1
                continue
            cum=rf'(?:Q1\s*-\s*Q{q}|YTD|HIÅ|Hittil i år|{ {2:"H1",3:"9M",4:"FY"}[q]})'
            if re.search(cq+r'\s+'+pq+r'\s+'+cum+rf'\s+{year}\s+'+cum+rf'\s+{year-1}\b',text,re.I):
                return (5 if re.search(cum+rf'\s+{year-1}\s+(?:FY\s+)?{year-1}\b',text,re.I) else 4),0,2,3
            # Fremtind labels the cumulative columns by reporting date.
            date_columns=rf'{re.escape(end)}\.{year}\s+{re.escape(end)}\.{year-1}\s+31\.12\.{year-1}\b'
            if re.search(cq+r'\s+'+pq+r'\s+'+date_columns,text,re.I):
                return 5,0,2,3
            # Tryg and Fremtind may put period labels and years on two rows.
            prefix=rf'Q\s*{q}\s+Q\s*{q}\s+{cum}\s+{cum}'
            if re.search(prefix+rf'\s+(?:FY\s+|Full Year\s+)?(?:DKKm\s+|NOKm\s+|MNOK\s+)?{year}\s+{year-1}\s+{year}\s+{year-1}\s+{year-1}\b',text,re.I):
                return 5,0,2,3
            # Fremtind's header can name the same cumulative date span once,
            # followed by the two explicitly printed years.
            if re.search(cq+r'\s+'+pq+rf'\s+(?:01\.01\s*-\s*(?:30\.06|30\.09|31\.12))\s+{year}\s+{year-1}\s+{year-1}\b',text,re.I):
                return 5,0,2,3
            if q==4 and re.search(cq+r'\s+'+pq+rf'\s+(?:FY\s+)?{year}\s+(?:FY\s+)?{year-1}\b',text,re.I):
                return 4,0,2,3
    return None

def parse_values(tail,count,norwegian=False):
    tail=tail.strip()
    if norwegian:
        cells=re.findall(r'([-−]?\d+(?:,\d+)?)\s*%',tail)
        if len(cells)==count:return [float(v.replace(',','.').replace('−','-')) for v in cells]
        return None
    # The table may include a separate '%' unit, then each value may carry %.
    tail=re.sub(r'^\s*%\s+','',tail)
    cells=re.sub(r'\s*%','',tail).split()
    if len(cells)!=count or not all(re.fullmatch(r'\(?[-−]?\d[\d,]*(?:\.\d+)?\)?',c) for c in cells):
        return None
    return [float(c.strip('()').replace(',','').replace('−','-'))*(-1 if c.startswith('(') else 1) for c in cells]

def obs(anchor,metric,year,value,page,definition,period='ytd'):
    return dict(company=anchor['company'],scope='group',source_scope='group',
        year=year,quarter=anchor['quarter'],period_type=period,metric=metric,
        value=value,unit=anchor['unit'] if metric in ('insurance_revenue','insurance_service_result','profit_before_tax') else 'percent',
        status='reported',source_type='official_quarterly_report',
        source_url=anchor['source_url'],source_sha256=anchor['source_sha256'],source_page=page,
        source_document_period=f"Q{anchor['quarter']} {anchor['year']}",source_definition=definition)

def check_quarter(metric,val,quarter_values):
    # Never use a cumulative/segment column that disagrees with the
    # independently verified isolated-quarter metric.
    if metric in quarter_values and abs(val-quarter_values[metric])>0.11:
        raise ValueError(f'Quarter anchor mismatch for {metric}: {val} vs {quarter_values[metric]}')

def sampo(pages,anchor,quarter_values):
    y,q=anchor['year'],anchor['quarter']
    hits=[]
    labels={
        'insurance_revenue':(r'Insurance revenue(?:\s*\(incl\.\s*brokerage\))?(?:,\s*net)?','EURm'),
        'insurance_service_result':(r'Underwriting result','EURm'),
        'combined_ratio':(r'Combined ratio,?','%'),
        'loss_ratio':(r'Risk ratio,?','%'),
        'expense_ratio':(r'Cost ratio,?','%')}
    for page,text in pages:
        if 'Financial overview' not in text or 'Nordic underlying development' not in text:continue
        block=text.split('Nordic underlying development',1)[0]
        layout=sampo_columns(block,y,q)
        if not layout:continue
        count,qcol,ycol=layout
        # The issuer's same table also identifies prior-year YTD by its
        # explicit period label, not a presumed positional offset.
        from sampo_group_kpis import PERIOD,DASHES
        prior=(1,3*q,y-1) if q!=4 else y-1
        header=[]
        for line in block.splitlines():
            norm=line.translate(str.maketrans(DASHES,'-'*len(DASHES)))
            tokens=[tuple(map(int,m.group(1,2,3))) if m.group(1) else int(m.group(4)) for m in PERIOD.finditer(norm)]
            current=(3*q-2,3*q,y)
            target=(1,3*q,y) if q!=4 else y
            if len(tokens)==count and current in tokens and target in tokens and tokens.count(prior)==1:
                header.append(tokens)
        if len(header)!=1:continue
        pcol=header[0].index(prior)
        rows=[]
        for metric,(label,unit) in labels.items():
            matches=[m.group(1) for l in block.splitlines() if (m:=re.fullmatch(r'\s*'+label+FOOT+r'\s+'+re.escape(unit)+r'\s+(.+?)\s*',l,re.I))]
            if len(matches)!=1:raise ValueError('Sampo HIÅ row not unique: '+metric+' '+repr([l for l in block.splitlines() if re.search(label,l,re.I)][:5]))
            cells=matches[0].split()
            if len(cells)!=count or any(not SAMPO_CELL.fullmatch(c) or c in ('-','–','—') for c in cells):
                raise ValueError('Sampo HIÅ column mismatch: '+metric)
            vals=[float(c.replace(',','').replace('−','-')) for c in cells]
            check_quarter(metric,vals[qcol],quarter_values)
            definition='Sampo Group official financial overview; explicitly labelled HIÅ columns'
            rows.append(obs(anchor,metric,y,vals[ycol],page,definition))
            if metric=='insurance_revenue':
                rows.append(obs(anchor,metric,y-1,vals[pcol],page,definition+' (explicit prior-year HIÅ comparative)'))
        hits.append(rows)
    if len(hits)!=1:raise ValueError('Sampo HIÅ financial overview not unique')
    return hits[0]

def protector(pages,anchor,quarter_values):
    y,q=anchor['year'],anchor['quarter'];hits=[]
    labels={'insurance_revenue':r'Insurance revenue','insurance_service_result':r'Insurance service result',
            'combined_ratio':r'Combined ratio','loss_ratio':r'Loss ratio,\s*net of reinsurance','expense_ratio':r'Cost ratio'}
    for page,text in pages:
        if not all(m in text for m in ('Income overview','NOKm','Insurance service result','Net result from reinsurance contracts held')):continue
        lines=text.splitlines()
        header=ytd_header(lines[:12],y,q)
        if not header:continue
        count,qcol,ycol,pcol=header;rows=[]
        for metric,label in labels.items():
            candidates=[]
            for line in lines:
                m=re.fullmatch(r'\s*'+label+FOOT+r'\s+(.+?)\s*',line,re.I)
                if not m:continue
                vals=parse_values(m.group(1),count)
                if vals is not None:candidates.append(vals)
            if len(candidates)!=1:
                raise ValueError('Protector HIÅ row not unique: '+metric+' '+repr([l for l in lines if re.search(label,l,re.I)][:6]))
            vals=candidates[0]
            check_quarter(metric,vals[qcol],quarter_values)
            definition='Protector issuer group income overview; explicitly labelled cumulative period'
            rows.append(obs(anchor,metric,y,vals[ycol],page,definition))
            if metric=='insurance_revenue':
                rows.append(obs(anchor,metric,y-1,vals[pcol],page,definition+' (prior-year comparative)'))
        hits.append(rows)
    if len(hits)!=1:raise ValueError('Protector HIÅ income overview not unique')
    return hits[0]

def returns(pages,anchor,quarter_values,positioned=None):
    c=anchor['company'];y,q=anchor['year'],anchor['quarter'];hits=[];diag=[]
    if c=='Gjensidige':
        for page,t in pages:
            for variant in [t,*((positioned or {}).get(page,[]))]:
                compact=' '.join(variant.translate(DASH_TRANS).split())
                # Normalize a hyphenated line break but never remove intervening
                # prose to manufacture a matching cumulative statement.
                pattern=r'annualis(?:ed|z)\s+return on equity\s+for\s+the\s+year\s*[- ]\s*to\s*[- ]\s*date\s+was\s+([-]?\d+(?:\.\d+)?)\s+per\s+cent'
                for m in re.finditer(pattern,compact,re.I):
                    hits.append((page,float(m.group(1))))
                if re.search(r'return on equity',compact,re.I):
                    diag.extend((page,m.group()[:280]) for m in re.finditer(r'.{0,50}return on equity.{0,160}',compact,re.I))
        definition='ROE annualised; issuer explicitly reports year-to-date'
    else:
        labels={'Protector':r'Return on equity,?\s*annualis(?:ed|z)',
                'Tryg':r'Return on Own Funds\s*(?:\(%\))?',
                'Fremtind':r'(?:transaksjonen\s+med\s+)?Eika\s*Forsikring\s+AS'}
        definition={'Protector':'ROE annualised; issuer HIÅ table','Tryg':'ROOF annualised; issuer HIÅ table',
                    'Fremtind':'Annualisert egenkapitalavkastning justert for transaksjonen med Eika Forsikring AS; HIÅ'}[c]
        for page,t in pages:
            lines=t.splitlines()
            for i,line in enumerate(lines):
                pattern=labels[c]
                match=re.search(r'^\s*'+pattern+FOOT+r'\s+(?=[-−\d%])(.+?)\s*$',line,re.I)
                if c=='Fremtind':
                    if not re.search(r'annualisert\s+egenkapitalavkastning\s+justert\s+for',' '.join(lines[max(0,i-7):i+1]),re.I):continue
                    match=re.search(pattern+FOOT+r'\s+(.+?)\s*$',line,re.I)
                if not match:continue
                header=ytd_header(lines[:i],y,q)
                if not header:
                    diag.append((page,line,lines[:min(i,12)]));continue
                count,qcol,ycol,_=header
                vals=parse_values(match.group(1),count,norwegian=c=='Fremtind')
                if vals is None:
                    diag.append((page,line,'unexpected column count'));continue
                try:check_quarter('return_on_equity',vals[qcol],quarter_values)
                except ValueError as exc:
                    diag.append((page,line,str(exc)));continue
                hits.append((page,vals[ycol]))
    distinct={v for _,v in hits}
    if len(distinct)!=1:
        raise ValueError(c+' HIÅ equity return not unique: '+repr(hits)+'; rows/headers='+repr(diag[:4]))
    page,val=hits[0]
    return [obs(anchor,'return_on_equity',y,val,page,definition)]

def latest_anchor(rows,company):
    matches=[r for r in rows if r.get('company')==company and r.get('scope')=='group'
        and r.get('period_type')=='quarter' and r.get('metric')=='insurance_revenue'
        and r.get('source_type')=='official_quarterly_report' and r.get('status') in ('reported','calculated')]
    if not matches:return None
    current=max((r['year'],r['quarter']) for r in matches)
    candidates=[r for r in matches if (r['year'],r['quarter'])==current]
    if len(candidates)!=1:raise ValueError(company+' ambiguous latest revenue anchor')
    anchor=candidates[0]
    if anchor.get('source_document_period') not in (None,f'Q{current[1]} {current[0]}'):
        raise ValueError(company+' wrong document period')
    return anchor

def collect(rows,downloader=download):
    additions=[];errors=[]
    for c in TARGETS:
        anchor=latest_anchor(rows,c)
        if not anchor:continue
        y,q=anchor['year'],anchor['quarter']
        current=[r for r in rows if r.get('company')==c and r.get('scope')=='group' and (r['year'],r['quarter'])==(y,q)]
        values={r['metric']:r['value'] for r in current if r['period_type']=='quarter'}
        needed=CORE if c in ('Sampo','Protector') else set()
        if c!='Sampo':needed=needed|{'return_on_equity'}
        present={r['metric'] for r in current if r['period_type']=='ytd'}
        prior_revenue=any(r.get('company')==c and r.get('scope')=='group' and (r.get('year'),r.get('quarter'),r.get('period_type'),r.get('metric'))==(y-1,q,'ytd','insurance_revenue') for r in rows)
        missing_prior=c in ('Sampo','Protector') and not prior_revenue
        if needed<=present and not missing_prior:continue
        try:
            raw=downloader(anchor['source_url'])
            if not raw.startswith(b'%PDF-') or hashlib.sha256(raw).hexdigest()!=anchor['source_sha256']:
                raise ValueError('Issuer document fingerprint differs from verified quarter')
            positioned={}
            with pdfplumber.open(io.BytesIO(raw)) as pdf:
                pages=[(i+1,p.extract_text() or '') for i,p in enumerate(pdf.pages)]
                if c=='Gjensidige':
                    for page,text in pages:
                        if not re.search(r'return on equity|year.to.date',text,re.I):continue
                        p=pdf.pages[page-1]
                        variants=[p.extract_text(use_text_flow=True) or '']
                        for a,b in ((0,.5),(.5,1),(0,.34),(.33,.67),(.66,1),(0,.55),(.45,1),(.30,.70)):
                            variants.append(p.crop((p.width*a,0,p.width*b,p.height)).extract_text() or '')
                        positioned[page]=list(dict.fromkeys(variants))
        except (ValueError,OSError,TimeoutError) as exc:
            errors.append((c,'PDF',str(exc)));continue
        tasks=[]
        if c=='Sampo' and (not CORE<=present or missing_prior):tasks.append(('core',sampo))
        if c=='Protector' and (not CORE<=present or missing_prior):tasks.append(('core',protector))
        if c!='Sampo' and 'return_on_equity' not in present:tasks.append(('return',returns))
        for name,parser in tasks:
            try:
                extracted=parser(pages,anchor,values,positioned=positioned) if parser is returns else parser(pages,anchor,values)
                additions.extend(extracted)
                print('GROUP_YTD_LIVE_VERIFIED',c,name,[(x['year'],x['metric'],x['value'],x['source_page']) for x in extracted],flush=True)
            except ValueError as exc:
                errors.append((c,name,str(exc)))
    return additions,errors

def run(path=DATA):
    data=json.loads(path.read_text(encoding='utf-8'))
    if not audit(data)['ok']:raise ValueError('Baseline audit failed')
    rows=data['observations']
    added,errors=collect(rows)
    key=lambda r:(r['company'],r['year'],r['quarter'],r['scope'],r['period_type'],r['metric'])
    index={key(r):r for r in rows if r.get('scope')=='group'}
    n=0
    for row in added:
        k=key(row);old=index.get(k)
        if old:
            if abs(old['value']-row['value'])>0.11:
                raise ValueError('Conflicting verified HIÅ source '+repr(k))
            continue
        rows.append(row);index[k]=row;n+=1
    # Correct the legacy label only after the same document explicitly states
    # the YTD value. A distinct reported isolated-quarter figure is retained.
    migrated=0
    for row in added:
        if row['company']!='Gjensidige' or row['metric']!='return_on_equity' or row['period_type']!='ytd':continue
        old=index.get((row['company'],row['year'],row['quarter'],'group','quarter','return_on_equity'))
        if old and old.get('source_sha256')==row['source_sha256'] and old['value']==row['value'] and old.get('source_definition')=='ROE annualised':
            rows.remove(old);migrated+=1
            print('GJENSIDIGE_LEGACY_ROE_RECLASSIFIED_YTD',row['year'],row['quarter'],row['value'],flush=True)
    if n or migrated:
        if not audit(data)['ok']:raise ValueError('New HIÅ rows failed financial audit')
        atomic_write(path,data)
    for c,name,error in errors:
        print('::warning::GROUP_YTD_UNVERIFIED',c,name,error[:1600],flush=True)
    print('GROUP_YTD_IMPORT',json.dumps({'added':n,'unverified':errors},ensure_ascii=False),flush=True)
    return added,errors

if __name__=='__main__':run()
