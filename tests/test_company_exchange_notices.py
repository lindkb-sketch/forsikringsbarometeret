import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / 'index.html').read_text(encoding='utf-8')

class ExchangeNoticesTests(unittest.TestCase):
    def test_company_pages_render_newsweb_only(self):
        self.assertIn('function companyExchangeNotices(c)', HTML)
        self.assertIn('${stockMarketSection(c)}${companyExchangeNotices(c)}${companyMediaNews(c)}', HTML)
        self.assertIn('Siste børsmelding · ', HTML)
        self.assertIn("if(!recent.length)return ''", HTML)
        self.assertIn('newsweb\\.oslobors\\.no', HTML)
        self.assertIn('92*24*60*60*1000', HTML)
        self.assertIn('Date.parse(b.published_at)-Date.parse(a.published_at)', HTML)

    def test_feed_is_empty_until_official_notices_verified(self):
        data=json.loads((ROOT/'data/newsweb_notices.json').read_text(encoding='utf-8'))
        self.assertEqual(data['source'],'NewsWeb')
        self.assertEqual(set(data['notices']), {'Fremtind','Gjensidige','Tryg','Sampo','Frende','Protector','Storebrand'})
        self.assertTrue(all(not rows for rows in data['notices'].values()))

if __name__ == '__main__':
    unittest.main()
