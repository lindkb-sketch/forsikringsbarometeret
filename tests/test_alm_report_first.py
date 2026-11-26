import copy
import datetime as dt
import json
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from rolling_alm_brand_reports import advance,validate_rolling
from advance_alm_brand import promote
from alm_brand_report_discovery import rss_notices,notice_reports,notice_url
from test_extended_rolling_periods import base_alm,alm_fixture,ALMU4,PRES4
from alm_brand_live_pdf import nasdaq_attachment,download_report,OFFICIAL_FILING_PDF
from check_nine_report_primary import check
from build_nine_insurer_comparison import build
ROOT=Path(__file__).resolve().parents[1]

class ReportFirstTests(unittest.TestCase):
    def test_report_without_presentation_advances(self):
        old=base_alm()
        data=advance(old,today=dt.date(2027,2,1),
            fetcher=lambda _:f'<a href="{ALMU4}">AB GROUP 4Q 2026</a>',
            downloader=lambda u:b'%PDF-Q4',reader=lambda _:(alm_fixture(2026,4),{}))
        self.assertEqual((data['year'],data['quarter']),(2026,4))
        self.assertEqual(data['presentation_check'],'not_available')
        self.assertEqual(validate_rolling(data),[])
    def test_presentation_alone_cannot_advance(self):
        old=base_alm()
        self.assertEqual(advance(old,today=dt.date(2027,2,1),
            fetcher=lambda _:f'<a href="{PRES4}">Investor presentation Q4 2026</a>',
            downloader=lambda u:self.fail('No original report')),old)
    def test_live_q3_primary_report_no_value_change(self):
        old=base_alm()
        new=promote(old)
        self.assertEqual(new['status'],'verified_official_pdf_reconciled')
        self.assertEqual(new['source_type'],'official_quarterly_report')
        self.assertEqual(new['metrics'],old['metrics'])
        self.assertEqual(len(new['source_pages']),9)
        self.assertEqual(validate_rolling(new),[])
    def test_exchange_notice_is_period_and_issuer_bound(self):
        url='https://view.news.eu.nasdaq.com/view?id='+'a'*32
        title='Alm. Brand A/S - Interim report for Q4'
        xml=f'<rss><channel><item><title>{title}</title><link>{url}</link><pubDate>Thu, 28 Jan 2027 07:00:00 GMT</pubDate></item></channel></rss>'
        self.assertEqual(len(rss_notices(xml,2026,4)),1)
        self.assertEqual(rss_notices(xml.replace('Alm. Brand','Other issuer'),2026,4),[])
        self.assertEqual(rss_notices(xml,2026,3),[])
        attachment='https://attachment.news.eu.nasdaq.com/'+'b'*32
        text=f'<h1>{title}</h1><a href="{attachment}">AB GROUP 4Q 2026.pdf</a><a href="{attachment.replace("b"*32,"c"*32)}">AB GROUP 3Q 2026.pdf</a>'
        docs=notice_reports(text,url,2026,4,title,dt.date(2027,1,28))
        self.assertEqual([x['url'] for x in docs],[attachment])
        self.assertFalse(notice_url(url.replace('view.news.eu.nasdaq.com','evil.test')))
        self.assertFalse(nasdaq_attachment(attachment+'?x=1'))
    def test_all_nine_report_gate_rejects_announcement(self):
        load=lambda n:json.loads((ROOT/'data'/n).read_text())
        feed=load('verified_financial_feed.json');ext=load('extended_insurer_financials.json')
        ext['insurers']['Alm. Brand']=promote(base_alm())
        comparison=build(feed,ext)
        self.assertEqual(check(feed,ext,comparison),[])
        bad=copy.deepcopy(feed)
        for r in bad['observations']:
            if r.get('company')=='Tryg' and r.get('scope')=='group' and (r.get('year'),r.get('quarter'))==(2026,3):
                r['source_type']='official_issuer_interim_announcement'
        self.assertTrue(any('Tryg' in e for e in check(bad,ext,build(bad,ext))))
if __name__=='__main__':unittest.main()
