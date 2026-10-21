import sys
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from storebrand_automation_check import choose_reports, test_pipeline, download_pdf

class StorebrandAutomationTests(unittest.TestCase):
    def test_requires_both_entities(self):
        with self.assertRaisesRegex(ValueError,'Both official'):
            choose_reports([{'year':2026,'quarter':3,'scope':'group','document_url':'https://storebrand.no/a.pdf'}])
    def test_rejects_ambiguous_discovery(self):
        with self.assertRaisesRegex(ValueError,'Ambiguous'):
            choose_reports([{'year':2026,'quarter':3,'scope':'group','document_url':f'https://storebrand.no/{i}.pdf'} for i in (1,2)])
    def test_disallows_untrusted_hosts(self):
        with self.assertRaisesRegex(ValueError,'approved'):
            download_pdf('https://example.com/report.pdf',Path('/tmp/untrusted.pdf'))
    def test_full_isolated_import_from_real_pdfs(self):
        result=test_pipeline(ROOT/'tests/fixtures/storebrand_asa_q3_2026.pdf',ROOT/'tests/fixtures/storebrand_forsikring_q3_2026.pdf')
        self.assertEqual(result['status'],'passed')
        self.assertEqual(result['repeat_import']['added'],0)
        self.assertFalse(result['production_data_modified'])

if __name__=='__main__':unittest.main()
