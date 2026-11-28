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

    def test_broker_summary_only_on_company_pages(self):
        home=HTML[HTML.index('function home(){'):HTML.index('function company(c){')]
        company=HTML[HTML.index('function company(c){'):HTML.index('function methodology(){')]
        self.assertNotIn('id="broker-commentary-panel"',home)
        self.assertIn('id="broker-commentary-panel" hidden',company)
        self.assertIn('scripts/broker_commentary.js',HTML)
        self.assertIn('scripts/broker_commentary.css',HTML)
        self.assertIn('.broker-summary-panel[hidden]{display:none!important}',CSS)
        self.assertIn("document.getElementById('broker-commentary-panel')",JS)
        self.assertIn('currentCompany()',JS)
        self.assertIn('setInterval(loadPublic,300000)',JS)

    def test_company_page_places_broker_summary_above_market_news(self):
        company_page=HTML[HTML.index('function company(c){'):HTML.index('function methodology(){')]
        self.assertIn('id="broker-commentary-panel" hidden',company_page)
        self.assertLess(company_page.index('id="broker-commentary-panel"'),company_page.index('companyMediaNews(c)'))
        self.assertIn("NAMES.includes(current)",JS)
        self.assertIn('window.FBActivePeriod',JS)
        self.assertIn("e.company===c&&e.quarter===q",JS)

    def test_public_broker_period_is_exact_year_and_quarter(self):
        start=JS.index('const currentQuarter=()=>{')
        end=JS.index('function valid(raw)',start)
        script=JS[start:end]+"""
const assert=require('node:assert/strict');
const QUARTER=/^Q[1-4] 20\\d{2}$/;
const quarters=['Q3 2025','Q3 2026'];
const window={FBActivePeriod:{year:2025,quarter:3}};
assert.equal(currentQuarter(),'Q3 2025');
window.FBActivePeriod={year:2026,quarter:3};
assert.equal(currentQuarter(),'Q3 2026');
window.FBActivePeriod={year:2026,quarter:4};
assert.equal(currentQuarter(),'Q4 2026');
window.FBActivePeriod=null;
assert.equal(currentQuarter(),'');
"""
        p=subprocess.run(['node','-e',script],capture_output=True,text=True,timeout=12)
        self.assertEqual(p.returncode,0,p.stderr)

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
