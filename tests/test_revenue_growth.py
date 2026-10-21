import unittest
from scripts.revenue_growth import growth, isolated_quarter, validate_row, DataQualityError
class RevenueTests(unittest.TestCase):
    def test_growth(self):
        self.assertEqual(str(growth(110,100,scope='Norge',currency='NOK',metric='IFRS17',source_url='https://example.org/report')), '10.0')
    def test_isolated(self):
        self.assertEqual(isolated_quarter(300,190,270,170),(110,100))
    def test_no_source(self):
        with self.assertRaises(DataQualityError): growth(110,100,scope='Norge',currency='NOK',metric='IFRS17',source_url='')
    def test_zero_prior(self):
        with self.assertRaises(DataQualityError): growth(110,0,scope='Norge',currency='NOK',metric='IFRS17',source_url='https://example.org')
    def test_mismatch(self):
        with self.assertRaises(DataQualityError): validate_row(dict(company='A',period='Q3',scope='Norge',currency='NOK',metric='IFRS17',source_url='https://example.org',current=110,previous=100,reported_growth=25))
if __name__=='__main__': unittest.main()
