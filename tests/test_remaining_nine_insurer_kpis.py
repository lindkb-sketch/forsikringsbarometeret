"""Actual issuer report smoke tests plus conservative quarter/HIÅ mapping."""
import json
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from import_reported_profit_before_tax import parse_pdf, parse_frende, ingest, choose_anchors, COMPANIES
from import_alm_brand_supplemental import attach, validate_supplemental, preserve
from alm_brand_live_pdf import run as live_alm
ROOT=Path(__file__).resolve().parents[1]
SHA='a'*64

def anchor(company='Protector',year=2026,q=3):
    return dict(company=company,year=year,quarter=q,source_page=5,source_sha256=SHA,
                source_url='https://issuer.test/report.pdf')

def pages(year=2026,q=3):
    return [(5,f"""Income overview
NOKm Q{q} {year} Q{q} {year-1} Q1-Q{q} {year} Q1-Q{q} {year-1} FY {year-1}
Insurance revenue 3,864 3,529 11,258 10,197 13,756
Insurance service result 670 598 1,912 1,571 2,106
Profit/(loss) before tax 1,120 640 2,402 2,541 3,438
Tax (267) (173) (629) (600) (791)
Profit/(loss) 853 468 1,773 1,941 2,646""")]

class PreTaxTests(unittest.TestCase):
    def test_protector_periods_and_source(self):
        rows=parse_pdf(pages(),anchor(),SHA)
        self.assertEqual([(r['period_type'],r['value']) for r in rows],[('quarter',1120),('ytd',2402)])
        self.assertTrue(all(r['source_sha256']==SHA and r['source_page']==5 for r in rows))
    def test_future_period_and_wrong_period(self):
        self.assertEqual(len(parse_pdf(pages(2027,2),anchor(year=2027,q=2),SHA)),2)
        with self.assertRaises(ValueError):parse_pdf(pages(),anchor(year=2027,q=2),SHA)
    def test_wrong_hash_and_net_income_rejected(self):
        with self.assertRaises(ValueError):parse_pdf(pages(),anchor(),'b'*64)
        with self.assertRaises(ValueError):
            parse_pdf([(5,pages()[0][1].replace('Profit/(loss) before tax','Operating profit'))],anchor(),SHA)
    def test_actual_layout_labels_and_neighbouring_rows(self):
        cases=[
            ('Fremtind','Resultatutvikling og nøkkeltall\nInntekter fra forsikringstjenester',
             'Resultat før skatt 1 810 1 621 4 933 3 845 5 335 segment (%)',1810,4933),
            ('Gjensidige','Insurance revenue from general insurance\nInsurance service result general insurance\nNOK millions',
             'Profit or loss before tax expense Pension -3.3 -414.5 -92.6 -136.2 50.7\nProfit or loss before tax expense 2,780.6 2,067.4 7,625.0 6,741.5 8,495.3',2780.6,7625),
            ('Tryg','Income overview\nInsurance revenue\nInsurance service result',
             'Profit/loss before taxa) 2,123 1,980 4,476 5,505 7,212',2123,4476),
            ('Storebrand','Storebrand Group\nIncome statement\nNOK million\nNet insurance service result\nTax expenses',
             'Profit before income tax 1,001 990 3,009 2,990 4,000',1001,3009),
        ]
        for company,heading,line,q,ytd in cases:
            with self.subTest(company=company):
                p=[(5,heading+'\nQ3 2026 Q3 2025 01.01 - 30.09 2026 2025 FY 2025\n'+line)]
                result=parse_pdf(p,anchor(company),SHA)
                self.assertEqual([r['value'] for r in result],[q,ytd])

    def test_frende_group_thousand_conversion(self):
        a=anchor('Frende')
        a['source_url']='https://frende.wrep.it/q3-2026-frende-holding-as/sec/7'
        html='<h1>Nøkkeltall konsern</h1><table><tr><th>Tall i 1000</th><th>Q3 2026</th><th>Q3 2025</th><th>Pr Q3 2026</th></tr><tr><td>Resultat før skatt</td><td>125 000</td><td>100 000</td><td>420 000</td></tr></table>'
        result=parse_frende(html,a)
        self.assertEqual([r['value'] for r in result],[125,420])
        self.assertTrue(all(r['source_url'].endswith('/sec/6') and r['source_page']==6 for r in result))
    def test_latest_actual_issuer_reports(self):
        data=json.loads((ROOT/'data/financial_observations.json').read_text(encoding='utf-8'))
        anchors=choose_anchors(data['observations'])
        for company in COMPANIES:
            with self.subTest(company=company):
                a=max((r for r in anchors if r['company']==company),key=lambda r:(r['year'],r['quarter']))
                result=ingest(a)
                self.assertEqual({r['period_type'] for r in result},{'quarter','ytd'})
                self.assertTrue(all(r['scope']=='group' and r['metric']=='profit_before_tax' and r['source_page']>0 and len(r['source_sha256'])==64 for r in result))
                print('PRETAX_LIVE_VERIFIED',company,a['year'],a['quarter'],[(r['period_type'],r['value'],r['source_page']) for r in result],flush=True)
                if company=='Protector' and (a['year'],a['quarter'])==(2026,3):
                    self.assertEqual([r['value'] for r in result],[1120,2402])

class AlmSupplementalTests(unittest.TestCase):
    def test_real_report_reconciliation_and_preservation(self):
        data=json.loads((ROOT/'data/extended_insurer_financials.json').read_text(encoding='utf-8'))
        original=data['insurers']['Alm. Brand']
        pdf=live_alm()
        row=attach(original,pdf)
        self.assertEqual(validate_supplemental(row),[])
        self.assertEqual(row['metrics']['profit_before_tax'],544)
        self.assertEqual(row['supplemental_pdf_evidence']['metrics']['profit_before_tax']['ytd_value'],907)
        self.assertEqual(row['metrics']['return_on_equity'],pdf['metrics']['return_on_equity'])
        self.assertEqual(preserve(original,row),row)
        corrupt={**row,'metrics':{**row['metrics'],'return_on_equity':999}}
        self.assertTrue(validate_supplemental(corrupt))
        print('ALM_SUPPLEMENTAL_LIVE_VERIFIED',row['supplemental_pdf_evidence']['metrics'],flush=True)

if __name__=='__main__':unittest.main()
