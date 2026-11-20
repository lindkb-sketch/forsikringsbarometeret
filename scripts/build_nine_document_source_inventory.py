#!/usr/bin/env python3
"""Milestone 4: combine existing imported provenance and real PDF discovery.

Only actual PDF byte verification is promoted to verified_document_bytes.
Existing imported SHA256 metadata alone is not proof of a fresh download.
No KPI is declared absent without checking both issuer documents.
"""
import json
from pathlib import Path
from urllib.parse import urlsplit
from verify_nine_document_bytes import COMPANIES, approved

ROOT=Path(__file__).resolve().parents[1]
OUTPUT=ROOT/'data/nine_document_source_inventory.json'
TYPES={'official_quarterly_report':'quarterly_report',
       'official_results_presentation':'results_presentation'}

def inventory(feed,extended,candidates,year=2026,quarter=3):
    rows=feed.get('observations',[])
    ext=extended.get('insurers',{})
    links=candidates.get('candidates',[])
    result={'schema_version':1,'year':year,'quarter':quarter,
            'status':'diagnostic_not_investor_approved','companies':[]}
    for company in COMPANIES:
        observations=[x for x in rows if x.get('company')==company and
            (x.get('year'),x.get('quarter'))==(year,quarter) and
            x.get('scope')=='group' and x.get('period_type')=='quarter']
        known={}
        for x in observations:
            url=x.get('source_url','')
            kind=TYPES.get(x.get('source_type'))
            if not kind or not url.startswith('https://'):continue
            key=(kind,url)
            if key not in known:
                known[key]={'document_type':kind,'url':url,'origin':'existing_imported_provenance',
                            'download_verified_now':False,'metrics':[]}
            known[key]['metrics'].append(x.get('metric'))
        source=ext.get(company,{})
        if source.get('year')==year and source.get('quarter')==quarter:
            kind=TYPES.get(source.get('source_type'))
            url=source.get('source_url','')
            if kind and url.startswith('https://'):
                known.setdefault((kind,url),{'document_type':kind,'url':url,
                    'origin':'existing_extended_provenance','download_verified_now':False,
                    'metrics':list(source.get('metrics',{}))})
            presentation=source.get('presentation_evidence',{})
            url=presentation.get('source_url','')
            if (presentation.get('source_type')=='official_results_presentation'
                and url.startswith('https://')):
                known.setdefault(('results_presentation',url),{
                    'document_type':'results_presentation','url':url,
                    'origin':'existing_extended_presentation_evidence',
                    'download_verified_now':False,'metrics':list(presentation.get('metrics',{}))})
        for candidate in links:
            if candidate.get('company')!=company:continue
            kind=candidate.get('document_type')
            url=candidate.get('document_url','')
            if kind not in ('quarterly_report','results_presentation'):continue
            # Discovery candidates remain unverified and may concern other periods.
            if not approved(company,url):continue
            known.setdefault((kind,url),{'document_type':kind,'url':url,
                'origin':'unverified_discovery_candidate_any_period',
                'download_verified_now':False,'metrics':[]})
        documents=list(known.values())
        for doc in documents:
            doc['approved_pdf_url']=approved(company,doc['url'])
            doc['is_pdf']=urlsplit(doc['url']).path.lower().endswith('.pdf')
            doc['metrics']=sorted(set(x for x in doc['metrics'] if x))
        types={x['document_type'] for x in documents
               if x['origin']!='unverified_discovery_candidate_any_period'}
        result['companies'].append({'company':company,'documents':documents,
            'report_provenance_present':'quarterly_report' in types,
            'presentation_provenance_present':'results_presentation' in types,
            'both_document_bytes_verified':False,
            'metric_reconciliation_status':'not_certified',
            'source_gap':'no_verified_presentation' if 'results_presentation' not in types
                         else 'cross_document_metric_reconciliation_not_certified'})
    result['all_nine_dual_document_verified']=False
    return result

def main():
    def load(p):return json.loads((ROOT/p).read_text(encoding='utf-8'))
    result=inventory(load('data/verified_financial_feed.json'),
                     load('data/extended_insurer_financials.json'),
                     load('data/report_candidates.json'))
    OUTPUT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('NINE_SOURCE_INVENTORY',json.dumps({
        c['company']:{'report':c['report_provenance_present'],
                      'presentation':c['presentation_provenance_present'],
                      'documents':len(c['documents'])}
        for c in result['companies']},ensure_ascii=False))
if __name__=='__main__':main()
