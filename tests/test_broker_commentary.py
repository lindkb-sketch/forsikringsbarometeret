"""Broker PDFs stay browser-local; only concise approved text reaches public Pages."""
import json
import subprocess
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
HTML=(ROOT/'index.html').read_text(encoding='utf-8')
JS=(ROOT/'scripts/broker_commentary.js').read_text(encoding='utf-8')
CSS=(ROOT/'scripts/broker_commentary.css').read_text(encoding='utf-8')


class BrokerCommentaryTests(unittest.TestCase):
    def test_clean_public_feed(self):
        data=json.loads((ROOT/'data/broker_commentary.json').read_text(encoding='utf-8'))
        self.assertEqual(data['schema_version'],1)
        self.assertIsInstance(data['entries'],list)
        for row in data['entries']:
            self.assertEqual(set(row),{'company','quarter','reaction','drivers','outlook','updated_at'})
            self.assertRegex(row['quarter'],r'^Q[1-4] 20\d{2}$')
            self.assertNotIn('filename',row)
            self.assertNotIn('source_file',row)

    def test_summary_is_below_profitability_not_an_upload_widget(self):
        self.assertIn('id="cr-podium-panel"',HTML)
        self.assertIn('id="broker-commentary-panel" hidden',HTML)
        self.assertLess(HTML.index('id="cr-podium-panel"'),HTML.index('id="broker-commentary-panel"'))
        self.assertIn('scripts/broker_commentary.js',HTML)
        self.assertIn('scripts/broker_commentary.css',HTML)
        self.assertIn('.broker-summary-panel[hidden]{display:none!important}',CSS)
        self.assertIn("document.getElementById('broker-commentary-panel')",JS)
        self.assertIn('window.FBActivePeriod',JS)
        self.assertIn('currentCompany()',JS)
        self.assertIn('setInterval(loadPublic,300000)',JS)

    def test_company_page_places_broker_summary_above_market_news(self):
        company_page=HTML[HTML.index('function company(c){'):HTML.index('function methodology(){')]
        self.assertIn('id="broker-commentary-panel" hidden',company_page)
        self.assertLess(company_page.index('id="broker-commentary-panel"'),company_page.index('companyMediaNews(c)'))
        self.assertIn("NAMES.includes(current)",JS)
        self.assertIn("typeof period!=='undefined'?period",JS)

    def test_quarter_folders_created_automatically_from_verified_data(self):
        self.assertIn('data/verified_financial_feed.json',JS)
        self.assertIn('createObjectStore(name,{keyPath:',JS)
        self.assertIn("put('folders'",JS)
        self.assertIn('scope',JS)
        self.assertIn('quarter',JS)
        self.assertIn('year',JS)
        self.assertIn('sort((a,b)=>order(a)-order(b))',JS)

    def test_private_pdfs_are_never_published(self):
        self.assertIn("new URLSearchParams(location.search).get('admin')==='1'",HTML)
        self.assertIn("new URLSearchParams(location.search).get('admin')==='1'",JS)
        self.assertIn("await put('private_pdfs'",JS)
        self.assertIn("pdf:file",JS)
        self.assertIn('new Blob([contents],{type:',JS)
        self.assertIn('const value=formValues()',JS)
        self.assertIn("entries.push({company,quarter,...value,updated_at:",JS)
        self.assertNotIn("fetch('https://api.openai.com",JS)
        self.assertNotIn('localStorage.setItem',JS)

    def test_browser_script_syntax(self):
        result=subprocess.run(['node','--check',str(ROOT/'scripts/broker_commentary.js')],
                              capture_output=True,text=True,timeout=12)
        self.assertEqual(result.returncode,0,result.stderr)

    def test_public_feed_contains_only_approved_public_summaries(self):
        data=json.loads((ROOT/'data/broker_commentary.json').read_text(encoding='utf-8'))
        self.assertIsInstance(data['entries'],list)
        for entry in data['entries']:
            self.assertTrue(entry['reaction'].strip())
            self.assertNotIn('pdf',entry.keys())
            self.assertNotIn('filename',entry.keys())
        self.assertIn('Ingen lokale PDF-er i denne mappen.',JS)
        self.assertIn('Ikke del dem med ChatGPT eller andre AI-tjenester uten tillatelse',JS)


if __name__=='__main__':
    unittest.main()
