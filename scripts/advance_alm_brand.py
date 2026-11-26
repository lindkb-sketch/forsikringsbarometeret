#!/usr/bin/env python3
"""Promote the existing Q3 PDF evidence, then advance from verified reports."""
import argparse
import hashlib
import json
import math
from pathlib import Path
from publish_geographic_workbooks import atomic_write
from rolling_alm_brand_reports import advance,validate_rolling,verify_report,read_report
from alm_brand_live_pdf import download_report,OFFICIAL_FILING_PDF,OFFICIAL_NASDAQ_NOTICE

DATA=Path(__file__).resolve().parents[1]/'data/extended_insurer_financials.json'

def promote(original,*,downloader=download_report,reader=read_report):
    if original.get('status')=='verified_official_pdf_reconciled':
        errors=validate_rolling(original)
        if errors:raise ValueError('; '.join(errors))
        return original
    if (original.get('year'),original.get('quarter'))!=(2026,3):
        raise ValueError('Unexpected legacy Alm. Brand period')
    prior=original.get('ytd_pdf_evidence') or original.get('supplemental_pdf_evidence') or {}
    url=prior.get('source_url') or OFFICIAL_FILING_PDF
    raw=downloader(url);digest=hashlib.sha256(raw).hexdigest()
    if prior.get('source_sha256') and prior['source_sha256']!=digest:
        raise ValueError('Previously verified Alm. Brand report fingerprint changed')
    texts,regions=reader(raw)
    new=verify_report(texts,url,raw,2026,3,regions)
    # Preserve the public Q3 precision of 1 decimal, from the actual report
    # current and comparative insurance revenues (not from the announcement).
    new['metrics']['insurance_revenue_growth']=round(new['metrics']['insurance_revenue_growth'],1)
    new['growth_evidence']['quarter_rounding_decimals']=1
    for metric,value in original.get('metrics',{}).items():
        if metric not in new['metrics'] or not math.isclose(value,new['metrics'][metric],abs_tol=1e-6,rel_tol=0):
            raise ValueError('Original Alm. Brand report differs from published Q3 metric: '+metric)
    if original.get('ytd_pdf_evidence'):
        for metric,value in original['ytd_pdf_evidence']['metrics'].items():
            if not math.isclose(value,new['ytd_metrics'][metric],abs_tol=1e-6,rel_tol=0):
                raise ValueError('Original Alm. Brand report differs from published HIÅ metric: '+metric)
    new['source_discovery']={'origin':OFFICIAL_NASDAQ_NOTICE if url==OFFICIAL_FILING_PDF else original.get('report_archive',new['issuer_page_url']),
                             'origin_kind':'previously_verified_official_report'}
    new['report_archive']=original.get('report_archive',new['issuer_page_url'])
    if original.get('presentation_evidence'):
        new['presentation_evidence']=original['presentation_evidence']
        new['presentation_check']='verified'
    else:new['presentation_check']='not_available'
    errors=validate_rolling(new)
    if errors:raise ValueError('; '.join(errors))
    return new

def run(path=DATA,*,baseline_only=False):
    data=json.loads(path.read_text(encoding='utf-8'))
    original=data['insurers']['Alm. Brand']
    primary=promote(original)
    updated=primary if baseline_only else advance(primary)
    errors=validate_rolling(updated)
    if errors:raise ValueError('; '.join(errors))
    if updated==original:return False
    data['insurers']['Alm. Brand']=updated
    atomic_write(path,data)
    print('ALM_BRAND_PRIMARY_REPORT_IMPORT',updated['year'],updated['quarter'],updated['source_sha256'],flush=True)
    return True

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--baseline-only',action='store_true')
    run(baseline_only=parser.parse_args().baseline_only)
