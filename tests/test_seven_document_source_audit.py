import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from audit_seven_document_sources import audit, COMPANIES

def feed(source='official_quarterly_report'):
 return {'observations':[{'company':c,'year':2026,'quarter':3,'scope':'group',
  'period_type':'quarter','metric':m,'value':1.0,'status':'reported',
  'source_type':source,'source_url':'https://issuer.test/q3.pdf',
  'source_sha256':'a'*64,'source_page':1}
  for c in COMPANIES for m in ('insurance_revenue','insurance_service_result',
                              'combined_ratio','loss_ratio','expense_ratio')]}

class SourceGapTests(unittest.TestCase):
 def test_reports_do_not_certify_presentation(self):
  x=audit(feed(),{'candidates':[],'errors':[],'complete':True},{})
  self.assertTrue(x['all_seven_quarter_core_metrics_present'])
  self.assertFalse(x['all_seven_dual_document_verified'])
  self.assertTrue(all(r['quarter_presentation_sourced_observations']==0 for r in x['companies']))
 def test_candidate_is_not_verified_evidence(self):
  x=audit(feed(),{'candidates':[{'company':'Tryg','document_type':'results_presentation'}]}, {})
  tryg=next(r for r in x['companies'] if r['company']=='Tryg')
  self.assertEqual(tryg['unverified_presentation_candidates_all_periods'],1)
  self.assertFalse(tryg['both_documents_checked_for_this_period'])
 def test_missing_metric_is_not_declared_absent_from_issuer(self):
  f=feed();f['observations']=[r for r in f['observations'] if not
      (r['company']=='Sampo' and r['metric']=='expense_ratio')]
  x=audit(f,{'candidates':[]},{})
  sampo=next(r for r in x['companies'] if r['company']=='Sampo')
  self.assertFalse(sampo['required_metrics_present'])
  self.assertIn('expense_ratio',sampo['not_present_in_quarter_feed'])
  self.assertEqual(sampo['presentation_metric_gap_status'],'not_audited_against_official_presentation')
 def test_duplicate_and_missing_digest_flagged(self):
  f=feed();f['observations'][0]['source_sha256']=''
  f['observations'].append(dict(f['observations'][0]))
  x=audit(f,{'candidates':[]},{})
  first=x['companies'][0]
  self.assertIn('missing_pdf_sha256:insurance_revenue',first['provenance_errors'])
  self.assertIn('ambiguous_duplicate:insurance_revenue',first['provenance_errors'])
if __name__=='__main__':unittest.main()
