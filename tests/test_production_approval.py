import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from check_production_approval import evaluate,SEVEN,NINE

def fixture():
 ready={'investor_ready':True,'status':'APPROVED_FOR_INVESTOR_USE',
        'financial_quarter_complete':True,'all_seven_automated':True,
        'definitions_comparable':True,'market_data_fresh':True,
        'companies':[{'company':c,'end_to_end_automation_certified':True} for c in SEVEN]}
 comparison={'count':9,'investor_use_approved':True,
             'companies':[{'company':c} for c in NINE]}
 gaps={'all_seven_dual_document_verified':True,
       'companies':[{'company':c,'both_documents_checked_for_this_period':True} for c in SEVEN]}
 dual={'metrics_published':False,'investor_use_approved':False,
       'companies':[{'company':c,'both_documents_verified':True,
                    'metric_extraction_status':'verified_and_reconciled',
                    'cross_document_matches':[{'metric':'combined_ratio','status':'match'}],
                    'conflicts':[]} for c in NINE]}
 return ready,comparison,gaps,dual

class ProductionApprovalTests(unittest.TestCase):
 def test_complete_independent_evidence_allows_approval(self):
  self.assertTrue(evaluate(*fixture())['approved'])
 def test_missing_dual_document_artifact_blocks(self):
  a,b,c,d=fixture()
  self.assertIn('nine_insurer_document_verification_evidence_missing',evaluate(a,b,c,None)['blockers'])
 def test_investor_not_ready_blocks(self):
  a,b,c,d=fixture();a['investor_ready']=False
  self.assertFalse(evaluate(a,b,c,d)['approved'])
 def test_single_issuer_unverified_blocks(self):
  a,b,c,d=fixture();d['companies'][2]['both_documents_verified']=False
  self.assertIn('both_document_bytes_not_verified:Tryg',evaluate(a,b,c,d)['blockers'])
 def test_missing_automated_issuer_blocks(self):
  a,b,c,d=fixture();a['companies'][0]['end_to_end_automation_certified']=False
  self.assertIn('automation_not_certified:Fremtind',evaluate(a,b,c,d)['blockers'])
 def test_no_matching_independent_kpis_blocks(self):
  a,b,c,d=fixture();d['companies'][0]['cross_document_matches']=[]
  self.assertIn('no_independently_reconciled_kpis:Fremtind',evaluate(a,b,c,d)['blockers'])
 def test_conflicting_kpis_block(self):
  a,b,c,d=fixture();d['companies'][0]['conflicts']=[{'metric':'combined_ratio'}]
  self.assertIn('conflicting_report_and_presentation_metrics:Fremtind',evaluate(a,b,c,d)['blockers'])
 def test_missing_reconciled_metrics_blocks(self):
  a,b,c,d=fixture();d['companies'][0]['metric_extraction_status']='not_implemented'
  self.assertIn('both_document_metrics_not_reconciled:Fremtind',evaluate(a,b,c,d)['blockers'])
if __name__=='__main__':unittest.main()
