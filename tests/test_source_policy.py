import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from source_policy import validate_source_policy
class SourcePolicyTest(unittest.TestCase):
 def test_reject_pdf_norway_without_named_geography(self):
  self.assertTrue(validate_source_policy([dict(company='Gjensidige',scope='norway',source_type='official_quarterly_report')]))
  self.assertTrue(validate_source_policy([dict(company='Tryg',scope='norway',source_type='official_quarterly_report')]))
 def test_accept_verified_excel_norway(self):
  row=dict(company='Gjensidige',scope='norway',source_type='official_investor_tables',
    source_url='https://issuer.example/figures.xlsx',source_sheet='Norway',
    source_cell='B12',source_document_url='https://issuer.example/report.pdf',source_sha256='a'*64)
  self.assertFalse(validate_source_policy([row]))
  self.assertTrue(validate_source_policy([{**row,'source_cell':None}]))
 def test_accept_explicit_tryg_norway_geography_pdf(self):
  row=dict(company='Tryg',scope='norway',source_type='official_quarterly_report',
    source_url='https://issuer.example/report.pdf',source_page=36,
    source_section='Quarterly outline - Geography / Norwegian general insurance',source_document_period='Q3 2026')
  self.assertFalse(validate_source_policy([row]))
  self.assertTrue(validate_source_policy([{**row,'source_section':'Group summary'}]))
class GjensidigeDerivedNorwayPolicy(unittest.TestCase):
 def test_derived_total_requires_both_official_segment_cells(self):
  base=dict(company='Gjensidige',year=2026,quarter=3,period_type='quarter',
    metric='insurance_revenue',source_type='official_investor_tables',
    source_url='https://issuer.example/figures.xlsx',
    source_document_url='https://issuer.example/report.pdf',source_sha256='a'*64)
  calculated=dict(base,scope='norway',status='calculated',
    calculation='sum_official_norway_segments')
  segments=[dict(base,scope='reported_segment',segment=name,status='reported',
    source_sheet=name,source_cell='B12') for name in ('Private Norway','Commercial Norway')]
  self.assertFalse(validate_source_policy([calculated]+segments))
  self.assertTrue(validate_source_policy([calculated,segments[0]]))
  self.assertTrue(validate_source_policy([calculated,{**segments[0], 'source_sha256':'b'*64},segments[1]]))

class StorebrandNorwayQ4Policy(unittest.TestCase):
 def test_global_audit_rejects_storebrand_norway_q4(self):
  from audit_financials import audit
  row=dict(company='Storebrand',year=2026,quarter=4,scope='norway',period_type='quarter',metric='insurance_revenue',value=100,source_url='https://storebrand.no/report.pdf',source_type='official_quarterly_report',source_page=1)
  self.assertTrue(any('Q4 must remain blank' in e for e in audit({'observations':[row]})['errors']))
if __name__=='__main__':unittest.main()
