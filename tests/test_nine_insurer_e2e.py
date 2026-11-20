import copy
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from check_nine_insurer_e2e import check,SEVEN,NINE,CORE,METRICS

def fixtures():
 rows=[]
 comparison=[]
 for name in SEVEN:
  metrics={k:float(i+10) for i,k in enumerate(CORE)}
  for k,v in metrics.items():
   rows.append({'company':name,'scope':'group','period_type':'quarter','status':'reported',
                'year':2026,'quarter':3,'metric':k,'value':v,
                'source_url':'https://issuer.test/q3.pdf','source_page':2,'source_sha256':'a'*64})
  comparison.append({'company':name,'period':'Q3 2026','currency':'NOK',
                     'status':'verified_quarterly_feed','metrics':metrics})
 ext={}
 for name,status in [('KLP Skadeforsikring','verified_official_pdf_reconciled'),
                     ('Alm. Brand','verified_official_presentation_reconciled')]:
  metrics={k:float(i+10) for i,k in enumerate(CORE)}
  if name=='Alm. Brand':metrics['solvency_ratio']=238
  source={'status':status,'year':2026,'quarter':3,'currency':'NOK' if name.startswith('KLP') else 'DKK',
          'source_url':'https://issuer.test/q3.pdf','metrics':metrics}
  if name.startswith('KLP'):source['periods']=[{}, {}, {}]
  else:source['presentation_evidence']={'source_page':19,'source_sha256':'b'*64,'metrics':{'solvency_ratio':238}}
  ext[name]=source
  comparison.append({'company':name,'period':'Q3 2026','currency':source['currency'],
                     'source_url':source['source_url'],'status':status,
                     'metrics':{k:metrics.get(k) for k in METRICS}})
 gaps={'all_seven_dual_document_verified':False,'companies':[{'company':c} for c in SEVEN]}
 return {'observations':rows},{'insurers':ext},{'companies':comparison,'count':9,'investor_use_approved':False},gaps

class NineInsurerE2ETests(unittest.TestCase):
 def test_valid_source_parity(self):
  self.assertEqual(check(*fixtures()),[])
 def test_changed_published_metric_fails(self):
  a,b,c,d=fixtures()
  c['companies'][0]['metrics']['insurance_revenue']=999
  self.assertTrue(any('value mismatch' in x for x in check(a,b,c,d)))
 def test_missing_sha_fails(self):
  a,b,c,d=fixtures();a['observations'][0]['source_sha256']=''
  self.assertTrue(any('invalid source digest' in x for x in check(a,b,c,d)))
 def test_unverified_alm_solvency_fails(self):
  a,b,c,d=fixtures();b['insurers']['Alm. Brand']['presentation_evidence']['source_page']=0
  self.assertTrue(any('presentation provenance' in x for x in check(a,b,c,d)))
 def test_false_dual_document_certification_fails(self):
  a,b,c,d=fixtures();d['all_seven_dual_document_verified']=True
  self.assertTrue(any('falsely certify' in x for x in check(a,b,c,d)))
 def test_missing_insurer_fails(self):
  a,b,c,d=fixtures();c['companies'].pop()
  self.assertTrue(any('nine companies' in x for x in check(a,b,c,d)))
if __name__=='__main__':unittest.main()
