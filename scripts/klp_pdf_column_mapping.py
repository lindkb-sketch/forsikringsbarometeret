#!/usr/bin/env python3
"""KLP explicit quarter/HIÅ table-column mapping and KPI reconciliation.

No automatic guess of PDF column positions or sign conventions is permitted.
A verified issuer report schema must supply row labels, columns and page.
"""
import re
from decimal import Decimal
from klp_quarter_from_ytd import number
from klp_ratio_reconciliation import reconcile

KEYS=('insurance_revenue','gross_claims_cost','reinsurance_effect','operating_expenses')
RATIO_KEYS=('gross_loss_ratio','reinsurance_ratio','loss_ratio','expense_ratio','combined_ratio')

def parse_cell(value):
    s=str(value or '').strip().replace('\u00a0','').replace(' ','')
    if not s or s in ('-','–','—'):raise ValueError('Missing financial table cell')
    # Norwegian decimal comma, with optional thousands grouping.
    if ',' in s:
        s=s.replace('.','').replace(',','.')
    elif re.fullmatch(r'-?\d{1,3}(?:\.\d{3})+',s):
        s=s.replace('.','')
    return number(s)

def extract(rows,schema,*,year,quarter,url,sha,scope='company'):
    """Map extracted PDF rows to explicit quarter and HIÅ columns.

    schema = {quarter_column:int, ytd_column:int, labels:{metric:exact label},
              ratio_labels:{metric:exact label}, page:int, unit:str,
              issuer_definition_verified:bool}
    All row labels must occur once, on the configured PDF page/table.
    """
    if not schema.get('issuer_definition_verified'):
        raise ValueError('Unverified issuer-specific PDF schema')
    qc,yc=schema.get('quarter_column'),schema.get('ytd_column')
    if type(qc)!=int or type(yc)!=int or qc==yc or min(qc,yc)<1:
        raise ValueError('Invalid explicit quarter/HIÅ columns')
    if set(schema.get('labels',{}))!=set(KEYS) or set(schema.get('ratio_labels',{}))!=set(RATIO_KEYS):
        raise ValueError('Incomplete issuer row label mapping')
    page=schema.get('page')
    table=schema.get('table')
    if type(page)!=int or page<1 or type(table)!=int or table<1:
        raise ValueError('Missing verified PDF page/table reference')
    quarter_values={}
    ytd_values={}
    reported={}
    for metric,label in schema['labels'].items():
        matching=[r for r in rows if r.get('page')==page and r.get('table')==table
                  and r.get('cells') and r['cells'][0].strip().casefold()==label.casefold()]
        if len(matching)!=1:raise ValueError('Missing or ambiguous KLP amount row: '+metric)
        cells=matching[0]['cells']
        if max(qc,yc)>=len(cells):raise ValueError('Missing quarter/HIÅ column')
        quarter_values[metric]=parse_cell(cells[qc])
        ytd_values[metric]=parse_cell(cells[yc])
    for metric,label in schema['ratio_labels'].items():
        matching=[r for r in rows if r.get('page')==page and r.get('table')==table
                  and r.get('cells') and r['cells'][0].strip().casefold()==label.casefold()]
        if len(matching)!=1:raise ValueError('Missing or ambiguous KLP ratio row: '+metric)
        cells=matching[0]['cells']
        if yc>=len(cells):raise ValueError('Missing HIÅ ratio column')
        reported[metric]=parse_cell(cells[yc].replace('%',''))
    basis={'company':'KLP Skadeforsikring','year':year,'quarter':quarter,
           'scope':scope,'currency':'NOK','unit':schema['unit'],
           'source_url':url,'source_sha256':sha,'source_pages':[page],
           'issuer_definition_verified':True}
    quarter_record={**basis,'period_type':'quarter','ratio_components':quarter_values}
    ytd_record={**basis,'period_type':'ytd','ratio_components':ytd_values,
                'reported_ratios':reported}
    result=reconcile(quarter_record,ytd_record)
    result['quarter_components']={k:float(v) for k,v in quarter_values.items()}
    result['ytd_components']={k:float(v) for k,v in ytd_values.items()}
    result['schema_version']=1
    return result
