#!/usr/bin/env python3
"""Admit only Alm. Brand group ROE and pre-tax profit from the original PDF.

Preserve the independent presentation solvency evidence and announcement
snapshot. The supplemental metrics have separate page-level PDF provenance.
"""
import json
import math
from pathlib import Path
from alm_brand_live_pdf import run as reconcile_pdf, trusted_pdf_link
from publish_geographic_workbooks import atomic_write

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'data/extended_insurer_financials.json'
KEYS=('return_on_equity','profit_before_tax')

def validate_supplemental(row):
    evidence=row.get('supplemental_pdf_evidence',{})
    metrics=row.get('metrics',{})
    present=set(KEYS)&set(metrics)
    if not present and not evidence and row.get('status')!='verified_official_pdf_reconciled':return []
    if present!=set(KEYS):return ['Alm. Brand incomplete supplemental PDF metrics']
    errors=[]
    digest=evidence.get('source_sha256','')
    if (evidence.get('source_type')!='official_quarterly_report'
        or not trusted_pdf_link(evidence.get('source_url',''))
        or not isinstance(digest,str) or len(digest)!=64
        or any(c not in '0123456789abcdef' for c in digest)
        or (evidence.get('year'),evidence.get('quarter'))!=(row.get('year'),row.get('quarter'))
        or evidence.get('scope')!='group' or evidence.get('currency')!='DKK'):
        errors.append('Alm. Brand supplemental PDF provenance invalid')
    primary=row.get('status')=='verified_official_pdf_reconciled'
    if primary and (evidence.get('source_url')!=row.get('source_url') or digest!=row.get('source_sha256')):
        errors.append('Alm. Brand management metrics must reference the primary report')
    for key in KEYS:
        metric=evidence.get('metrics',{}).get(key,{})
        if primary and (metric.get('source_page')!=row.get('source_pages',{}).get(key) or metric.get('ytd_value')!=row.get('ytd_metrics',{}).get(key)):
            errors.append('Alm. Brand primary report quarter/HIÅ evidence mismatch: '+key)
        if (type(metric.get('quarter_value')) not in (int,float)
            or type(metric.get('ytd_value')) not in (int,float)
            or not math.isfinite(metric['quarter_value']) or not math.isfinite(metric['ytd_value'])
            or metric['quarter_value']!=metrics[key]
            or type(metric.get('source_page')) is not int or metric['source_page']<1
            or not metric.get('definition')):
            errors.append('Alm. Brand supplemental PDF metric invalid: '+key)
    return errors

def attach(existing,pdf):
    if existing.get('company')!='Alm. Brand' or existing.get('scope')!='group' or existing.get('currency')!='DKK':
        raise ValueError('Alm. Brand group scope mismatch')
    if (existing.get('year'),existing.get('quarter'))!=(pdf.get('year'),pdf.get('quarter')):
        raise ValueError('Alm. Brand PDF and existing report period differ')
    if pdf.get('status')!='verified_official_pdf_reconciled':
        raise ValueError('Alm. Brand report did not pass PDF reconciliation')
    if existing.get('status')=='verified_official_pdf_reconciled':
        from rolling_alm_brand_reports import validate_rolling
        if validate_rolling(existing) or existing.get('source_sha256')!=pdf.get('source_sha256') or existing['metrics']!=pdf['metrics'] or existing.get('ytd_metrics')!=pdf.get('ytd_metrics'):
            raise ValueError('Report-first snapshot does not match independent baseline PDF replay')
        return existing
    for k,v in existing['metrics'].items():
        if k in KEYS:continue
        if k not in pdf['metrics'] or abs(v-pdf['metrics'][k])>0.001:
            raise ValueError('Alm. Brand independent sources disagree on '+k)
    evidence=dict(source_url=pdf['source_url'],source_sha256=pdf['source_sha256'],
        source_type='official_quarterly_report',year=pdf['year'],quarter=pdf['quarter'],
        scope='group',currency='DKK',metrics={
            'return_on_equity':dict(quarter_value=pdf['metrics']['return_on_equity'],
                ytd_value=pdf['return_on_equity_ytd'],source_page=pdf['source_pages']['return_on_equity'],
                definition=pdf['return_on_equity_definition']),
            'profit_before_tax':dict(quarter_value=pdf['metrics']['profit_before_tax'],
                ytd_value=pdf['profit_before_tax_ytd'],source_page=pdf['source_pages']['profit_before_tax'],
                definition='Group profit/loss before tax, continuing operations; DKK million')})
    result={**existing,'metrics':{**existing['metrics'],**{k:pdf['metrics'][k] for k in KEYS}},
        'supplemental_pdf_evidence':evidence}
    if 'ytd_metrics' in pdf:
        from import_extended_ytd import make_alm,validate_baseline
        result['ytd_pdf_evidence']=make_alm(result,pdf)
        errors=validate_baseline(result)
        if errors:raise ValueError('; '.join(errors))
    errors=validate_supplemental(result)
    if errors:raise ValueError('; '.join(errors))
    return result

def preserve(new,previous):
    """Retain same-period verified supplemental observations on refresh."""
    if previous.get('status')=='verified_official_pdf_reconciled' and (new.get('year'),new.get('quarter'))==(previous.get('year'),previous.get('quarter')):
        from rolling_alm_brand_reports import validate_rolling
        errors=validate_rolling(previous)
        if errors:raise ValueError('; '.join(errors))
        return previous
    if not previous.get('supplemental_pdf_evidence'):return new
    if (new.get('year'),new.get('quarter'))!=(previous.get('year'),previous.get('quarter')):
        return new
    result={**new,'metrics':{**new['metrics'],**{k:previous['metrics'][k] for k in KEYS}},
            'supplemental_pdf_evidence':previous['supplemental_pdf_evidence']}
    if previous.get('ytd_pdf_evidence'):
        from import_extended_ytd import validate_baseline
        result['ytd_pdf_evidence']=previous['ytd_pdf_evidence']
        errors=validate_baseline(result)
        if errors:raise ValueError('; '.join(errors))
    errors=validate_supplemental(result)
    if errors:raise ValueError('; '.join(errors))
    return result

def run(path=DATA,pdf=None):
    data=json.loads(path.read_text(encoding='utf-8'))
    existing=data['insurers']['Alm. Brand']
    if existing.get('status')=='verified_official_pdf_reconciled' or (existing.get('year',0),existing.get('quarter',0))>(2026,3):
        print('ALM_LEGACY_SUPPLEMENTAL_SKIPPED rolling snapshot retained',flush=True)
        return existing
    new=attach(existing,pdf if pdf is not None else reconcile_pdf())
    if new!=existing:
        data['insurers']['Alm. Brand']=new
        atomic_write(path,data)
    print('ALM_BRAND_SUPPLEMENTAL_PDF_VERIFIED',json.dumps(new['supplemental_pdf_evidence'],ensure_ascii=False),flush=True)
    return new

if __name__=='__main__':run()
