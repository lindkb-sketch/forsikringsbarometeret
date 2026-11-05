import unittest
from pathlib import Path

HTML = (Path(__file__).resolve().parents[1] / 'index.html').read_text(encoding='utf-8')

class ExchangeNoticesTests(unittest.TestCase):
    def test_all_company_pages_have_official_source_section(self):
        self.assertIn('function companyExchangeNotices(c)', HTML)
        self.assertIn('${stockMarketSection(c)}${companyExchangeNotices(c)}${companyMediaNews(c)}', HTML)
        self.assertIn('Siste børsmeldinger · ', HTML)
        self.assertIn('Kilde: Oslo Børs NewsWeb', HTML)
        self.assertNotIn('Fremtind – finansiell informasjon', HTML)

    def test_unverified_newsweb_feed_not_claimed_live(self):
        self.assertIn('Automatisk import fra NewsWeb er ikke aktivert', HTML)
        self.assertIn('https://newsweb.oslobors.no/', HTML)

if __name__ == '__main__':
    unittest.main()
