"""Owner-approved KLP Q4 residual regression; actual historical PDF replay."""
import copy
import hashlib
import sys
import unittest
from datetime import date
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from klp_annual_q4 import parse_annual,parse_q3,derive,validate_derived,annual_views
from rolling_klp_reports import advance,verify_report,fetch_archive
from import_klp_production import build_snapshot
from test_klp_production_import import reconciled
from import_extended_pdfs import download,pages
from klp_q2_q3_discovery import discover
from build_nine_insurer_comparison import build
from check_extended_insurer_evidence import validate,COMPANIES

ANNUAL='https://www.klp.no/annual.pdf'
Q3='https://www.klp.no/q3.pdf'
Q1='https://www.klp.no/q1.pdf'
A_RAW=b'%PDF-synthetic-annual'
Q_RAW=b'%PDF-synthetic-q3'
A_SHA=hashlib.sha256(A_RAW).hexdigest()
Q_SHA=hashlib.sha256(Q_RAW).hexdigest()

def annual_fixture(year=2025):
    return [f'Årsregnskap {year}\nKLP Skadeforsikring AS',
        f'''Hovedtall {year}
MILLIONER KRONER {year} {year-1}
Forsikringsinntekter 3 116,7 2 758,4
Resultat før skattekostnad 334,8 385,9
Skadeprosent-brutto 86,9% 77,3%
Gjenforsikringsprosent 1,6% 6,4%
Skadeprosent etter gjenforsikring 88,6% 83,8%
Kostnadsprosent 11,9% 13,0%
Solvenskapitaldekning (%) 233% 256%''',
        f'''Resultatregnskap
KLP Skadeforsikring AS
NOTE MILLIONER KRONER {year} {year-1}
3, 7 Forsikringsinntekter 3 116,7 2 758,4
7 Forsikringskostnader -2 709,6 -2 132,5
4, 7, 8 Forsikringsrelaterte driftskostnader -370,5 -359,7
Gjenforsikringsresultat -51,2 -177,9
Forsikringsresultat etter gjenforsikring -14,6 88,5
Resultat før skattekostnad 334,8 385,9''',
        f'''Note 2 Informasjon om vesentlige regnskapsprinsipp
IFRS Accounting Standards og årsregnskapsforskriften.
Det er ingen nye eller endrede IFRS Accounting Standard eller IFRIC-fortolkninger som er trådt i kraft for {year} årsregnskapet som påvirker foretakets årsregnskap i vesentlig grad.''']

def q3_fixture(year=2025):
    return [f'3. kvartalsregnskap {year}\nKLP Skadeforsikring AS',
        f'''Resultatregnskap
KLP Skadeforsikring AS
01.01.{year}- 01.01.{year-1}- 01.01.{year-1}-
NOTE MILLIONER KRONER 3. kvartal {year} 3. kvartal {year-1} 30.09.{year} 30.09.{year-1} 31.12.{year-1}
3 Forsikringsinntekter 783,7 687,9 2 316,1 2 052,8 2 758,4
Forsikringskostnader -539,7 -514,7 -1 694,5 -1 626,3 -2 132,5
4 Forsikringsrelaterte driftskostnader -95,5 -92,4 -308,1 -278,3 -359,7
Gjenforsikringsresultat -38,1 -38,3 -135,8 -171,3 -177,9
Forsikringsresultat etter gjenforsikring 110,4 42,6 177,7 -23,2 88,5
Resultat før skattekostnad 215,9 131,8 408,5 195,5 385,9''',
        f'''Note 2 Regnskapsprinsipper og estimater
Delårsrapporten er satt opp i samsvar med IFRS Accounting Standards og årsregnskapsforskriften. IAS 34 om delårsrapportering.
Det er ikke foretatt andre endringer i regnskapsprinsippene som har hatt betydning for delårsregnskapet per 30.09.{year}.''',
        f'''Note 11 Nøkkeltall - akkumulert
MILLIONER KRONER 3. kvartal {year} 2. kvartal {year} 1. kvartal {year} 4. kvartal {year-1} 3. kvartal {year-1}
Resultat før skatt 408,5 192,6 32,3 385,9 195,5
Forsikringsinntekter 2 316,1 1 532,4 786,1 2 758,4 2 052,8
Skadeprosent brutto 73,2 % 75,4 % 74,8 % 77,3 % 79,2 %
Gjenforsikringsprosent 5,9 % 6,4 % 8,8 % 6,4 % 8,3 %
Skadeprosent etter gjenforsikring 79,0 % 81,7 % 83,6 % 83,8 % 87,6 %
Kostnadsprosent 13,3 % 13,9 % 15,1 % 13,0 % 13,6 %
Totalskadeprosent 92,3 % 95,6 % 98,7 % 96,8 % 101,1 %
Solvenskapitaldekning 261 % 242 % 246 % 256 % 238 %''']

def inputs(year=2025):
    return parse_annual(annual_fixture(year),year,ANNUAL,A_SHA),parse_q3(q3_fixture(year),year,Q3,Q_SHA)

def expected(row,test):
    m=row['metrics']
    test.assertAlmostEqual(m['insurance_revenue'],800.6,places=5)
    test.assertAlmostEqual(m['insurance_service_result'],-192.3,places=5)
    test.assertAlmostEqual(m['profit_before_tax'],-73.7,places=5)
    test.assertAlmostEqual(m['loss_ratio'],116.225331,places=5)
    test.assertAlmostEqual(m['expense_ratio'],7.794154,places=5)
    test.assertAlmostEqual(m['combined_ratio'],124.019485,places=5)
    test.assertAlmostEqual(m['insurance_revenue_growth'],13.463719,places=5)
    test.assertEqual(m['solvency_ratio'],233)
    test.assertNotIn('return_on_equity',m)
    test.assertEqual(row['metric_methods']['solvency_ratio'],'reported_quarter_end')
    test.assertEqual(row['metric_methods']['combined_ratio'],'calculated')
    test.assertEqual(row['ytd_metrics']['profit_before_tax'],334.8)
    test.assertEqual(validate_derived(row),[])

class KLPAnnualQ4Tests(unittest.TestCase):
    def test_residual_signed_reinsurance_and_negative_profit(self):
        annual,q3=inputs()
        expected(derive(annual,q3),self)

    def test_different_year_basis_restatement_and_tampering_rejected(self):
        annual,q3=inputs()
        for field,value in [('year',2026),('currency','DKK'),('basis','unknown')]:
            bad=copy.deepcopy(q3);bad['document'][field]=value
            with self.subTest(field=field), self.assertRaises(ValueError):
                derive(annual,bad)
        bad=copy.deepcopy(q3);bad['prior_full_year']['insurance_revenue']+=5
        with self.assertRaisesRegex(ValueError,'comparator changed'):derive(annual,bad)
        row=derive(annual,q3);row['metrics']['combined_ratio']=10
        self.assertTrue(validate_derived(row))
        bad=annual_fixture();bad[-1]=bad[-1].replace('ingen nye eller endrede','nye og endrede')
        with self.assertRaisesRegex(ValueError,'policy'):parse_annual(bad,2025,ANNUAL,A_SHA)

    def test_owner_approved_fallback_in_rolling_pipeline(self):
        from import_klp_production import row_from_reconciliation,snapshot_from_rows
        from test_extended_rolling_periods import klp_fixture,base_alm
        previous=build_snapshot(*[reconciled(q) for q in (1,2,3)])
        previous_q3=row_from_reconciliation(verify_report(q3_fixture(2026),2026,3,Q3,Q_SHA))
        previous=snapshot_from_rows(previous['periods'][:2]+[previous_q3])
        html=f'<h2>KLP Skadeforsikring</h2><h3>2026</h3><a href="{ANNUAL}">Årsrapport</a><h3>2027</h3><a href="{Q1}">Kvartalsrapport 1. kvartal</a>'
        raw={ANNUAL:A_RAW,Q3:Q_RAW,Q1:b'%PDF-synthetic-q1'}
        extracted={A_RAW:annual_fixture(2026),Q_RAW:q3_fixture(2026),raw[Q1]:klp_fixture(2027,1)}
        opts=dict(fetcher=lambda:html,downloader=lambda url,c:raw[url],extractor=lambda body:extracted[body])
        fourth=advance(previous,today=date(2027,2,1),**opts)
        expected(fourth['periods'][-1],self)
        self.assertEqual(validate_derived(fourth['periods'][-1],previous_q3),[])
        self.assertEqual(fourth['source_type'],'official_annual_report')
        self.assertEqual(fourth['periods'][:3],previous['periods'])
        ext={'insurers':{'KLP Skadeforsikring':fourth,'Alm. Brand':base_alm()}}
        self.assertEqual(validate(ext,{'sources':[{'company':x} for x in COMPANIES]},{x:{} for x in COMPANIES}),[])
        comp=build({'observations':[]},ext)
        k=next(x for x in comp['companies'] if x['company']=='KLP Skadeforsikring')
        self.assertEqual(k['metric_methods']['profit_before_tax'],'calculated')
        self.assertEqual(len(k['metric_sources']['profit_before_tax']['source_documents']),2)
        self.assertEqual(len(k['metric_sources']['solvency_ratio']['source_documents']),1)
        next_year=advance(fourth,today=date(2027,5,1),**opts)
        self.assertEqual((next_year['year'],next_year['quarter']),(2027,1))
        self.assertNotIn('metric_methods',next_year)
        self.assertEqual(next_year['periods'][:4],fourth['periods'])
        self.assertEqual(advance(next_year,today=date(2027,5,1),**opts),next_year)
        raw[Q3]=b'%PDF-changed'
        with self.assertRaisesRegex(ValueError,'changed'):advance(previous,today=date(2027,2,1),**opts)

    def test_actual_2025_official_annual_and_q3_pdfs(self):
        html=fetch_archive()
        found=discover(html,year=2025,periods=(3,4))
        self.assertEqual(len(found[3]),1)
        self.assertEqual(len(found[4]),1)
        a_url=found[4][0];q_url=found[3][0]
        a_raw=download(a_url,'KLP Skadeforsikring');q_raw=download(q_url,'KLP Skadeforsikring')
        a_text=pages(a_raw);q_text=pages(q_raw)
        annual=parse_annual(a_text,2025,a_url,hashlib.sha256(a_raw).hexdigest(),annual_views(a_raw,a_text))
        q3=parse_q3(q_text,2025,q_url,hashlib.sha256(q_raw).hexdigest())
        row=derive(annual,q3)
        expected(row,self)
        print('KLP_ACTUAL_2025_Q4_RESIDUAL_VERIFIED',row['metrics'],row['source_documents'],flush=True)

if __name__=='__main__':unittest.main()
