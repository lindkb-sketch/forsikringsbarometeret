import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from protector_publish import discover_pdf
P='https://storage.mfn.se/34613cd2-9b91-47d8-bae6-1c5274fa1298/interim-report-q3-2025-prot.pdf'
B='https://storage.mfn.se/other-q3-2025.pdf'
def fetch(*args):
 return ('<a href="'+P+'">Q3 2025 report</a><a href="'+B+'">Q3 2025 report</a>').encode()
class TestProtectorArchive(unittest.TestCase):
 def test_duplicate_pdf_discovery_selects_issuer_verified_q3(self):
  self.assertEqual(discover_pdf(2025,3,fetch=fetch),P)

def consensus_fetch(*args):
 return ('<a href="'+P+'">Q3 2025 interim report</a>'
         '<a href="https://cdn.prod.website-files.com/estimates_q3_2025_consensus.pdf">Q3 2025 Consensus Estimates</a>').encode()

class TestNonIssuerDocumentRejection(unittest.TestCase):
 def test_analyst_consensus_not_a_quarterly_report(self):
  self.assertEqual(discover_pdf(2025,3,fetch=consensus_fetch),P)


def bond_and_consensus(*args):
 return ('<a href="https://cdn.prod.website-files.com/2025_Q3_Contemplated%20Perpetual%20RT1%20Bond%20Issue.pdf">Q3 2025 Bond update</a>'
         '<a href="https://cdn.prod.website-files.com/2025_Q3_Consensus%20Estimates.pdf">Q3 2025 Consensus Estimates</a>').encode()
class TestNonFinancialAttachments(unittest.TestCase):
 def test_bond_update_and_consensus_cannot_substitute_for_q3_report(self):
  self.assertEqual(discover_pdf(2025,3,fetch=bond_and_consensus),P)

if __name__=='__main__':unittest.main()
