import unittest
from scripts.publication_provenance import build, COMPANIES

class ProvenanceTests(unittest.TestCase):
    def rows(self):
        source = []
        for company in COMPANIES:
            source.append(dict(company=company, year=2026, quarter=3, scope='group',
                               period_type='quarter', metric='combined_ratio', value=85,
                               status='reported', source_type='official_quarterly_report',
                               source_url='https://example.org/official.pdf'))
        return source

    def test_seven_issuers_not_falsely_certified(self):
        rows = self.rows()
        result = build(rows, [dict(row) for row in rows])
        self.assertEqual(len(result['companies']), 7)
        self.assertTrue(all(row['source_to_feed_parity'] for row in result['companies']))
        self.assertTrue(all(not row['fully_automatic_certified'] for row in result['companies']))

    def test_modified_publication_fails(self):
        source = self.rows()
        feed = [dict(row) for row in source]
        feed[0]['value'] = 77
        with self.assertRaisesRegex(ValueError, 'altered published'):
            build(source, feed)

    def test_unofficial_source_fails(self):
        source = self.rows()
        source[0]['source_type'] = 'unverified'
        with self.assertRaisesRegex(ValueError, 'non-official'):
            build(source, source)

    def test_duplicate_metric_fails(self):
        source = self.rows()
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            build(source + [dict(source[0])], source)

if __name__ == '__main__':
    unittest.main()
