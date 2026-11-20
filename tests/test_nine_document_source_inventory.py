import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from build_nine_document_source_inventory import inventory

def row(company,url,kind='official_quarterly_report'):
 return {'company':company,'year':2026,'quarter':3,'scope':'group',
         'period_type':'quarter','source_type':kind,'source_url':url,
         'metric':'combined_ratio','value':89}

class NineSourceInventoryTests(unittest.TestCase):
 def test_pdf_provenance_is_not_download_verification(self):
  result=inventory({'observations':[row('Tryg','https://tryg.com/q3-2026.pdf')]},
                   {'insurers':{}},{'candidates':[]})
  item=next(x for x in result['companies'] if x['company']=='Tryg')
  self.assertTrue(item['report_provenance_present'])
  self.assertFalse(item['both_document_bytes_verified'])
  self.assertFalse(item['documents'][0]['download_verified_now'])
 def test_html_source_not_misrepresented_as_pdf(self):
  result=inventory({'observations':[row('Frende','https://frende.wrep.it/q3-2026/sec/6')]},
                   {'insurers':{}},{'candidates':[]})
  doc=next(x for x in result['companies'] if x['company']=='Frende')['documents'][0]
  self.assertFalse(doc['is_pdf'])
  self.assertFalse(doc['approved_pdf_url'])
 def test_candidate_does_not_count_as_presentation_evidence(self):
  c={'company':'Tryg','document_type':'results_presentation',
     'document_url':'https://tryg.com/q3-2026-presentation.pdf'}
  result=inventory({'observations':[]},{'insurers':{}},{'candidates':[c]})
  item=next(x for x in result['companies'] if x['company']=='Tryg')
  self.assertFalse(item['presentation_provenance_present'])
 def test_alm_presentation_provenance_preserved(self):
  ext={'insurers':{'Alm. Brand':{'year':2026,'quarter':3,
        'presentation_evidence':{'source_type':'official_results_presentation',
         'source_url':'https://s29.q4cdn.com/q3-2026.pdf','metrics':{'solvency_ratio':238}}}}}
  result=inventory({'observations':[]},ext,{'candidates':[]})
  item=next(x for x in result['companies'] if x['company']=='Alm. Brand')
  self.assertTrue(item['presentation_provenance_present'])
  self.assertFalse(item['both_document_bytes_verified'])
  self.assertFalse(result['all_nine_dual_document_verified'])
if __name__=='__main__':unittest.main()
