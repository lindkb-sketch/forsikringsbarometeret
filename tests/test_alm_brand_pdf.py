import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from alm_brand_pdf import extract_table,inspect_report
URL='https://investorrelations.almbrand.dk/reports/Q3.pdf'
def rows():
    return [{'page':7,'period':'Q3 2026','label':label,'value':value,'unit':unit}
        for label,value,unit in [
            ('Insurance revenue',3054,'DKK million'),
            ('Insurance service result',755,'DKK million'),
            ('Combined ratio',75.3,'%'),
            ('Claims ratio',59.2,'%'),
            ('Expense ratio',16.1,'%')]]
class AlmBrandPDFContractTests(unittest.TestCase):
    def test_isolated_quarter_table(self):
        result=extract_table(b'%PDF-1.7 test',URL,2026,3,rows())
        self.assertEqual(result['metrics']['insurance_revenue'],3054)
        self.assertEqual(result['source_pages']['loss_ratio'],7)
        self.assertIn('pending_independent_reconciliation',result['status'])
    def test_reject_ytd_instead_of_quarter(self):
        r=rows()
        for row in r:row['period']='YTD Q3 2026'
        with self.assertRaisesRegex(ValueError,'Incomplete'):extract_table(b'%PDF-test',URL,2026,3,r)
    def test_reject_duplicate_metric(self):
        r=rows();r.append(dict(r[0]))
        with self.assertRaisesRegex(ValueError,'duplicate'):extract_table(b'%PDF-test',URL,2026,3,r)
    def test_reject_wrong_units(self):
        r=rows();r[0]['unit']='NOK million'
        with self.assertRaisesRegex(ValueError,'units'):extract_table(b'%PDF-test',URL,2026,3,r)
    def test_reject_nonissuer_url(self):
        with self.assertRaisesRegex(ValueError,'Unapproved'):extract_table(b'%PDF-test','https://evil.test/report.pdf',2026,3,rows())
    def test_reject_incomplete(self):
        with self.assertRaisesRegex(ValueError,'Incomplete'):extract_table(b'%PDF-test',URL,2026,3,rows()[:-1])
    def test_reject_missing_page(self):
        r=rows();r[0]['page']=0
        with self.assertRaisesRegex(ValueError,'page'):extract_table(b'%PDF-test',URL,2026,3,r)
if __name__=='__main__':unittest.main()
