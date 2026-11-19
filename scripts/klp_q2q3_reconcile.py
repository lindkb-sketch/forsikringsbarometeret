#!/usr/bin/env python3
"""Verify isolated Q2/Q3 2026 amounts against issuer HIÅ, fail closed."""
import hashlib, io, json, re
from decimal import Decimal
from pathlib import Path
from import_extended_pdfs import download
from klp_ratio_reconciliation import reconcile

AMOUNTS={'insurance_revenue':'Forsikringsinntekter',
'gross_claims_cost':'Forsikringskostnader',
'operating_expenses':'Forsikringsrelaterte driftskostnader',
'reinsurance_result':'Gjenforsikringsresultat',
'insurance_service_result':'Forsikringsresultat etter gjenforsikring'}
RATIOS={'gross_loss_ratio':'Skadeprosent brutto',
'reinsurance_ratio':'Gjenforsikringsprosent',
'loss_ratio':'Skadeprosent etter gjenforsikring',
'expense_ratio':'Kostnadsprosent',
'combined_ratio':'Totalskadeprosent'}
NUM=re.compile(r'-?\d{1,3}(?: \d{3})*(?:,\d+)?')

def columns(text,label,expected=5,percent=False):
    pattern=re.compile(r'^(?:\d+\s+)?'+re.escape(label)+r'\s+(.+)$',re.I)
    lines=[m.group(1) for line in text.splitlines() if (m:=pattern.match(line.strip()))]
    if len(lines)!=1:raise ValueError('Missing or ambiguous issuer row '+label)
    tokens=(re.findall(r'(-?\d{1,3}(?:,\d+)?)\s*%',lines[0]) if percent
            else NUM.findall(lines[0]))
    if len(tokens)!=expected:raise ValueError('Unexpected column count for '+label)
    return [Decimal(t.replace(' ','').replace(',','.')) for t in tokens]

def verify_pages(texts,quarter,url,sha):
    if quarter not in (2,3) or len(texts)<20:raise ValueError('Unexpected quarter/pages')
    rp=next((i for i,t in enumerate(texts) if re.search(r'^Resultatregnskap$',t,re.M)
             and 'NOTE MILLIONER KRONER' in t),None)
    np=next((i for i,t in enumerate(texts) if 'Note 10 Nøkkeltall - akkumulert' in t
             and 'Totalskadeprosent' in t),None)
    if rp is None or np is None:raise ValueError('Missing issuer result/HIÅ note')
    result,note=texts[rp],texts[np]
    header=re.search(r'NOTE MILLIONER KRONER\s+(.+)',result)
    date={2:'30.06.2026',3:'30.09.2026'}[quarter]
    if not header or not header.group(1).startswith(
            f'{quarter}. kvartal 2026 {quarter}. kvartal 2025') or date not in header.group(1):
        raise ValueError('Unexpected isolated quarter / HIÅ column order')
    if not re.search(r'MILLIONER KRONER\s+'+str(quarter)+r'\. kvartal 2026\s+',note):
        raise ValueError('Unexpected HIÅ KPI column order')
    rows={k:columns(result,label) for k,label in AMOUNTS.items()}
    reported={k:columns(note,label,percent=True)[0] for k,label in RATIOS.items()}
    def components(idx):
        revenue=rows['insurance_revenue'][idx]
        gross=-rows['gross_claims_cost'][idx]
        expense=-rows['operating_expenses'][idx]
        reins=-rows['reinsurance_result'][idx]
        net=rows['insurance_service_result'][idx]
        if min(revenue,gross,expense,reins)<=0:raise ValueError('Invalid issuer signs')
        if abs(revenue-gross-expense-reins-net)>Decimal('0.25'):
            raise ValueError('Result accounting reconciliation failed')
        return {'insurance_revenue':float(revenue),'gross_claims_cost':float(gross),
                'operating_expenses':float(expense),'reinsurance_effect':float(reins)}
    basis={'company':'KLP Skadeforsikring','year':2026,'quarter':quarter,
           'scope':'company','currency':'NOK','unit':'NOK million',
           'source_url':url,'source_sha256':sha,'issuer_definition_verified':True}
    q={**basis,'period_type':'quarter','source_pages':[rp+1],
       'ratio_components':components(0)}
    y={**basis,'period_type':'ytd','source_pages':[rp+1,np+1],
       'ratio_components':components(2),
       'reported_ratios':{k:float(v) for k,v in reported.items()}}
    result=reconcile(q,y)
    result.update({'reported_quarter_amounts':{k:float(v[0]) for k,v in rows.items()},
                   'reported_ytd_amounts':{k:float(v[2]) for k,v in rows.items()},
                   'reported_ytd_ratios':{k:float(v) for k,v in reported.items()},
                   'status':'issuer_pdf_quarter_and_ytd_reconciled_not_published'})
    return result

def run(url,quarter):
    raw=download(url,'KLP Skadeforsikring')
    import pdfplumber
    with pdfplumber.open(io.BytesIO(raw)) as pdf:
        texts=[p.extract_text(layout=False) or '' for p in pdf.pages]
    return verify_pages(texts,quarter,url,hashlib.sha256(raw).hexdigest())

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument('--evidence',required=True)
    p.add_argument('--out',required=True)
    args=p.parse_args()
    report=json.loads(Path(args.evidence).read_text())
    output={}
    for quarter in (2,3):
        source=report['periods'].get(str(quarter),{})
        if not source.get('url'):raise SystemExit('Missing issuer PDF Q'+str(quarter))
        item=run(source['url'],quarter)
        if item['source_documents'][0]['source_sha256']!=source['sha256']:
            raise SystemExit('Issuer PDF changed since discovery')
        output[str(quarter)]=item
        print('KLP_REAL_PDF_HIA_RECONCILED_Q'+str(quarter),json.dumps(item,sort_keys=True))
    dest=Path(args.out);dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n')
