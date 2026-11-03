"""Fail-closed future Sampo segment publishing and all-seven ingestion wiring."""
import json
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from quarterly_import_contract import verify_sampo_nordic_segments
from verify_expected_published_quarters import validate

METRICS=('insurance_revenue','insurance_service_result','combined_ratio','loss_ratio','expense_ratio')
SEGMENTS=(None,'Private Nordic','Nordic Commercial')

def rows():
    result=[]
    for segment in SEGMENTS:
        scope='group' if segment is None else 'reported_segment'
        for metric in METRICS:
            value={'insurance_revenue':1100,'insurance_service_result':220,
                   'combined_ratio':80,'loss_ratio':66,'expense_ratio':14}[metric]
            result.append(dict(company='Sampo',year=2026,quarter=3,scope=scope,
                 segment=segment,period_type='quarter',metric=metric,value=value,
                 status='reported',source_url='https://www.sampo.com/report.pdf',
                 source_page=1,source_sha256='a'*64,
                 source_type='official_quarterly_report'))
    # A group revenue comparator is mandatory for real release growth.
    result.append(dict(result[0],year=2025))
    return result

class SampoNordicReleaseTests(unittest.TestCase):
    def test_both_segments_reach_feed(self):
        source=rows()
        self.assertTrue(verify_sampo_nordic_segments(source,list(source),2026,3))
        self.assertTrue(validate(source))

    def test_missing_private_nordic_blocks_source(self):
        source=[r for r in rows() if r.get('segment')!='Private Nordic']
        with self.assertRaisesRegex(ValueError,'Private Nordic'):
            verify_sampo_nordic_segments(source,list(source),2026,3)
        with self.assertRaisesRegex(ValueError,'Private Nordic'):
            validate(source)

    def test_missing_commercial_blocks_feed(self):
        source=rows()
        feed=[r for r in source if r.get('segment')!='Nordic Commercial']
        with self.assertRaisesRegex(ValueError,'Nordic Commercial'):
            verify_sampo_nordic_segments(source,feed,2026,3)

    def test_modified_published_segment_value_is_rejected(self):
        source=rows()
        feed=[dict(r) for r in source]
        next(r for r in feed if r.get('segment')=='Private Nordic')['value']+=1
        with self.assertRaisesRegex(ValueError,'provenance changed'):
            verify_sampo_nordic_segments(source,feed,2026,3)

    def test_missing_group_metric_blocks_published_quarter(self):
        source=[r for r in rows() if not (r.get('scope')=='group'
                and r.get('year')==2026 and r['metric']=='combined_ratio')]
        with self.assertRaisesRegex(ValueError,'group missing'):
            validate(source)

    def test_sampo_is_imported_on_regular_seven_issuer_schedule(self):
        pipeline=(ROOT/'scripts/run_pipeline.py').read_text()
        for module in ('import_fremtind_holding.py','import_frende_holding.py',
                       'import_gjensidige_latest.py','import_tryg.py',
                       'protector_publish.py','sampo_publish.py',
                       'storebrand_publish_q3.py'):
            self.assertIn(module,pipeline)
        workflow=(ROOT/'.github/workflows/update.yml').read_text()
        self.assertIn('schedule:',workflow)
        self.assertIn('python scripts/quarterly_import_contract.py',workflow)
        self.assertIn('python scripts/verify_expected_published_quarters.py',pipeline)
        self.assertLess(workflow.index('python scripts/quarterly_import_contract.py'),
                        workflow.index('actions/deploy-pages@v4'))

if __name__=='__main__':
    unittest.main()
