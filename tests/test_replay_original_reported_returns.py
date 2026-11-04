"""Original historical-return replay must verify PDF bytes, page, and parsed amount."""
import hashlib,sys,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import replay_original_reported_returns as replay

BLOB=b'%PDF-test-source'
SHA=hashlib.sha256(BLOB).hexdigest()
URL='https://issuer.example/original-q1-2026.pdf'

def reference(**kw):
    row=dict(company='Gjensidige',year=2026,quarter=1,scope='group',
             period_type='quarter',metric='return_on_equity',status='reported',
             source_type='official_quarterly_report',source_url=URL,
             source_page=5,source_sha256=SHA,source_document_period='Q1 2026',
             value=27.7)
    row.update(kw)
    return row

class OriginalReturnReplayTests(unittest.TestCase):
    def call(self,row,parser=None,fetch=None):
        parser=parser or (lambda *a:(5,27.7,'ROE annualised'))
        fetch=fetch or (lambda *a:BLOB)
        with patch.object(replay,'audit',return_value={'ok':True}):
            return replay.reconstruct({'observations':[]},[row],'Gjensidige',fetch,parser)

    def test_parses_value_from_original_fingerprinted_pdf(self):
        rows,added,blocked=self.call(reference())
        self.assertFalse(blocked)
        self.assertEqual(len(added),1)
        self.assertEqual(rows['observations'][0]['value'],27.7)
        self.assertEqual(rows['observations'][0]['source_sha256'],SHA)

    def test_fingerprint_mismatch_does_not_restore(self):
        rows,added,blocked=self.call(reference(source_sha256='f'*64))
        self.assertFalse(added)
        self.assertTrue(blocked)
        self.assertFalse(rows['observations'])

    def test_wrong_page_or_value_rejected(self):
        for parser in (lambda *a:(4,27.7,'ROE'),lambda *a:(5,99.9,'ROE')):
            with self.subTest(parser=parser):
                rows,added,blocked=self.call(reference(),parser=parser)
                self.assertFalse(added)
                self.assertTrue(blocked)
                self.assertFalse(rows['observations'])

    def test_unverified_source_rejected(self):
        rows,added,blocked=self.call(reference(source_url='http://bad.example/q1.pdf'))
        self.assertFalse(added)
        self.assertTrue(blocked)

    def test_ytd_requires_first_quarter(self):
        rows,added,blocked=self.call(reference(quarter=2,period_type='ytd'))
        self.assertFalse(added)
        self.assertTrue(blocked)

    def test_does_not_copy_reference_value(self):
        rows,added,blocked=self.call(reference(value=35.0))
        self.assertFalse(added)
        self.assertTrue(blocked)

if __name__=='__main__':unittest.main()
