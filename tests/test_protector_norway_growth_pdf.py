"""PDF-only Norway comparators must be sourced from the Norway columns."""
import unittest
from scripts.import_protector_norway_historical_pdf import parse_norway_revenue,merge_observations

URL='https://storage.mfn.se/34613cd2-9b91-47d8-bae6-1c5274fa1298/interim-report-q3-2025-prot.pdf'
PAGE='''Interim Report (unaudited)Q3 and Q1-Q3 2025|Notes
Segment information - Q3
UK Sweden Norway Denmark France
NOKm Q3 2025 Q3 2024 Q3 2025 Q3 2024 Q3 2025 Q3 2024 Q3 2025 Q3 2024 Q3 2025 Q3 2024
Gross written premium 940 995 315 316 229 231 122 121 71
Insurance revenue 1,489 1,293 812 704 665 589 469 415 94
Insurance service result 295 284 108 168 78 178 132 (126) (16)'''

class ProtectorNorwayGrowthPDFTests(unittest.TestCase):
    def test_q3_norway_2024_comes_from_norway_revenue_column(self):
        rows=parse_norway_revenue([(14,PAGE)],URL,'a'*64)
        self.assertEqual([(r['year'],r['value']) for r in rows],[(2025,665),(2024,589)])
        self.assertTrue(all(r['scope']=='norway' and r['source_page']==14 for r in rows))
        self.assertTrue(all(r['source_document_period']=='Q3 2025' for r in rows))
    def test_historical_import_preserves_norway_private_and_commercial_segments(self):
        def obs(company,scope,segment,metric,value):
            return dict(company=company,scope=scope,segment=segment,year=2026,
                        quarter=1,period_type='quarter',metric=metric,value=value,
                        source_url='https://issuer.example/test.pdf',
                        source_sha256='a'*64,source_page=1)
        rows=[
            obs('Gjensidige','reported_segment','Private Norway','insurance_revenue',100),
            obs('Gjensidige','reported_segment','Commercial Norway','insurance_revenue',200),
            obs('Gjensidige','norway',None,'insurance_revenue',300),
            obs('Protector','norway',None,'insurance_revenue',700),
        ]
        addition=obs('Protector','norway',None,'insurance_revenue',589)
        addition['year']=2024
        addition['quarter']=3
        merged=merge_observations({'observations':rows},[addition])
        self.assertEqual(len(merged['observations']),5)
        segments=[r for r in merged['observations'] if r['company']=='Gjensidige'
                  and r['scope']=='reported_segment']
        self.assertEqual({r['segment'] for r in segments},
                         {'Private Norway','Commercial Norway'})
        self.assertEqual({r['value'] for r in segments},{100,200})
        self.assertEqual(len([r for r in merged['observations'] if r['company']=='Protector']),2)
    def test_reject_duplicate_segment_identity_instead_of_losing_rows(self):
        row=dict(company='Gjensidige',scope='reported_segment',segment='Private Norway',
                 year=2026,quarter=1,period_type='quarter',metric='insurance_revenue',value=100)
        with self.assertRaisesRegex(ValueError,'Duplicate'):
            merge_observations({'observations':[row,dict(row)]},[])

    def test_no_group_totals_or_wrong_quarter(self):
        with self.assertRaises(ValueError):
            parse_norway_revenue([(14,PAGE.replace('Norway','Norwayx'))],URL,'a'*64)
        with self.assertRaises(ValueError):
            parse_norway_revenue([(14,PAGE.replace('Segment information - Q3','Segment information - Q2'))],URL,'a'*64)

if __name__=='__main__':
    unittest.main()
