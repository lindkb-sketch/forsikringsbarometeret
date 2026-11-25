"""Regression and real-source replay for separate nine-insurer HIÅ coverage."""
import copy
import hashlib
import json
import sys
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from import_group_ytd import collect,protector,sampo,returns,ytd_header
from import_extended_ytd import make_klp,validate_baseline
from import_alm_brand_supplemental import attach
from import_extended_pdfs import download,pages
from rolling_klp_reports import verify_report
from alm_brand_live_pdf import run as alm_pdf
from build_nine_insurer_comparison import build
from quarterly_kpi_completeness import build as coverage
from nine_insurer_ytd import group_values
from audit_financials import audit

SHA='a'*64
URL='https://issuer.example/report.pdf'
def row(c,key,value,year=2026,q=3,period='ytd',unit='percent',definition='issuer report'):
    return dict(company=c,metric=key,value=value,year=year,quarter=q,period_type=period,
                scope='group',source_scope='group',status='reported',source_url=URL,
                source_type='official_quarterly_report',source_sha256=SHA,source_page=5,
                unit=unit,source_definition=definition)

class YTDContracts(unittest.TestCase):
    def test_growth_uses_same_cumulative_period_and_solvency_is_point_in_time(self):
        rows=[row('Fremtind','insurance_revenue',300,unit='NOKm'),
              row('Fremtind','insurance_revenue',250,year=2025,unit='NOKm'),
              row('Fremtind','insurance_revenue',100,period='quarter',unit='NOKm'),
              row('Fremtind','insurance_revenue',50,year=2025,period='quarter',unit='NOKm'),
              row('Fremtind','solvency_ratio',200,period='quarter'),
              row('Fremtind','return_on_equity',35,period='quarter')]
        v,e=group_values(rows,'Fremtind',(2026,3))
        self.assertAlmostEqual(v['insurance_revenue_growth'],20)
        self.assertEqual(v['solvency_ratio'],200)
        self.assertEqual(e['solvency_ratio']['method'],'reported_quarter_end')
        self.assertNotIn('return_on_equity',v)
        self.assertEqual(len(e['insurance_revenue_growth']['source_documents']),2)
        rows[1]['unit']='EURm'
        self.assertNotIn('insurance_revenue_growth',group_values(rows,'Fremtind',(2026,3))[0])

    def test_future_year_does_not_reuse_ytd_and_q1_is_identical(self):
        rows=[row('Tryg','profit_before_tax',100,year=2026,q=4),
              row('Tryg','profit_before_tax',25,year=2027,q=1,period='quarter')]
        v,e=group_values(rows,'Tryg',(2027,1))
        self.assertEqual(v['profit_before_tax'],25)
        self.assertEqual(e['profit_before_tax']['method'],'q1_equals_ytd')
        self.assertEqual(group_values(rows,'Tryg',(2027,2)),({},{}))

    def test_explicit_period_header_and_wrong_year(self):
        self.assertEqual(ytd_header(['NOKm Q3 2026 Q3 2025 Q1-Q3 2026 Q1-Q3 2025 FY 2025'],2026,3),(5,0,2,3))
        self.assertEqual(ytd_header(['Q3 Q3 Q1-Q3 Q1-Q3 FY','2027 2026 2027 2026 2026'],2027,3),(5,0,2,3))
        self.assertIsNone(ytd_header(['Q3 2026 Q3 2025 Q1-Q3 2025 Q1-Q3 2026 FY 2025'],2026,3))
        self.assertIsNone(ytd_header(['Q3 2026 Q3 2025 FY 2025'],2026,3))

    def test_gjensidige_explicit_ytd_not_ordinary_roe(self):
        a=row('Gjensidige','insurance_revenue',100,period='quarter',unit='MNOK')
        parsed=returns([(6,'The annualised return on equity for the year-to-date was 34.2 per cent (29.6).')],a,{'return_on_equity':34.2})
        self.assertEqual(parsed[0]['period_type'],'ytd')
        self.assertEqual(parsed[0]['value'],34.2)
        with self.assertRaises(ValueError):returns([(6,'The annualised return on equity was 34.2 per cent.')],a,{})

    def test_live_q3_2026_all_nine_ytd_source_replay(self):
        # Replay original documents, even after future imports: no fixture
        # values are written to the repository or admitted to production.
        data=json.loads((ROOT/'data/financial_observations.json').read_text(encoding='utf-8'))
        rows=[r for r in data['observations'] if (r['year'],r['quarter'])<=(2026,3)]
        # Force each new issuer parser to read the original report even after
        # the baseline has been published.
        targets={'Sampo','Protector','Fremtind','Tryg','Gjensidige'}
        retained=[r for r in rows if not (r.get('scope')=='group' and r.get('company') in targets and
            (r['year'],r['quarter'],r['period_type'])==(2026,3,'ytd') and
            ((r['company'] in ('Sampo','Protector') and r['metric'] in ('insurance_revenue','insurance_service_result','combined_ratio','loss_ratio','expense_ratio')) or
             (r['company']!='Sampo' and r['metric']=='return_on_equity')))]
        additions,errors=collect(retained)
        self.assertFalse(errors,repr(errors))
        key=lambda r:(r['company'],r['year'],r['quarter'],r['scope'],r['period_type'],r['metric'],r.get('segment'))
        index={key(r):r for r in retained}
        for r in additions:
            if key(r) not in index:index[key(r)]=r
            else:self.assertAlmostEqual(index[key(r)]['value'],r['value'],places=1)
        merged=list(index.values())
        self.assertTrue(audit({**data,'observations':merged})['ok'])
        ext=json.loads((ROOT/'data/extended_insurer_financials.json').read_text(encoding='utf-8'))
        klp=ext['insurers']['KLP Skadeforsikring']
        if (klp['year'],klp['quarter'])!=(2026,3):
            from import_klp_production import snapshot_from_rows
            klp=snapshot_from_rows([p for p in klp['periods'] if (p['year'],p['quarter'])<=(2026,3)])
        else:klp=copy.deepcopy(klp)
        raw=download(klp['source_url'],'KLP Skadeforsikring')
        digest=hashlib.sha256(raw).hexdigest()
        self.assertEqual(digest,klp['source_sha256'])
        klp['ytd_pdf_evidence']=make_klp(klp,verify_report(pages(raw),2026,3,klp['source_url'],digest))
        self.assertEqual(validate_baseline(klp),[])
        alm=ext['insurers']['Alm. Brand']
        if (alm['year'],alm['quarter'])!=(2026,3):alm=alm['periods'][0]
        alm=attach(alm,alm_pdf())
        self.assertEqual(validate_baseline(alm),[])
        comp=build({'observations':merged},{'insurers':{'KLP Skadeforsikring':klp,'Alm. Brand':alm}})
        kpis=coverage(comp)['ytd']
        print('NINE_LIVE_YTD_COVERAGE',kpis['present_metric_count'],kpis['expected_metric_count'],
              [(x['company'],x['missing_metrics']) for x in kpis['companies'] if x['missing_metrics']],flush=True)
        self.assertEqual((kpis['present_metric_count'],kpis['expected_metric_count']),(78,78))
        self.assertTrue(kpis['all_nine_same_period'])
        for item in comp['companies']:
            print('NINE_LIVE_YTD_VALUES',item['company'],item['ytd_metrics'],flush=True)
        prot=next(x for x in comp['companies'] if x['company']=='Protector')
        self.assertEqual(prot['ytd_metrics']['return_on_equity'],33.8)
        self.assertEqual(prot['ytd_metrics']['insurance_revenue'],11258)
        sam=next(x for x in comp['companies'] if x['company']=='Sampo')
        self.assertEqual(sam['ytd_metrics']['insurance_revenue'],7303)
        self.assertEqual(sam['ytd_metrics']['insurance_service_result'],1221)

if __name__=='__main__':unittest.main()
