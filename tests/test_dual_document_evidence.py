import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from dual_document_evidence import validate_evidence, reconcile_documents, missing_after_both_checked

BASE = dict(company="Alm. Brand", document_type="results_presentation",
 source_url="https://example.org/official-presentation.pdf", issuer_verified=True,
 source_sha256="a"*64, source_page=19, year=2026, quarter=3,
 period_type="quarter", scope="group", metric="solvency_ratio",
 unit="percent", value=238.0)

class DualDocumentEvidenceTests(unittest.TestCase):
 def test_slide_evidence(self):
  self.assertEqual(reconcile_documents([BASE])[("Alm. Brand",2026,3,"quarter","group","solvency_ratio","percent")]["value"],238)
 def test_conflicting_report_is_blocked(self):
  report=dict(BASE, document_type="quarterly_report", value=225)
  with self.assertRaises(ValueError):
   reconcile_documents([BASE, report])
 def test_complementary_metrics(self):
  other=dict(BASE, document_type="quarterly_report", metric="insurance_revenue", unit="DKK million", value=3054)
  self.assertEqual(len(reconcile_documents([BASE,other])),2)
 def test_missing_provenance_rejected(self):
  with self.assertRaises(ValueError):
   validate_evidence(dict(BASE, source_sha256=""))
 def test_missing_requires_both(self):
  with self.assertRaises(ValueError):
   missing_after_both_checked("solvency_ratio", True, False)
  self.assertIsNone(missing_after_both_checked("solvency_ratio",True,True))

if __name__ == "__main__":
 unittest.main()
