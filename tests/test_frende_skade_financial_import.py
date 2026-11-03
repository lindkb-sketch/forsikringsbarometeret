"""Regression contract for Frende Skade PDF extraction, separate from Holding."""
import unittest
from scripts.import_frende_skade import parse_page,parse_pdf_numbers,parse_legacy_2024_revenue,build

PDF='https://live.euronext.com/offisielt.pdf'
Q3='''Kvartalsrapport, tredje kvartal 2026|Resultat
Resultat
Resultatregnskap 3.kv.2026 3.kv.2025 01.01-30.09.26 01-01-30.09.25 31.12.2025
I tusen kroner
Teknisk regnskap for skadeforsikring
Premieinntekter for egen regning 961 391 825 529 2 787 759 2 420 547 3 275 575
Erstatningskostnader for egen regning 596 615 513 840 1 893 934 1 703 865 2 231 872
Forskringsrelaterte driftskostnader 172 109 143 752 452 805 411 862 598 135
Resultat av teknisk regnskap i skadeforsikring 192 667 167 938 441 020 304 820 445 567
Nøkkelinformasjon
Kostnadsandel % 17,9 % 17,4 % 16,2 % 17,0 % 18,3 %
Skade % E/R 62,1 % 62,2 % 67,9 % 70,4 % 68,1 %
Combined Ratio 80,0 % 79,7 % 84,2 % 87,4 % 86,4 %
'''
class FrendeSkadePDFTests(unittest.TestCase):
    def test_pdf_thousands_grouping_has_unique_five_columns(self):
        s='961 391 825 529 2 787 759 2 420 547 3 275 575'
        self.assertEqual(parse_pdf_numbers(s,5),[961391,825529,2787759,2420547,3275575])
    def test_actual_q3_reported_ytd_and_same_period_last_year(self):
        rows=parse_page(Q3,2026,3,PDF,'a'*64,3)
        self.assertEqual(len(rows),20)
        d={(r['year'],r['period_type'],r['metric']):r['value'] for r in rows}
        self.assertEqual(d[(2026,'quarter','insurance_revenue')],961.391)
        self.assertEqual(d[(2025,'quarter','insurance_revenue')],825.529)
        self.assertEqual(d[(2026,'quarter','insurance_service_result')],192.667)
        self.assertEqual(d[(2025,'quarter','insurance_service_result')],167.938)
        self.assertEqual(d[(2026,'quarter','combined_ratio')],80.0)
        self.assertEqual(d[(2025,'quarter','combined_ratio')],79.7)
        self.assertEqual(d[(2025,'quarter','loss_ratio')],62.2)
        self.assertEqual(d[(2025,'quarter','expense_ratio')],17.4)
        self.assertEqual(d[(2026,'ytd','insurance_revenue')],2787.759)
        self.assertEqual(d[(2025,'ytd','insurance_revenue')],2420.547)
        self.assertEqual(d[(2026,'ytd','combined_ratio')],84.2)
        self.assertEqual(d[(2025,'ytd','combined_ratio')],87.4)
        self.assertEqual({r['year'] for r in rows},{2025,2026})
        self.assertTrue(all(r['source_entity']=='Frende Skadeforsikring AS' for r in rows))
        self.assertTrue(all(r['source_url']==PDF for r in rows))
        self.assertTrue(all(r['source_document_period']=='Q3 2026' for r in rows))
        self.assertTrue(all(r['source_sha256']=='a'*64 for r in rows))
        self.assertTrue(all('fjorårskolonne' in r['source_definition'] for r in rows if r['year']==2025))

    def test_future_2027_quarter_automatically_imports_2026_comparisons(self):
        # The importer must not contain a hardcoded 2026 period boundary.
        future=Q3.replace('2026','2027').replace('2025','2026')
        rows=parse_page(future,2027,3,PDF,'b'*64,3)
        self.assertEqual({r['year'] for r in rows},{2026,2027})
        self.assertEqual(len(rows),20)
        self.assertEqual(
            next(r['value'] for r in rows if r['year']==2026 and
                 r['period_type']=='quarter' and r['metric']=='combined_ratio'),
            79.7)
    def test_q1_negative_prior_year_result_is_preserved(self):
        q1='''Resultatregnskap 1.kv.2026 1.kv.2025 31.12.2025
Teknisk regnskap for skadeforsikring
Premieinntekter for egen regning 893535 773391 3275575
Erstatningskostnader for egen regning 685018 649203 2231872
Forskringsrelaterte driftskostnader 150421 140599 598135
Resultat av teknisk regnskap i skadeforsikring 58095 -16410 445567
Nøkkelinformasjon
Kostnadsandel % 16,8% 18,2% 18,3%
Skade % E/R 76,7% 83,9% 68,1%
Combined Ratio 93,5% 102,1% 86,4%'''
        rows=parse_page(q1,2026,1,PDF,'c'*64,18)
        self.assertEqual(len(rows),20)
        self.assertEqual(
            next(r['value'] for r in rows if r['year']==2025 and
                 r['period_type']=='quarter' and r['metric']=='insurance_service_result'),
            -16.41)
        self.assertEqual(
            next(r['value'] for r in rows if r['year']==2025 and
                 r['period_type']=='quarter' and r['metric']=='combined_ratio'),
            102.1)

    def test_2024_issuer_pdf_revenue_for_2025_growth_percentages(self):
        cases=[
            (1,'01.01-31.03.2024 01.01-31.03.2023 31.12.2023',
             '642 453 585 130 2 444 087',642.453,585.13),
            (2,'2.kv.2024 2.kv.2023 01.01-30.06.2024 01.01-30.06.2023 31.12.2023',
             '6 65 117 604 296 1 307 570 1 189 426 2 444 087',665.117,604.296),
            (3,'3.kv.2024 3.kv.2023 01.01-30.09.2024 01.01-30.09.2023 31.12.2023',
             '6 88 230 6 21 760 1 995 800 1 811 186 2 444 087',688.23,621.76)]
        for quarter,heading,values,expected,previous in cases:
            with self.subTest(quarter=quarter):
                html=('Frende Skadeforsikring AS\\nResultatregnskap '+heading+
                      '\\nTeknisk regnskap for skadeforsikring\\n'
                      'Premieinntekter for egen regning '+values)
                rows=parse_legacy_2024_revenue(
                    html,2024,quarter,PDF,'d'*64,4)
                byyear={(r['year'],r['period_type']):r['value'] for r in rows}
                self.assertEqual(byyear[(2024,'quarter')],expected)
                self.assertEqual(byyear[(2023,'quarter')],previous)
                self.assertEqual(byyear[(2024,'ytd')],expected if quarter==1 else
                                 {2:1307.57,3:1995.8}[quarter])
                self.assertTrue(all(r['source_entity']=='Frende Skadeforsikring AS'
                                    for r in rows))

    def test_wrong_period_and_mismatching_ratio_rejected(self):
        with self.assertRaisesRegex(ValueError,'year/quarter mismatch'):
            parse_page(Q3,2026,2,PDF,'a'*64,3)
        with self.assertRaisesRegex(ValueError,'combined ratio'):
            parse_page(Q3.replace('80,0 %','89,0 %'),2026,3,PDF,'a'*64,3)
    def test_unverified_pdf_never_creates_rows(self):
        result=build({'reports':[{'year':2026,'quarter':3,'source_url':'https://frende.wrep.it/q3-2026-frende-skadeforsikring-as'}]})
        self.assertFalse(result['observations'])
        self.assertTrue(result['diagnostics'])
if __name__=='__main__': unittest.main()
