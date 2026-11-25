"""Test explicitly labelled Sampo quarter, HIÅ and quarter-end columns."""
import hashlib
import io
import sys
import unittest
import urllib.request
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import pdfplumber
from sampo_group_kpis import parse_overview
from build_nine_insurer_comparison import build

URL='https://www.sampo.com/globalassets/investors/quarterly-reporting/2026/q3/interim-statement_q3_2026.pdf'
SHA='a'*64

def fixture(year=2026,quarter=3):
    end=quarter*3
    return [(8,f"""Financial overview {end-2}–{end}/{year} {end-2}–{end}/{year-1} 1–{end}/{year} 1–{end}/{year-1} {year-1}
Insurance revenue (incl. brokerage), net EURm 2,503 2,303 7,303 6,755 9,078
Underwriting result EURm 435 392 1,221 1,121 1,485
Profit before taxes EURm 323 866 934 1,769 2,436
Solvency II ratio (incl. distribution accrual) % — — 175 172 174
Return on equity own funds % — — 33.4 34.0 32.3
Nordic underlying development
""")]

class SampoKPI(unittest.TestCase):
    def test_explicit_periods_and_provenance(self):
        rows=parse_overview(fixture(),URL,2026,3,SHA)
        values={(r['metric'],r['period_type']):r['value'] for r in rows}
        self.assertEqual(values,{('profit_before_tax','quarter'):323,('profit_before_tax','ytd'):934,
            ('solvency_ratio','quarter'):175,('return_on_equity','ytd'):33.4})
        self.assertTrue(all(r['source_page']==8 and r['source_sha256']==SHA and r['source_scope']=='group' for r in rows))

    def test_future_period_and_ambiguous_or_missing_columns(self):
        self.assertEqual(len(parse_overview(fixture(2027,2),URL,2027,2,SHA)),4)
        with self.assertRaisesRegex(ValueError,'period header'):
            parse_overview(fixture(),URL,2026,2,SHA)
        broken=[(8,fixture()[0][1].replace('— — 33.4 34.0 32.3','33.4 34.0 32.3'))]
        with self.assertRaisesRegex(ValueError,'column mismatch'):
            parse_overview(broken,URL,2026,3,SHA)

    def test_missing_roe_is_not_fabricated(self):
        pages=[(8,fixture()[0][1].replace('— — 33.4 34.0 32.3','— — — 34.0 32.3'))]
        rows=parse_overview(pages,URL,2026,3,SHA)
        self.assertFalse(any(r['metric']=='return_on_equity' for r in rows))

    def test_comparison_keeps_ytd_basis(self):
        rows=parse_overview(fixture(),URL,2026,3,SHA)
        result=build({'observations':rows},{'insurers':{}})
        sampo=next(r for r in result['companies'] if r['company']=='Sampo')
        self.assertEqual(sampo['metrics']['return_on_equity'],33.4)
        self.assertEqual(sampo['metric_periods']['return_on_equity'],'ytd')
        self.assertEqual(sampo['metric_sources']['return_on_equity']['source_page'],8)

    def test_real_q3_2026_issuer_pdf(self):
        request=urllib.request.Request(URL,headers={'User-Agent':'Mozilla/5.0'})
        with urllib.request.urlopen(request,timeout=60) as response:
            blob=response.read(30_000_001)
        self.assertLessEqual(len(blob),30_000_000)
        self.assertTrue(blob.startswith(b'%PDF'))
        with pdfplumber.open(io.BytesIO(blob)) as pdf:
            pages=[(i+1,p.extract_text() or '') for i,p in enumerate(pdf.pages)]
        rows=parse_overview(pages,URL,2026,3,hashlib.sha256(blob).hexdigest())
        values={(r['metric'],r['period_type']):r['value'] for r in rows}
        self.assertEqual(values,{('profit_before_tax','quarter'):323,('profit_before_tax','ytd'):934,
            ('solvency_ratio','quarter'):175,('return_on_equity','ytd'):33.4})

if __name__=='__main__':unittest.main()
