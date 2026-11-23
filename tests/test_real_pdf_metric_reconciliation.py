import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from reconcile_nine_pdf_metrics import extract_unambiguous,parse_number,source_documents,reconcile_extracted,discover_presentation_metrics

class RealPdfMetricReconciliationTests(unittest.TestCase):
 def test_single_labelled_value_is_extracted(self):
  self.assertEqual(extract_unambiguous(['Solvency ratio: 238%'],'solvency_ratio'),238)
 def test_multiple_period_columns_are_ambiguous(self):
  self.assertIsNone(extract_unambiguous(['Solvency ratio 238% 230%'],'solvency_ratio'))
 def test_prior_expected_value_never_disambiguates(self):
  self.assertIsNone(extract_unambiguous(['Solvency ratio 238% 230%'],'solvency_ratio',expected=238))
 def test_norwegian_decimal(self):
  self.assertEqual(extract_unambiguous(['Kostnadsprosent: 20,5 %'],'expense_ratio'),20.5)
 def test_presentation_explicit_q3_table_extracts_only_correct_column(self):
  page='Results Q3 2026 GROUP\nMetric    Q3 2026    Q3 2025\nCombined ratio    76.8    80.1'
  evidence=discover_presentation_metrics([(7,page)],2026,3)
  self.assertEqual(len(evidence),1)
  self.assertEqual(evidence[0]['metric'],'combined_ratio')
  self.assertEqual(evidence[0]['value'],76.8)
  self.assertEqual(evidence[0]['source_page'],7)
  self.assertEqual(evidence[0]['extraction_method'],'explicit_quarter_table_column_on_group_page')
 def test_presentation_ambiguous_or_ytd_table_not_extracted(self):
  pages=[(2,'Results Q3 2026 GROUP\nMetric    Q3 2026    Q3 2026\nCombined ratio    76.8    80.1'),
         (3,'Results Q3 2026 GROUP\nMetric    YTD 2026    YTD 2025\nCombined ratio    76.8    80.1'),
         (4,'Results Q3 2026 NORWAY ONLY GROUP\nMetric    Q3 2026    Q3 2025\nCombined ratio    76.8    80.1')]
  self.assertEqual(discover_presentation_metrics(pages,2026,3),[])
 def test_rejects_glued_pdf_chart_values(self):
  self.assertIsNone(extract_unambiguous(['Solvency ratio 203199188184183%'],'solvency_ratio'))
  self.assertIsNone(extract_unambiguous(['Insurance revenue 168141481439584'],'insurance_revenue'))
 def test_rejects_chart_prose_and_unmarked_ratio(self):
  self.assertIsNone(extract_unambiguous(['Strong solvency ratio 203%'],'solvency_ratio'))
  self.assertIsNone(extract_unambiguous(['Combined ratio 2.15'],'combined_ratio'))
 def test_source_hash_and_page_preserved(self):
  f={'observations':[{'company':'Fremtind','year':2026,'quarter':3,
      'source_type':'official_quarterly_report',
      'source_url':'https://cdn.sanity.io/report.pdf','source_sha256':'a'*64,
      'source_page':3,'metric':'combined_ratio','value':73}]}
  d=source_documents(f,{'insurers':{}},{'candidates':[]},2026,3)
  record=next(iter(d['Fremtind'].values()))
  self.assertEqual(record['expected_hashes'],{'a'*64})
  self.assertEqual(record['observations'][0]['source_page'],3)
 def test_matching_independently_extracted_values(self):
  records=[{'metric':'solvency_ratio','scope':'group','period_type':'quarter',
            'document_type':kind,'value':value,'status':'extracted_unambiguous'}
           for kind,value in [('quarterly_report',238),('results_presentation',238)]]
  self.assertEqual(reconcile_extracted(records)[0]['status'],'match')
  records[1]['value']=231
  self.assertEqual(reconcile_extracted(records)[0]['status'],'conflict')
 def test_unverified_presentation_does_not_count_as_match(self):
  records=[{'metric':'solvency_ratio','scope':'group','period_type':'quarter',
            'document_type':'results_presentation','value':238,'status':'ambiguous_or_not_found'}]
  self.assertEqual(reconcile_extracted(records),[])
if __name__=='__main__':unittest.main()
