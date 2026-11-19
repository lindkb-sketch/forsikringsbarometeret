import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from klp_live_pdf_audit import audit

URL='https://www.klp.no/quarter.pdf'
class KLPLiveAuditTests(unittest.TestCase):
    def test_diagnostic_not_certification(self):
        def fetch(url,company):return b'%PDF-test'
        def extract(raw,url):return {'source_url':url,'source_sha256':'a'*64,
            'rows':[{'page':1,'table':1,'row':1,'cells':['Forsikringsinntekter','10']},
                    {'page':2,'table':1,'row':2,'cells':['Gjenforsikring','2']}]}
        result=audit(URL,fetch=fetch,extract=extract)
        self.assertEqual(result['diagnostics']['financial_rows'],2)
        self.assertFalse(result['diagnostics']['production_import_approved'])
        self.assertFalse(result['diagnostics']['hiy_ratio_reconciliation_verified'])
    def test_empty_pdf_tables_fail(self):
        with self.assertRaisesRegex(ValueError,'No financial'):
            audit(URL,fetch=lambda url,company:b'%PDF-',extract=lambda raw,url:{'rows':[]})
    def test_irrelevant_rows_fail(self):
        with self.assertRaisesRegex(ValueError,'Insufficient'):
            audit(URL,fetch=lambda url,company:b'%PDF-',extract=lambda raw,url:
                {'rows':[{'cells':['Resultat','100']}]})
if __name__=='__main__':unittest.main()
