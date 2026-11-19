import copy, json, sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from import_klp_production import build_snapshot,update,verify_latest
from check_extended_insurer_evidence import validate,COMPANIES,REQUIRED
from build_nine_insurer_comparison import build

def reconciled(q):
    return {'company':'KLP Skadeforsikring','year':2026,'quarter':q,
            'status':'q1_2026_pdf_reconciled_not_published' if q==1 else
                     'issuer_pdf_quarter_and_ytd_reconciled_not_published',
            'ratios':{'loss_ratio':84.5,'expense_ratio':12.5,'combined_ratio':97.0},
            'reported_quarter_amounts':{'insurance_revenue':1000+q,'insurance_service_result':30},
            'reported_ytd_amounts':{'insurance_revenue':1000+q if q==1 else 2200+q},
            'reported_prior_year_quarter_amounts':{'insurance_revenue':800+q},
            'reported_prior_year_ytd_amounts':{'insurance_revenue':800+q if q==1 else 1800+q},
            'reported_management_metrics':{'profit_before_tax':30.0,
               'profit_before_tax_ytd':30.0 if q==1 else 70.0,
               'solvency_ratio':{1:231.0,2:222.0,3:219.0}[q],
               'investment_return_ytd':{1:0.5,2:3.0,3:3.7}[q],
               'return_on_equity':None,'source_page':21 if q==1 else 20,
               'period_basis':{'profit_before_tax':'quarter',
                   'profit_before_tax_ytd':'ytd','solvency_ratio':'quarter_end',
                   'investment_return_ytd':'ytd'}},
            'reported_ytd_ratios':{'gross_loss_ratio':80,'reinsurance_ratio':4,
                                    'loss_ratio':84,'expense_ratio':13,'combined_ratio':97},
            'source_documents':[{'source_url':'https://www.klp.no/a.pdf','source_sha256':str(q)*64,
                                 'source_pages':[6]},
                                {'source_url':'https://www.klp.no/a.pdf','source_sha256':str(q)*64,
                                 'source_pages':[6,20]}]}
def fixture():
    return {'insurers':{'KLP Skadeforsikring':{'company':'KLP Skadeforsikring',
        'status':'awaiting_source_verified_metrics','metrics':{}},
      'Alm. Brand':{'company':'Alm. Brand','year':2026,'quarter':3,
       'status':'verified_issuer_announcement','source_type':'official_issuer_interim_announcement',
       'source_url':'https://investorrelations.almbrand.dk/report','metrics':{k:1.0 for k in REQUIRED}}}}
class KLPProductionTests(unittest.TestCase):
    def test_all_three_quarters_publish_with_independent_ytd(self):
        snapshot=build_snapshot(*[reconciled(q) for q in (1,2,3)])
        self.assertEqual(snapshot['metrics']['combined_ratio'],97)
        self.assertAlmostEqual(snapshot['metrics']['insurance_revenue_growth'],(1003/803-1)*100)
        self.assertNotIn('return_on_equity',snapshot['metrics'])
        self.assertEqual(snapshot['metrics']['solvency_ratio'],219)
        self.assertNotIn('investment_return_ytd',snapshot['metrics'])
        self.assertEqual(snapshot['metrics']['profit_before_tax'],30)
        self.assertAlmostEqual(snapshot['periods'][-1]['revenue_growth_evidence']['ytd']['growth_percent'],(2203/1803-1)*100)
        self.assertEqual(len(snapshot['periods']),3)
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);(root/'data').mkdir()
            (root/'data/extended_insurer_financials.json').write_text(json.dumps(fixture()))
            self.assertTrue(update(root,*[reconciled(q) for q in (1,2,3)]))
            self.assertFalse(update(root,*[reconciled(q) for q in (1,2,3)]))
            out=json.loads((root/'data/extended_insurer_financials.json').read_text())
            self.assertEqual(out['insurers']['Alm. Brand'],fixture()['insurers']['Alm. Brand'])
            self.assertEqual(validate(out,{'sources':[{'company':x} for x in COMPANIES]},
                {x:{} for x in COMPANIES}),[])
            comp=build({'observations':[]},out)
            klp=next(x for x in comp['companies'] if x['company']=='KLP Skadeforsikring')
            self.assertEqual(klp['status'],'verified_official_pdf_reconciled')
            self.assertEqual(klp['period'],'Q3 2026')
            self.assertFalse(comp['investor_use_approved'])
    def test_incomplete_periods_blocked(self):
        with self.assertRaisesRegex(ValueError,'incomplete'):
            build_snapshot(reconciled(1),reconciled(2),reconciled(2))
    def test_modified_previously_verified_quarter_blocks(self):
        snapshot=build_snapshot(*[reconciled(q) for q in (1,2,3)])
        changed=copy.deepcopy(snapshot)
        changed['periods'][0]['metrics']['combined_ratio']=88
        with self.assertRaisesRegex(ValueError,'changed'):
            verify_latest(snapshot,changed)
    def test_gate_rejects_forged_quarters(self):
        data=fixture()
        data['insurers']['KLP Skadeforsikring']=build_snapshot(*[reconciled(q) for q in (1,2,3)])
        data['insurers']['KLP Skadeforsikring']['periods'][1]['source_sha256']='bad'
        errors=validate(data,{'sources':[{'company':x} for x in COMPANIES]},
            {x:{} for x in COMPANIES})
        self.assertTrue(errors)
    def test_announcement_only_stays_announcement(self):
        a=fixture()
        self.assertEqual(a['insurers']['Alm. Brand']['status'],'verified_issuer_announcement')
if __name__=='__main__':unittest.main()
