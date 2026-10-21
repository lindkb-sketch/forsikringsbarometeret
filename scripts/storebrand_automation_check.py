#!/usr/bin/env python3
"""Isolated Storebrand Q3 2026 end-to-end test. Does not alter production data.

Without --group/--norway, discovers both issuer PDFs and downloads them.
The Q3 2026 parser is deliberately strict; later quarters require an update.
"""
import argparse
import hashlib
import json
import shutil
import sys
import tempfile
import urllib.parse
import urllib.request
from pathlib import Path

from audit_financials import ROOT
from import_storebrand_reports import parse_group, parse_norway, integrate
from storebrand_sources import discover, official


def download_pdf(url, destination):
    parsed = urllib.parse.urlparse(url)
    if not official(url):
        raise ValueError('Not an approved Storebrand HTTPS PDF host')
    if not parsed.path.lower().endswith('.pdf'):
        raise ValueError('Not a direct PDF URL')
    req = urllib.request.Request(url, headers={'User-Agent': 'Forsikringsbarometeret/1.0'})
    with urllib.request.urlopen(req, timeout=40) as response:
        final = urllib.parse.urlparse(response.geturl())
        if not official(response.geturl()):
            raise ValueError('PDF redirected to an unapproved host')
        blob = response.read(35_000_001)
    if not blob.startswith(b'%PDF-') or len(blob) > 35_000_000:
        raise ValueError('Invalid or oversized Storebrand PDF')
    destination.write_bytes(blob)
    return hashlib.sha256(blob).hexdigest()


def choose_reports(records, year=2026, quarter=3):
    selected = {}
    for item in records:
        if item.get('year') != year or item.get('quarter') != quarter:
            continue
        scope = item.get('scope')
        if scope not in ('group', 'norway'):
            continue
        if scope in selected and selected[scope]['document_url'] != item['document_url']:
            raise ValueError('Ambiguous Storebrand report: '+scope)
        selected[scope] = item
    if set(selected) != {'group', 'norway'}:
        raise ValueError('Both official Storebrand Q3 2026 reports must be discovered')
    return selected


def test_pipeline(group=None, norway=None, group_url=None, norway_url=None, output=None, discoverer=discover, downloader=download_pdf):
    with tempfile.TemporaryDirectory(prefix='storebrand-isolated-') as temp:
        work = Path(temp)
        if group is None or norway is None:
            if group is not None or norway is not None:
                raise ValueError('Supply both local PDFs or neither')
            selected = choose_reports(discoverer()['reports'])
            group = work/'group.pdf'; norway = work/'norway.pdf'
            group_url = selected['group']['document_url']
            norway_url = selected['norway']['document_url']
            downloader(group_url, group)
            downloader(norway_url, norway)
        else:
            group_url = group_url or 'https://www.storebrand.no/en/investor-relations/quarterly-reporting/storebrand-asa/2026'
            norway_url = norway_url or 'https://www.storebrand.no/en/investor-relations/quarterly-reporting/storebrand-forsikring-as'
        target = work/'observations.json'
        shutil.copyfile(ROOT/'data/financial_observations.json', target)
        incoming = parse_group(group, group_url) + parse_norway(norway, norway_url)
        baseline = json.loads(target.read_text())
        merged, added, updated = integrate(baseline, incoming)
        repeated, second_added, second_updated = integrate(merged, incoming)
        first = {'parsed':len(incoming),'added':added,'updated_provenance':updated}
        second = {'added':second_added,'updated_provenance':second_updated}
        if second_added != 0:
            raise AssertionError('Repeat import created duplicate observations')
        rows = repeated['observations']
        storebrand = [r for r in rows if r['company'] == 'Storebrand']
        def value(scope, metric, period='quarter'):
            matches = [r['value'] for r in storebrand if r['year']==2026 and r['quarter']==3 and r['scope']==scope and r['period_type']==period and r['metric']==metric]
            if len(matches) != 1: raise AssertionError('Missing or duplicate metric: '+str((scope,metric,period)))
            return matches[0]
        if abs(value('norway','combined_ratio')-79.791)>0.005 or value('norway','loss_ratio')!=60 or value('group','combined_ratio')!=87:
            raise AssertionError('Q3 reference values did not reconcile')
        if any(r['scope']=='norway' and r['metric']=='expense_ratio' for r in storebrand):
            raise AssertionError('Norway expense ratio must remain blank')
        report = {'status':'passed', 'scope':'Storebrand Q3 2026 isolated test only', 'first_import':first, 'repeat_import':second, 'norway_q3_combined_ratio':value('norway','combined_ratio'), 'group_q3_combined_ratio':value('group','combined_ratio'), 'source_urls':{'group':group_url,'norway':norway_url}, 'production_data_modified':False}
        if output:
            output = Path(output); output.parent.mkdir(parents=True,exist_ok=True)
            output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
        return report


if __name__ == '__main__':
    ap=argparse.ArgumentParser()
    ap.add_argument('--group',type=Path); ap.add_argument('--norway',type=Path)
    ap.add_argument('--output',type=Path,default=ROOT/'data/storebrand_automation_test.json')
    args=ap.parse_args()
    try:
        print(json.dumps(test_pipeline(args.group,args.norway,output=args.output),ensure_ascii=False,indent=2))
    except Exception as exc:
        print('Storebrand isolated test FAILED: '+str(exc),file=sys.stderr)
        sys.exit(1)
