import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from klp_pdf_column_mapping import extract,parse_cell

SCHEMA={'quarter_column':1,'ytd_column':2,'page':10,'table':1,'unit':'NOK million',
 'issuer_definition_verified':True,
 'labels':{'insurance_revenue':'Forsikringsinntekter','gross_claims_cost':'Brutto erstatninger',
           'reinsurance_effect':'Gjenforsikring','operating_expenses':'Driftskostnader'},
 'ratio_labels':{'gross_loss_ratio':'Skadeprosent brutto','reinsurance_ratio':'Gjenforsikringsprosent',
                 'loss_ratio':'Skadeprosent etter gjenforsikring','expense_ratio':'Kostnadsprosent',
                 'combined_ratio':'Totalskadeprosent'}}
def rows():
    vals=[('Forsikringsinntekter','100','300'),('Brutto erstatninger','82,8','240'),
          ('Gjenforsikring','3,7','12'),('Driftskostnader','13,8','42'),
          ('Skadeprosent brutto','82,8%','80,0%'),('Gjenforsikringsprosent','3,7%','4,0%'),
          ('Skadeprosent etter gjenforsikring','86,5%','84,0%'),
          ('Kostnadsprosent','13,8%','14,0%'),('Totalskadeprosent','100,3%','98,0%')]
    return [{'page':10,'table':1,'row':i,'cells':list(v)} for i,v in enumerate(vals,1)]
class KLPColumnTests(unittest.TestCase):
    def test_explicit_columns_and_ytd_reconciliation(self):
        r=extract(rows(),SCHEMA,year=2026,quarter=3,url='https://www.klp.no/test.pdf',sha='a'*64)
        self.assertEqual(r['quarter_components']['insurance_revenue'],100)
        self.assertEqual(r['ytd_components']['insurance_revenue'],300)
        self.assertAlmostEqual(r['ratios']['combined_ratio'],100.3)
    def test_wrong_reported_ytd_blocks(self):
        x=rows();x[-1]['cells'][2]='80%'
        with self.assertRaisesRegex(ValueError,'reconciliation'):extract(x,SCHEMA,year=2026,quarter=3,url='https://www.klp.no/test.pdf',sha='a'*64)
    def test_no_guess_of_columns(self):
        s=dict(SCHEMA);s.pop('quarter_column')
        with self.assertRaisesRegex(ValueError,'columns'):extract(rows(),s,year=2026,quarter=3,url='https://www.klp.no/test.pdf',sha='a'*64)
    def test_duplicate_row_rejected(self):
        x=rows();x.append(dict(x[0]))
        with self.assertRaisesRegex(ValueError,'ambiguous'):extract(x,SCHEMA,year=2026,quarter=3,url='https://www.klp.no/test.pdf',sha='a'*64)
    def test_norwegian_number(self):
        self.assertEqual(float(parse_cell('1 234,5')),1234.5)
if __name__=='__main__':unittest.main()
