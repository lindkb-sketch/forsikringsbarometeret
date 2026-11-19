import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from klp_pdf_tables import table_evidence

URL='https://www.klp.no/quarter.pdf'
class KLPTableEvidenceTests(unittest.TestCase):
    def test_page_and_row_provenance(self):
        def fake(raw):
            yield 8,[[['Forsikringsinntekter','100','300'],['Gjenforsikring','-10','-30'],['Unrelated','0']]]
        result=table_evidence(b'%PDF-1.7 sample',URL,extractor=fake)
        self.assertEqual(len(result['rows']),2)
        self.assertEqual(result['rows'][0]['page'],8)
        self.assertEqual(result['rows'][0]['cells'][1],'100')
        self.assertEqual(result['status'],'diagnostic_table_evidence_not_verified_financials')
        self.assertNotIn('metrics',result)
    def test_reject_wrong_host(self):
        with self.assertRaisesRegex(ValueError,'Unapproved'):
            table_evidence(b'%PDF-1.7','https://klp.no.evil.test/a.pdf',extractor=lambda raw:[])
    def test_reject_fake_pdf(self):
        with self.assertRaisesRegex(ValueError,'invalid'):
            table_evidence(b'not a pdf',URL,extractor=lambda raw:[])
    def test_reject_bad_page(self):
        with self.assertRaisesRegex(ValueError,'page'):
            table_evidence(b'%PDF-1.7',URL,extractor=lambda raw:[(0,[[['Forsikringsinntekter','1']]])])
if __name__=='__main__':unittest.main()
