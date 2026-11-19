import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from alm_brand_live_pdf import trusted_pdf_link,find_candidates,verify_pages

URL='https://s29.q4cdn.com/228553818/files/doc_financials/2026/q3/AB-GROUP-3Q-2026.pdf'
def fixture():
    t=['']*7
    t[2]='Total capital as a percentage of solvency capital\nrequirement 238 225'
    t[0]='Alm Brand Group interim report Q3 2026'
    data=[
      ('Insurance revenue','3,054','3,006','9,000','8,900','11,790'),
      ('Claims expenses','1,700','1,600','5,000','5,100','7,000'),
      ('Insurance operating expenses','492','500','1,500','1,500','2,000'),
      ('Profit/loss on reinsurance','107','100','300','200','250'),
      ('Insurance service result','755','806','2,200','2,100','2,540'),
      ('Gross claims ratio','55.7','53.2','55.6','57.3','59.4'),
      ('Net reinsurance ratio','3.5','3.3','3.3','2.2','2.1'),
      ('Claims ratio','59.2','56.5','58.9','59.6','61.5'),
      ('Gross expense ratio','16.1','16.6','16.7','16.9','17.0'),
      ('Combined ratio','75.3','73.1','75.6','76.4','78.5')]
    t[4]='ALM. BRAND GROUP – Q3 2026\nQ3 2026 Q3 2025 Q1-Q3 2026 Q1-Q3 2025 2025\n'+'\n'.join(
         k+' '+v+' '+p+' '+y+' '+yp+' '+full for k,v,p,y,yp,full in data)
    t[4]+='\nReturn on equity after tax\n18.0 13.6 10.0 14.4 14.4\n(% p.a.) **'\n    return t
class AlmBrandLivePDFTests(unittest.TestCase):
    def test_only_issuer_cdn_and_ir_pdf(self):
        self.assertTrue(trusted_pdf_link(URL))
        self.assertFalse(trusted_pdf_link('https://evil.test/228553818/files/report.pdf'))
        self.assertFalse(trusted_pdf_link('https://s29.q4cdn.com/other/files/report.pdf'))
    def test_source_link_candidates(self):
        html='<a href="'+URL+'">AB GROUP 3Q 2026</a><a href="https://evil.test/bad.pdf">Report Q3 2026</a>'
        self.assertEqual(find_candidates(html),[(URL,'AB GROUP 3Q 2026')])
    def test_q3_and_ytd_reconciled_and_growth(self):
        res=verify_pages(fixture(),URL,b'%PDF-synthetic-test')
        self.assertEqual(res['status'],'verified_official_pdf_reconciled')
        self.assertEqual(res['metrics']['insurance_revenue_growth'],1.6)
        self.assertEqual(res['metrics']['combined_ratio'],75.3)
        self.assertAlmostEqual(res['revenue_growth_evidence']['quarter']['calculated_growth_percent'],
                               (3054/3006-1)*100)
        self.assertEqual(res['metrics']['return_on_equity'],18.0)
        self.assertEqual(res['return_on_equity_ytd'],10.0)
        self.assertEqual(res['metrics']['solvency_ratio'],238.0)
        self.assertNotIn('investment_return_ytd',res['metrics'])
    def test_issuer_announcement_mismatch_blocks(self):
        x=fixture();x[4]=x[4].replace('Insurance revenue 3,054','Insurance revenue 3,150')
        with self.assertRaises(ValueError):verify_pages(x,URL,b'%PDF-synthetic-test')
    def test_wrong_period_blocks(self):
        x=fixture();x[0]='Alm Brand Group interim report Q2 2026'
        with self.assertRaisesRegex(ValueError,'Wrong entity'):verify_pages(x,URL,b'%PDF-synthetic-test')
if __name__=='__main__':unittest.main()
