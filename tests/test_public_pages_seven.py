import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from verify_public_pages import COMPANIES,check_seven

class PublishedDashboardTests(unittest.TestCase):
    def setUp(self):
        self.feed={'observations':[dict(company=c,year=2026,quarter=2,scope='group',
                     period_type='quarter',metric='insurance_revenue',value=100,
                     status='reported') for c in COMPANIES]}
        self.html=' '.join(sorted(COMPANIES))+' data/verified_financial_feed.json'
    def test_all_seven_rendered_and_in_feed(self):
        self.assertTrue(check_seven(self.feed,self.html))
    def test_missing_group_data_fails(self):
        self.feed['observations']=[r for r in self.feed['observations'] if r['company']!='Tryg']
        with self.assertRaisesRegex(ValueError,'Tryg'):check_seven(self.feed,self.html)
    def test_missing_company_from_html_fails(self):
        with self.assertRaisesRegex(ValueError,'Protector'):check_seven(self.feed,self.html.replace('Protector',''))
    def test_feed_not_loaded_fails(self):
        with self.assertRaisesRegex(ValueError,'does not load'):check_seven(self.feed,self.html.replace('data/verified_financial_feed.json',''))
    def test_only_norway_data_fails(self):
        self.feed['observations']=[{**r,'scope':'norway'} if r['company']=='Tryg' else r for r in self.feed['observations']]
        with self.assertRaisesRegex(ValueError,'Tryg'):check_seven(self.feed,self.html)

if __name__=='__main__':unittest.main()
