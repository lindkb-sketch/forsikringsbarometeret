#!/usr/bin/env python3
"""Reproduce KLP Skadeforsikring Q1 2026 official quarter KPIs from PDF.

Fail closed: this schema is ONLY verified for the Q1 2026 issuer document.
Extracts result-account quarter column and Note 10 HIÅ KPI column directly.
No financial feed is modified.
"""
import hashlib
import io
import json
import re
from decimal import Decimal
from import_extended_pdfs import download
from klp_ratio_reconciliation import reconcile

URL='https://www.klp.no/om-klp/finans-og-ir/rapporter-og-presentasjoner/_/attachment/inline/003381a3-7e8d-44bc-84e4-6de354b1fc79%3Aee97b842e57469c4897509abea3bee80331904b3/Kvartalsrapport%20KLP%20Skadeforsikring%20AS%20Q1%202026.pdf'
AMOUNT_LABELS={
 'insurance_revenue':'Forsikringsinntekter',
 'gross_claims_cost':'Forsikringskostnader',
 'operating_expenses':'Forsikringsrelaterte driftskostnader',
 'reinsurance_result':'Gjenforsikringsresultat',
 'insurance_service_result':'Forsikringsresultat etter gjenforsikring',
}
RATIO_LABELS={
 'gross_loss_ratio':'Skadeprosent brutto',
 'reinsurance_ratio':'Gjenforsikringsprosent',
 'loss_ratio':'Skadeprosent etter gjenforsikring',
 'expense_ratio':'Kostnadsprosent',
 'combined_ratio':'Totalskadeprosent',
}
NUM=r'-?\d[\d ]*(?:[.,]\d+)?'
def decimal(s):
    return Decimal(s.replace(' ','').replace(',','.'))
def row_value(text,label,*,percentage=False):
    lines=[line.strip() for line in text.splitlines()]
    matches=[line for line in lines if re.match(r'^(?:\d+\s+)?'+re.escape(label)+r'\s+',line,re.I)]
    if len(matches)!=1:raise ValueError('Missing or ambiguous official PDF row: '+label)
    tail=re.sub(r'^(?:\d+\s+)?'+re.escape(label)+r'\s+','',matches[0],count=1,flags=re.I)
    pattern=r'^('+NUM+r')\s*%' if percentage else r'^('+NUM+r')(?=\s|$)'
    match=re.match(pattern,tail)
    if not match:raise ValueError('Missing first quarter column for '+label)
    return decimal(match.group(1))

def prior_year_comparative(text,label):
    """Read second result-account column, Q1 2025, directly from Q1 PDF."""
    matching=[line.strip() for line in text.splitlines()
              if re.match(r'^(?:\d+\s+)?'+re.escape(label)+r'\s+',line.strip(),re.I)]
    if len(matching)!=1:
        raise ValueError('Missing or ambiguous 2025 comparative: '+label)
    tail=re.sub(r'^(?:\d+\s+)?'+re.escape(label)+r'\s+','',matching[0],count=1,flags=re.I)
    nums=re.findall(r'-?\d{1,3}(?: \d{3})*(?:,\d+)?',tail)
    if len(nums)<2:
        raise ValueError('Missing Q1 2025 comparative numeric column: '+label)
    return decimal(nums[1])

def verify_pages(texts,url=URL,sha=None):
    if len(texts)<21 or '1. kvartal 2026' not in texts[5] or 'Resultatregnskap' not in texts[5]:
        raise ValueError('Unexpected Q1 2026 result page layout')
    if 'Note 10 Nøkkeltall - akkumulert' not in texts[20]:
        raise ValueError('Missing official HIÅ Note 10')
    if not re.search(r'MILLIONER KRONER\s+1\. kvartal 2026\s+1\. kvartal 2025',texts[5]):
        raise ValueError('Unexpected result-column order')
    if not re.search(r'MILLIONER KRONER\s+1\. kvartal 2026\s+4\. kvartal 2025',texts[20]):
        raise ValueError('Unexpected HIÅ-column order')
    amounts={k:row_value(texts[5],label) for k,label in AMOUNT_LABELS.items()}
    reported={k:row_value(texts[20],label,percentage=True) for k,label in RATIO_LABELS.items()}
    revenue=amounts['insurance_revenue']
    gross=-amounts['gross_claims_cost']
    expenses=-amounts['operating_expenses']
    reins=-amounts['reinsurance_result']
    if min(revenue,gross,expenses,reins)<=0:
        raise ValueError('Unexpected financial sign convention')
    if abs(revenue-gross-expenses+amounts['reinsurance_result']-amounts['insurance_service_result'])>Decimal('0.25'):
        raise ValueError('Result table fails accounting reconciliation')
    basis={'company':'KLP Skadeforsikring','year':2026,'quarter':1,
           'scope':'company','currency':'NOK','unit':'NOK million',
           'source_url':url,'source_sha256':sha or '0'*64,
           'issuer_definition_verified':True}
    components={'insurance_revenue':float(revenue),'gross_claims_cost':float(gross),
                'reinsurance_effect':float(reins),'operating_expenses':float(expenses)}
    q={**basis,'period_type':'quarter','source_pages':[6],'ratio_components':components}
    y={**basis,'period_type':'ytd','source_pages':[21],'ratio_components':components,
       'reported_ratios':{k:float(v) for k,v in reported.items()}}
    profit_before_tax=row_value(texts[5],'Resultat før skattekostnad')
    ytd_pre_tax=row_value(texts[20],'Resultat før skatt')
    if abs(profit_before_tax-ytd_pre_tax)>Decimal('0.15'):
        raise ValueError('Q1 pre-tax profit disagrees with issuer HIÅ note')
    solvency=row_value(texts[20],'Solvenskapitaldekning',percentage=True)
    if not 0<solvency<1000:
        raise ValueError('Unexpected KLP solvency ratio')
    result=reconcile(q,y)
    result['reported_management_metrics']={'profit_before_tax':float(profit_before_tax),
        'profit_before_tax_ytd':float(ytd_pre_tax),
        'solvency_ratio':float(solvency),'source_page':21,
        'period_basis':{'profit_before_tax':'quarter','profit_before_tax_ytd':'ytd',
                        'solvency_ratio':'quarter_end'}}
    result['reported_quarter_amounts']={k:float(v) for k,v in amounts.items()}
    result['reported_ytd_amounts']={k:float(v) for k,v in amounts.items()}
    result['reported_prior_year_quarter_amounts']={k:float(prior_year_comparative(texts[5],label)) for k,label in AMOUNT_LABELS.items()}
    result['reported_prior_year_ytd_amounts']=dict(result['reported_prior_year_quarter_amounts'])
    result['reported_ytd_ratios']={k:float(v) for k,v in reported.items()}
    result['status']='q1_2026_pdf_reconciled_not_published'
    return result

def run(url=URL):
    if url!=URL:raise ValueError('Q1 schema is restricted to approved issuer report')
    raw=download(url,'KLP Skadeforsikring')
    import pdfplumber
    with pdfplumber.open(io.BytesIO(raw)) as pdf:
        texts=[page.extract_text(layout=False) or '' for page in pdf.pages]
    return verify_pages(texts,url,hashlib.sha256(raw).hexdigest())

if __name__=='__main__':
    result=run()
    print('KLP_Q1_2026_REAL_PDF_RECONCILED',json.dumps(result,ensure_ascii=False,sort_keys=True))
