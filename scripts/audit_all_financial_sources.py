#!/usr/bin/env python3
"""Audit source evidence for EVERY financial observation, without inventing data.

Comparative columns in official quarterly reports are legitimate, but a
source-document period mismatch is not proof of the referenced column.
"""
import json
from collections import Counter
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
def inspect(rows):
    problems=[]
    types=Counter()
    comparisons=Counter()
    missing_sha=Counter()
    for index,row in enumerate(rows,1):
        company=row.get('company','unknown')
        kind=row.get('source_type','missing')
        types[kind]+=1
        observed=f"Q{row.get('quarter')} {row.get('year')}"
        document=row.get('source_document_period')
        if document and document!=observed:
            comparisons[company]+=1
        if not row.get('source_sha256'):
            missing_sha[company]+=1
        if kind not in ('official_quarterly_report','official_investor_tables'):
            problems.append(f"row {index}: unsupported source type {kind}")
        if kind=='official_investor_tables':
            problems.append(f"row {index}: workbook evidence, not report/presentation PDF")
        if not str(row.get('source_url','')).startswith('https://'):
            problems.append(f"row {index}: no HTTPS source")
        if kind=='official_quarterly_report' and not isinstance(row.get('source_page'),int):
            problems.append(f"row {index}: missing report page")
    return {'observation_count':len(rows),'source_types':dict(types),
            'comparative_period_rows':sum(comparisons.values()),
            'comparative_periods_by_company':dict(comparisons),
            'missing_source_sha256':sum(missing_sha.values()),
            'missing_source_sha256_by_company':dict(missing_sha),
            'source_policy_exceptions':problems,
            'official_pdf_or_presentation_only_confirmed':not problems and not sum(missing_sha.values()),
            'note':'Historical comparison columns require separate column-level evidence; a source URL or report year alone cannot certify the reported period.'}

def main():
    rows=json.loads((ROOT/'data/financial_observations.json').read_text(encoding='utf-8'))['observations']
    report=inspect(rows)
    dest=ROOT/'data/all_financial_source_evidence.json'
    dest.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('ALL_FINANCIAL_SOURCE_EVIDENCE',json.dumps(report,ensure_ascii=False),flush=True)
if __name__=='__main__':main()
