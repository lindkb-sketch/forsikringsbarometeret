import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from import_alm_brand_production import validated_pdf,update
from check_extended_insurer_evidence import validate,COMPANIES
from build_nine_insurer_comparison import build
from update_extended_insurers import update as update_announcement

SHA='a'*64
URL='https://attachment.news.eu.nasdaq.com/ab696c52809fdbebae74678c86c8f5a78'
METRICS={'insurance_revenue':3054.,'insurance_service_result':755.,
         'combined_ratio':75.3,'loss_ratio':59.2,'expense_ratio':16.1,
         'insurance_revenue_growth':1.6,'return_on_equity':18.,
         'solvency_ratio':238.,'profit_before_tax':544.}

def report():
    return {'company':'Alm. Brand','year':2026,'quarter':3,
        'status':'verified_official_pdf_reconciled',
        'scope':'group','currency':'DKK','source_type':'official_quarterly_report',
        'source_url':URL,'source_sha256':SHA,
        'source_pages':{k:(5 if k=='solvency_ratio' else 3) for k in METRICS},
        'metrics':dict(METRICS),
        'revenue_growth_evidence':{'source_sha256':SHA,'source_page':3,
           'quarter':{'current':3054.,'prior_year':3006.,'issuer_reported_growth_percent':1.6},
           'ytd':{'current':8982.,'prior_year':8814.,'growth_percent':(8982/8814-1)*100}},
        'quarter_recalculated_ratios':{'combined_ratio':75.27832351015063,
             'loss_ratio':59.1683038637852,'expense_ratio':16.110019646365423},
        'ytd_recalculated_ratios':{'combined_ratio':86.65107993765308,
             'loss_ratio':69.66154531284792,'expense_ratio':16.989534624805167},
        'reported_ytd_ratios':{'combined_ratio':86.6,'loss_ratio':69.6,
             'expense_ratio':17.,'gross_claims_ratio':66.8,'reinsurance_ratio':2.8},
        'return_on_equity_definition':'Annualised Group return on equity after tax',
        'return_on_equity_ytd':10.,
        'return_on_equity_source_page':3,
        'solvency_definition':'Group capital / solvency capital requirement',
        'profit_before_tax_ytd':907.,
        'issuer_page_url':'https://view.news.eu.nasdaq.com/view?id=bf0c320779f45c795395beb8fb6aa3cdd&lang=da&src=listed'}

def fixture():
    return {'insurers':{
      'KLP Skadeforsikring':{'company':'KLP Skadeforsikring',
        'status':'awaiting_source_verified_metrics','metrics':{}},
      'Alm. Brand':{'company':'Alm. Brand','year':2026,'quarter':3,
        'status':'verified_issuer_announcement','source_type':'official_issuer_interim_announcement',
        'source_url':'https://investorrelations.almbrand.dk/English/press-release-details/2026/Alm--Brand-AS---Interim-report-for-Q3/default.aspx',
        'metrics':{k:v for k,v in METRICS.items()
                   if k in {'insurance_revenue','insurance_service_result',
                            'combined_ratio','loss_ratio','expense_ratio',
                            'insurance_revenue_growth'}}}}}
def prereqs():
    return ({'sources':[{'company':x} for x in COMPANIES]},
            {name:{} for name in COMPANIES})

class AlmBrandProductionTests(unittest.TestCase):
    def test_verified_pdf_promoted_and_published_with_roe(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);(root/'data').mkdir()
            path=root/'data/extended_insurer_financials.json'
            path.write_text(json.dumps(fixture()),encoding='utf-8')
            self.assertTrue(update(root,report()))
            self.assertFalse(update(root,report()))
            data=json.loads(path.read_text(encoding='utf-8'))
            self.assertEqual(data['insurers']['KLP Skadeforsikring'],fixture()['insurers']['KLP Skadeforsikring'])
            self.assertEqual(validate(data,*prereqs()),[])
            nine=build({'observations':[]},data)
            alm=next(x for x in nine['companies'] if x['company']=='Alm. Brand')
            self.assertEqual(alm['status'],'verified_official_pdf_reconciled')
            self.assertEqual(alm['metrics']['return_on_equity'],18)
            self.assertEqual(alm['metrics']['solvency_ratio'],238)
            self.assertIsNone(alm['metrics'].get('investment_return'))
            self.assertFalse(nine['investor_use_approved'])
    def test_missing_roe_is_rejected(self):
        r=report();del r['metrics']['return_on_equity']
        with self.assertRaisesRegex(ValueError,'coverage'):validated_pdf(r)
    def test_investment_return_cannot_replace_roe(self):
        r=report();r['metrics']['investment_return']=17.
        with self.assertRaisesRegex(ValueError,'forbidden'):validated_pdf(r)
    def test_incorrect_ytd_reconciliation_rejected(self):
        r=report();r['reported_ytd_ratios']['combined_ratio']=75.
        with self.assertRaisesRegex(ValueError,'HIÅ'):validated_pdf(r)
    def test_wrong_revenue_growth_comparator_rejected(self):
        r=report();r['revenue_growth_evidence']['quarter']['prior_year']=2800.
        with self.assertRaisesRegex(ValueError,'growth'):validated_pdf(r)
    def test_pdf_sha_change_blocks_update(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);(root/'data').mkdir()
            path=root/'data/extended_insurer_financials.json'
            path.write_text(json.dumps(fixture()),encoding='utf-8')
            update(root,report())
            changed=report();changed['source_sha256']='b'*64
            changed['revenue_growth_evidence']['source_sha256']='b'*64
            with self.assertRaisesRegex(ValueError,'changed'):update(root,changed)
    def test_announcement_refresh_must_preserve_verified_pdf(self):
        announcement=('Interim report for Q3 28 October 2026 '
          'Insurance revenue grew by 1.6% to DKK 3,054 million. '
          'insurance service result was DKK 755 million. combined ratio of 75.3. '
          'claims ratio of 59.2. expense ratio increased by 0.3 of a percentage point to 16.1.')
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);(root/'data').mkdir()
            path=root/'data/extended_insurer_financials.json'
            path.write_text(json.dumps(fixture()),encoding='utf-8')
            update(root,report())
            self.assertFalse(update_announcement(document=announcement,out=path))
            self.assertEqual(json.loads(path.read_text())['insurers']['Alm. Brand']['status'],
                             'verified_official_pdf_reconciled')

if __name__=='__main__':unittest.main()
