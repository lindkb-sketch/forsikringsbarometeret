#!/usr/bin/env python3
"""Strict Storebrand Q3 2026 import, from issuer PDFs; no guesswork or scope mixing.

Usage: python scripts/import_storebrand_reports.py --group path.pdf --norway path.pdf
PDFs are verified by their document title and their named, column-headed tables.
Source URLs point to official issuer archive pages unless --group-url/--norway-url
provide direct official PDF links. PDF SHA-256 preserves exact file provenance.
"""
import argparse, hashlib, json, re, tempfile, os
from pathlib import Path
import pdfplumber
from audit_financials import audit, ROOT

GROUP_ARCHIVE='https://www.storebrand.no/en/investor-relations/quarterly-reporting/storebrand-asa/2026'
NORWAY_ARCHIVE='https://www.storebrand.no/en/investor-relations/quarterly-reporting/storebrand-forsikring-as'
DATA=ROOT/'data/financial_observations.json'
# Only accept numeric tokens in known table columns. No prose-based extraction.
NUM=re.compile(r'(?<!\S)-?(?:\d{1,3}(?:[ ,]\d{3})+|\d+)(?:[.,]\d+)?%?(?!\S)')

def number(s):
    s=s.strip().replace('%','').replace(' ','')
    if ',' in s and '.' in s: raise ValueError('Ambiguous numeric format: '+s)
    if ',' in s:
        # English group tables have comma thousands; Norwegian subsidiary decimal comma.
        return float(s.replace(',','.'))
    return float(s)

def english(s):
    return float(s.replace(',','').replace('%',''))

def row(text,label,count,parser):
    hits=[]
    for line in text.splitlines():
        m=re.fullmatch(r'\s*'+re.escape(label)+r'\s+(.+?)\s*',line,re.I)
        if not m:continue
        tokens=NUM.findall(m.group(1))
        if len(tokens)==count: hits.append([parser(v) for v in tokens])
    if len(hits)!=1: raise ValueError(f'Expected one {count}-column row for {label!r}; found {len(hits)}')
    return hits[0]

def pages(path,expected,year=2026):
    blob=Path(path).read_bytes()
    if not blob.startswith(b'%PDF-') or len(blob)>35_000_000:raise ValueError('Invalid PDF')
    with pdfplumber.open(path) as pdf:
        texts=[p.extract_text() or '' for p in pdf.pages]
    if expected not in texts[0] or str(year) not in texts[0]:raise ValueError('Wrong Storebrand entity or year')
    return texts,hashlib.sha256(blob).hexdigest()

def obs(scope,year,quarter,period,metric,value,page,url,sha,definition,entity,document_year=2026,document_quarter=3):
    return dict(company='Storebrand',year=year,quarter=quarter,scope=scope,source_scope=scope,
        period_type=period,metric=metric,value=value,unit='percent' if metric.endswith('ratio') or metric=='return_on_equity' or metric=='solvency_ratio' else 'MNOK',
        status='reported',source_url=url,source_page=page,source_type='official_quarterly_report',
        source_sha256=sha,source_document_period=f'Q{document_quarter} {document_year}',source_entity=entity,source_definition=definition)

def parse_group(path,url=GROUP_ARCHIVE,year=2026,quarter=3):
    texts,sha=pages(path,'Storebrand Group',year)
    if quarter in (1,2):return parse_group_early(path,url,year,quarter)
    if quarter not in (3,4) or year < 2025: raise ValueError('Unsupported report period')
    candidates=[(i,text) for i,text in enumerate(texts) if 'Insurance – Results' in text]
    if len(candidates)!=1:raise ValueError('Expected exactly one Group insurance results table')
    insurance_page,t=candidates[0]
    if not (str(year) in t and (('Q3 Q2 Q1' in t) if quarter==3 else re.search(r'Q4\s+Q3\s+Q2\s+Q1',t))):raise ValueError('Group insurance table header changed')
    column_count=8 if quarter==3 else 7
    metrics={'insurance_revenue':('Insurance premiums f.o.a.','APM: Insurance segment premiums f.o.a.; not IFRS insurance revenue'),
             'loss_ratio':('Claims ratio','Insurance segment claims ratio'),
             'expense_ratio':('Cost ratio','Insurance segment cost ratio'),
             'combined_ratio':('Combined ratio','Insurance segment combined ratio')}
    result=[]
    for metric,(label,definition) in metrics.items():
        vals=row(t,label,column_count,english)
        quarter_values=([(quarter,vals[0]),(quarter-1,vals[1]),(quarter-2,vals[2])]
                        if quarter==3 else [(4,vals[0]),(3,vals[1]),(2,vals[2]),(1,vals[3])])
        for q,v in quarter_values:
            result.append(obs('group',year,q,'quarter',metric,v,insurance_page+1,url,sha,definition,'Storebrand ASA / Insurance segment',year,quarter))
        result.append(obs('group',year-1,quarter,'quarter',metric,vals[4],insurance_page+1,url,sha,definition,'Storebrand ASA / Insurance segment',year,quarter))
        result.append(obs('group',year,quarter,'ytd',metric,vals[5],insurance_page+1,url,sha,definition,'Storebrand ASA / Insurance segment',year,quarter))
        result.append(obs('group',year-1,quarter,'ytd',metric,vals[6],insurance_page+1,url,sha,definition,'Storebrand ASA / Insurance segment',year,quarter))
    # Insurance segment result, distinct from total Storebrand Group earnings.
    # The source reports the named operating subtotal, but PDF text extraction
    # may split its long label. Reconstruct from the three reported lines.
    premiums=row(t,'Insurance premiums f.o.a.',column_count,english)
    claims=row(t,'Claims f.o.a.',column_count,english)
    costs=row(t,'Operational cost',column_count,english)
    operating=[round(a+b+c,5) for a,b,c in zip(premiums,claims,costs)]

    operating_q=([(quarter,operating[0]),(quarter-1,operating[1]),(quarter-2,operating[2])]
                 if quarter==3 else [(4,operating[0]),(3,operating[1]),(2,operating[2]),(1,operating[3])])
    for q,v in operating_q:
        result.append(obs('group',year,q,'quarter','insurance_service_result',v,insurance_page+1,url,sha,
            'Insurance segment Cash equivalent earnings from operations','Storebrand ASA / Insurance segment',year,quarter))
    for y,p,v in [(year-1,'quarter',operating[4]),(year,'ytd',operating[5]),(year-1,'ytd',operating[6])]:
        result.append(obs('group',y,quarter,p,'insurance_service_result',v,insurance_page+1,url,sha,
            'Insurance segment Cash equivalent earnings from operations','Storebrand ASA / Insurance segment',year,quarter))
    key_candidates=[(i,text) for i,text in enumerate(texts) if 'Group - Key figures' in text]
    if len(key_candidates)!=1:raise ValueError('Expected exactly one Group key figures table')
    key_page,k=key_candidates[0]
    if str(year) not in k:raise ValueError('Group key figures heading changed')
    for metric,label in [('return_on_equity','Cash return on equity, annualised (%)'),('solvency_ratio','Solvency II ratio (%)')]:
        vals=row(k,label,column_count,english)
        quarter_values=([(quarter,vals[0]),(quarter-1,vals[1]),(quarter-2,vals[2])]
                        if quarter==3 else [(4,vals[0]),(3,vals[1]),(2,vals[2]),(1,vals[3])])
        for q,v in quarter_values:
            result.append(obs('group',year,q,'quarter',metric,v,key_page+1,url,sha,'Group key figures; '+label,'Storebrand ASA',year,quarter))
        result.append(obs('group',year-1,quarter,'quarter',metric,vals[4],key_page+1,url,sha,'Group key figures; '+label,'Storebrand ASA',year,quarter))
        result.append(obs('group',year,quarter,'ytd',metric,vals[5],key_page+1,url,sha,'Group key figures; '+label,'Storebrand ASA',year,quarter))
        result.append(obs('group',year-1,quarter,'ytd',metric,vals[6],key_page+1,url,sha,'Group key figures; '+label,'Storebrand ASA',year,quarter))
    for item in result:item['source_document_period']=f'Q{quarter} {year}'
    return result

def parse_norway(path,url=NORWAY_ARCHIVE,year=2026,quarter=3):
    texts,sha=pages(path,'Storebrand Forsikring',year)
    if quarter in (1,2):return parse_norway_early(path,url,year,quarter)
    if quarter==4:raise ValueError('Storebrand Forsikring AS Q4 must remain blank: no Q4 report')
    if quarter != 3 or year != 2026: raise ValueError('New report layout requires independent validation before import')
    t=texts[3]
    if 'Totalresultat' not in t or not ((('3.kvartal' in t) if quarter==3 else re.search(r'4\.\s*kvartal',t,re.I))) or not ('01.01 - '+('30.09' if quarter==3 else '31.12')) in t:raise ValueError('Norway income statement header changed')
    result=[]
    for metric,label,definition in [
        ('insurance_revenue','Forsikringsinntekter','IFRS 17 forsikringsinntekter'),
        ('insurance_service_result','Totalt forsikringsresultat','IFRS 17 totalt forsikringsresultat etter reassuranse')]:
        vals=row(t,label,5,number)
        for y,p,v in [(year,'quarter',vals[0]),(year-1,'quarter',vals[1]),(year,'ytd',vals[2]),(year-1,'ytd',vals[3])]:
            result.append(obs('norway',y,quarter,p,metric,v,4,url,sha,definition,'Storebrand Forsikring AS'))
    # Storebrand Forsikring AS does not report an expense ratio. Never infer it
    # from the published claims ratio: definitions may differ.
    costs=row(t,'Forsikringskostnader',5,number)
    reinsurance=row(t,'Netto resultat fra reassuransekontrakter',5,number)
    revenue=row(t,'Forsikringsinntekter',5,number)
    insurance_result=row(t,'Totalt forsikringsresultat',5,number)
    for obs_year,period,col in ((year,'quarter',0),(year-1,'quarter',1),(year,'ytd',2),(year-1,'ytd',3)):
        if revenue[col] <= 0: raise ValueError('Insurance revenue must be positive for combined ratio')
        # Report expenses are negative; positive reinsurance result reduces net cost.
        # CR = -(insurance expenses + net reinsurance result) / revenue * 100.
        calculated=round(-(costs[col]+reinsurance[col])/revenue[col]*100, 4)
        check=round((1-insurance_result[col]/revenue[col])*100, 4)
        if abs(calculated-check)>0.03:
            raise ValueError(f'Combined ratio does not reconcile with insurance result: {obs_year} {period}')
        r=obs('norway',obs_year,quarter,period,'combined_ratio',calculated,4,url,sha,
              'Calculated: -(insurance expenses + net reinsurance result) / insurance revenue * 100; IFRS 17',
              'Storebrand Forsikring AS')
        r['status']='calculated'
        r['calculation']='-(Forsikringskostnader + Netto resultat fra reassuransekontrakter) / Forsikringsinntekter * 100'
        r['calculation_inputs']={'insurance_expenses':costs[col], 'net_reinsurance_result':reinsurance[col], 'insurance_revenue':revenue[col]}
        result.append(r)
    # The report states the net claims ratio in prose (page 2); it does not
    # provide a comparable expense ratio. Only the stated claims ratio is used.
    prose=texts[1]
    if not re.search(r'Netto skadeprosent inkludert reassuranse endte på 60 prosent.*?3\.\s*kvartal og 62 prosent.*?hittil i år',prose,re.I|re.S):
        raise ValueError('Reported claims ratios changed or could not be verified')
    for period,value in ((('quarter',60.0),('ytd',62.0)) if quarter==3 else ()):
        result.append(obs('norway',year,quarter,period,'loss_ratio',value,2,url,sha,
                          'Netto skadeprosent inkludert reassuranse; as reported',
                          'Storebrand Forsikring AS'))
    # Solvency is an as-of-date balance-sheet ratio, not a quarterly flow.
    t=texts[10]
    if 'Solvenskapitalkrav og -margin' not in t:raise ValueError('Norway solvency table heading changed')
    v=row(t,'Solvensmargin',2,number)[0]
    result.append(obs('norway',year,quarter,'quarter','solvency_ratio',v,11,url,sha,f'Solvency II margin at Q{quarter} {year} end','Storebrand Forsikring AS'))
    if quarter==4 and not any(r['metric']=='solvency_ratio' for r in result):raise ValueError('Missing Q4 solvency')
    for item in result:item['source_document_period']=f'Q{quarter} {year}'
    return result


def _unique_table(texts, marker):
    hits=[(i,t) for i,t in enumerate(texts) if marker in t]
    if len(hits)!=1: raise ValueError('Expected one Storebrand table: '+marker+'; found '+str(len(hits)))
    return hits[0]

def parse_group_early(path,url=GROUP_ARCHIVE,year=2026,quarter=1):
    if year < 2026 or quarter not in (1,2): raise ValueError('Unsupported Storebrand group period')
    texts,sha=pages(path,'Storebrand Group',year)
    page,t=_unique_table(texts,'Insurance – Results')
    section=t.split('Insurance – Results',1)[1].split('Financial performance',1)[0]
    if not re.search(r'\bQ'+str(quarter)+r'\b',section): raise ValueError('Group period header mismatch: '+repr(section[:900]))
    count=6 if quarter==1 else 8
    metrics={'insurance_revenue':('Insurance premiums f.o.a.','APM: Insurance segment premiums f.o.a.; not IFRS insurance revenue'),
             'loss_ratio':('Claims ratio','Insurance segment claims ratio'),
             'expense_ratio':('Cost ratio','Insurance segment cost ratio'),
             'combined_ratio':('Combined ratio','Insurance segment combined ratio')}
    result=[]
    for metric,(label,definition) in metrics.items():
        vals=row(section,label,count,english)
        result.append(obs('group',year,quarter,'quarter',metric,vals[0],page+1,url,sha,definition,'Storebrand ASA / Insurance segment',year,quarter))
    p=row(section,'Insurance premiums f.o.a.',count,english)
    c=row(section,'Claims f.o.a.',count,english)
    o=row(section,'Operational cost',count,english)
    earnings=round(p[0]+c[0]+o[0],5)
    result.append(obs('group',year,quarter,'quarter','insurance_service_result',
        earnings,page+1,url,sha,'Insurance segment Cash equivalent earnings from operations',
        'Storebrand ASA / Insurance segment',year,quarter))
    keypage,keytext=_unique_table(texts,'Group - Key figures')
    keysection=keytext.split('Group - Key figures',1)[1].split('Financial metrics',1)[0]
    for metric,label in [('return_on_equity','Cash return on equity, annualised (%)'),('solvency_ratio','Solvency II ratio (%)')]:
        vals=row(keysection,label,count,english)
        result.append(obs('group',year,quarter,'quarter',metric,vals[0],keypage+1,url,sha,'Group key figures; '+label,'Storebrand ASA',year,quarter))
    return result

def parse_norway_early(path,url=NORWAY_ARCHIVE,year=2026,quarter=1):
    if year < 2026 or quarter not in (1,2): raise ValueError('Unsupported Storebrand Norway period')
    texts,sha=pages(path,'Storebrand Forsikring',year)
    page,t=_unique_table(texts,'Totalresultat')
    if not re.search(r'0[1-9]\.0[1-9]\s*-\s*(?:31\.03|30\.06)',t) and not ('31.03' if quarter==1 else '30.06') in t:
        raise ValueError('Norway statement period header mismatch')
    count=3 if quarter==1 else 5
    vals={label:row(t,label,count,number) for label in ('Forsikringsinntekter','Totalt forsikringsresultat','Forsikringskostnader','Netto resultat fra reassuransekontrakter')}
    revenue=vals['Forsikringsinntekter'][0];result_value=vals['Totalt forsikringsresultat'][0]
    costs=vals['Forsikringskostnader'][0];reinsurance=vals['Netto resultat fra reassuransekontrakter'][0]
    if revenue<=0:raise ValueError('Invalid Storebrand Norway revenue')
    combined=round(-(costs+reinsurance)/revenue*100,4)
    if abs(combined-(1-result_value/revenue)*100)>0.03:raise ValueError('Storebrand Norway combined ratio reconciliation failed')
    result=[]
    for metric,value,definition in [
        ('insurance_revenue',revenue,'IFRS 17 forsikringsinntekter'),
        ('insurance_service_result',result_value,'IFRS 17 totalt forsikringsresultat etter reassuranse'),
        ('combined_ratio',combined,'Calculated from IFRS 17 insurance costs and net reinsurance')]:
        r=obs('norway',year,quarter,'quarter',metric,value,page+1,url,sha,definition,'Storebrand Forsikring AS',year,quarter)
        if metric=='combined_ratio':
            r.update(status='calculated',calculation='-(Forsikringskostnader + Netto resultat fra reassuransekontrakter) / Forsikringsinntekter * 100',
                     calculation_inputs={'insurance_expenses':costs,'net_reinsurance_result':reinsurance,'insurance_revenue':revenue})
        result.append(r)
    prose=texts[1]
    claim=re.search(r'Netto skadeprosent\s+inkludert reassuranse endte på\s+(\d+)\s+prosent',prose,re.I)
    if not claim:raise ValueError('Storebrand Norway claims ratio not reported')
    result.append(obs('norway',year,quarter,'quarter','loss_ratio',float(claim.group(1)),2,url,sha,'Netto skadeprosent inkludert reassuranse; as reported','Storebrand Forsikring AS',year,quarter))
    solvency=[(i,t) for i,t in enumerate(texts) if 'Solvenskapitalkrav og -margin' in t]
    if len(solvency)!=1:raise ValueError('Storebrand Norway solvency table missing')
    sp,st=solvency[0];margin=row(st,'Solvensmargin',2,number)[0]
    result.append(obs('norway',year,quarter,'quarter','solvency_ratio',margin,sp+1,url,sha,'Solvency II margin at quarter end','Storebrand Forsikring AS',year,quarter))
    return result

def parse_norway_annual_q4(*args, **kwargs):
    """No Q4 observations for Storebrand Forsikring AS without a Q4 report.

    An annual report is not a standalone fourth-quarter report. Neither
    derived Q4 flows nor annual YTD values should populate its Q4 slot.
    """
    raise ValueError('Storebrand Forsikring AS Q4 must remain blank: no Q4 report')


def integrate(existing, incoming):
    result=json.loads(json.dumps(existing)); index={tuple(r[k] for k in ('company','year','quarter','scope','period_type','metric')):i for i,r in enumerate(result['observations'])}
    added=0; updated=0
    for r in incoming:
        key=tuple(r[k] for k in ('company','year','quarter','scope','period_type','metric'))
        if key in index:
            old=result['observations'][index[key]]
            if old['value']!=r['value']:
                # No replacement of an existing official figure without a verifiable newer source date.
                raise ValueError('Conflicting Storebrand observation; manual source-version verification required: '+str(key))
            # Same value: improve provenance only if original did not contain a source SHA.
            if not old.get('source_sha256'):
                result['observations'][index[key]]={**old,**r};updated+=1
        else:
            index[key]=len(result['observations']);result['observations'].append(r);added+=1
    validation=audit(result)
    if not validation['ok']:raise ValueError('Financial audit failed: '+str(validation['errors']))
    return result,added,updated

def run(group,norway,group_url=GROUP_ARCHIVE,norway_url=NORWAY_ARCHIVE,output=DATA):
    if not (group_url.startswith('https://') and norway_url.startswith('https://')):raise ValueError('HTTPS provenance required')
    incoming=parse_group(group,group_url)+parse_norway(norway,norway_url)
    target=Path(output);existing=json.loads(target.read_text())
    result,added,updated=integrate(existing,incoming)
    fd,tmp=tempfile.mkstemp(dir=target.parent,prefix='.storebrand-',suffix='.json')
    try:
        with os.fdopen(fd,'w',encoding='utf-8') as f:json.dump(result,f,ensure_ascii=False,indent=2);f.write('\n')
        os.replace(tmp,target)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)
    return {'parsed':len(incoming),'added':added,'updated_provenance':updated,'group':len(parse_group(group,group_url)),'norway':len(parse_norway(norway,norway_url))}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--group',required=True);p.add_argument('--norway',required=True)
    p.add_argument('--group-url',default=GROUP_ARCHIVE);p.add_argument('--norway-url',default=NORWAY_ARCHIVE)
    p.add_argument('--output',default=str(DATA));a=p.parse_args()
    print(json.dumps(run(a.group,a.norway,a.group_url,a.norway_url,a.output),ensure_ascii=False,indent=2))
