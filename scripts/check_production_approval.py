#!/usr/bin/env python3
"""Milestone 6 investor/production release approval: evidence-driven and fail closed.

Ordinary dashboard publication can continue; this is a separate explicit approval.
Never confuse successful GitHub Pages deployment with investor-ready certification.
"""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SEVEN=('Fremtind','Gjensidige','Tryg','Sampo','Frende','Protector','Storebrand')
NINE=SEVEN+('KLP Skadeforsikring','Alm. Brand')

def evaluate(readiness,comparison,gaps,dual_documents):
    blockers=[]
    if readiness.get('investor_ready') is not True or readiness.get('status')!='APPROVED_FOR_INVESTOR_USE':
        blockers.append('investor_readiness_not_approved')
    for key in ('financial_quarter_complete','all_seven_automated',
                'definitions_comparable','market_data_fresh'):
        if readiness.get(key) is not True:
            blockers.append('readiness_'+key+'_not_certified')
    seven=readiness.get('companies',[])
    if {c.get('company') for c in seven}!=set(SEVEN):
        blockers.append('seven_company_readiness_incomplete')
    for c in seven:
        if c.get('end_to_end_automation_certified') is not True:
            blockers.append('automation_not_certified:'+str(c.get('company')))
    if (comparison.get('count')!=9 or
        {c.get('company') for c in comparison.get('companies',[])}!=set(NINE)):
        blockers.append('nine_company_comparison_incomplete')
    if comparison.get('investor_use_approved') is not True:
        blockers.append('nine_company_comparison_not_approved')
    if gaps.get('all_seven_dual_document_verified') is not True:
        blockers.append('seven_insurer_dual_document_not_verified')
    if {c.get('company') for c in gaps.get('companies',[])}!=set(SEVEN):
        blockers.append('seven_insurer_document_inventory_incomplete')
    for c in gaps.get('companies',[]):
        if c.get('both_documents_checked_for_this_period') is not True:
            blockers.append('dual_document_period_not_checked:'+str(c.get('company')))
    if not isinstance(dual_documents,dict):
        blockers.append('nine_insurer_document_verification_evidence_missing')
    else:
        if {c.get('company') for c in dual_documents.get('companies',[])}!=set(NINE):
            blockers.append('nine_insurer_document_verification_incomplete')
        for c in dual_documents.get('companies',[]):
            if c.get('both_documents_verified') is not True:
                blockers.append('both_document_bytes_not_verified:'+str(c.get('company')))
            if c.get('metric_extraction_status')!='verified_and_reconciled':
                blockers.append('both_document_metrics_not_reconciled:'+str(c.get('company')))
    return {'schema_version':1,'milestone':6,'status':'APPROVED' if not blockers else 'BLOCKED',
            'approved':not blockers,'blockers':sorted(set(blockers))}

def main():
    def read(path):
        return json.loads((ROOT/path).read_text(encoding='utf-8'))
    dual=ROOT/'data/dual_document_verification.json'
    result=evaluate(read('data/investor_readiness.json'),
                    read('data/nine_insurer_comparison.json'),
                    read('data/seven_insurer_source_gap_audit.json'),
                    json.loads(dual.read_text()) if dual.is_file() else None)
    print(json.dumps(result,ensure_ascii=False,indent=2))
    # A BLOCKED approval is the correct successful result of an audit.
    # --require-approved is the release gate and exits nonzero when blocked.
    import sys
    if '--require-approved' in sys.argv and not result['approved']:
        raise SystemExit(1)

if __name__=='__main__':main()
