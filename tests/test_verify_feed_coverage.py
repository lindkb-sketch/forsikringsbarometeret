import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from verify_feed_coverage import validate,COMPANIES

def sample():
    return [{'company':name,'year':2026,'quarter':1,'scope':'group',
             'period_type':'quarter','metric':'insurance_revenue','value':42,
             'status':'reported'} for name in sorted(COMPANIES)]

class SevenInsurerFeedTests(unittest.TestCase):
    def test_exact_feed_parity(self):
        rows=sample()
        self.assertEqual(len(validate(rows,rows)),7)
    def test_missing_latest_quarter_fails(self):
        rows=sample()
        with self.assertRaisesRegex(ValueError,'absent'):
            validate(rows,rows[:-1])
    def test_changed_number_fails(self):
        rows=sample();feed=[dict(r) for r in rows];feed[0]['value']=43
        with self.assertRaisesRegex(ValueError,'changed'):
            validate(rows,feed)
    def test_missing_issuer_fails(self):
        rows=sample()[:-1]
        with self.assertRaisesRegex(ValueError,'missing'):
            validate(rows,rows)
if __name__=='__main__':unittest.main()
