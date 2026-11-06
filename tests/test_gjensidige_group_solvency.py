"""Prove Group approved solvency comes from the correct issuer-year PDF."""
import importlib.util, json, sys, tempfile, unittest
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
spec=importlib.util.spec_from_file_location('group_solvency',ROOT/'scripts/import_group_solvency_pdf.py')
imp=importlib.util.module_from_spec(spec);spec.loader.exec_module(imp)

class Page:
 def __init__(self,text):self.text=text
 def extract_text(self):return self.text
class Pdf:
 def __init__(self,texts):self.pages=[Page(t) for t in texts]
 def __enter__(self):return self
 def __exit__(self,*args):return False

class GjensidigeGroupSolvency(unittest.TestCase):
 def parse(self,paragraphs,year=2026):
  cover=f'INTERIM REPORT 3rd quarter {year} Gjensidige Forsikring Group'
  with patch.object(imp.pdfplumber,'open',return_value=Pdf([cover]+paragraphs)):
   return imp.extract(b'%PDF-1.7\n','Gjensidige',year,3)
 def test_importer_includes_gjensidige(self):
  self.assertIn('Gjensidige',imp.COMPANIES)
 def test_approved_group_model_not_own_or_pension(self):
  text='Approved Partial Internal Model 1: 190 per cent. Own Partial Internal Model 2: 217 per cent. Pension solvency 138%'
  self.assertEqual(self.parse([text]),(2,190.0))
 def test_historical_approved_model_variants(self):
  for text in ('Approved Partial Internal Model:2 191 per cent',
               'Approved Partial Internal Model²: 191 per cent',
               'Approved Partial Internal Model: 191 per cent'):
   self.assertEqual(self.parse([text],2025),(2,191.0))
 def test_wrong_year_and_unapproved_model_rejected(self):
  with patch.object(imp.pdfplumber,'open',return_value=Pdf([
      'INTERIM REPORT 3rd quarter 2026 Gjensidige Forsikring Group',
      'Approved Partial Internal Model 190 per cent'])):
   with self.assertRaisesRegex(ValueError,'cover'):
    imp.extract(b'%PDF-1.7\n','Gjensidige',2025,3)
  with self.assertRaisesRegex(ValueError,'Missing or ambiguous'):
   self.parse(['Gjensidige Forsikring ASA solvency 205%. Own Partial Internal Model 217 per cent'])
 def test_conflicting_ratios_rejected(self):
  with self.assertRaisesRegex(ValueError,'ambiguous'):
   self.parse(['Approved Partial Internal Model 190 per cent','Approved Partial Internal Model 191 per cent'])
 def test_prior_year_uses_separate_official_source(self):
  source={'observations':[
   {'company':'Gjensidige','year':2026,'quarter':3,'scope':'group','metric':'insurance_revenue','period_type':'quarter','source_type':'official_quarterly_report','source_url':'https://mb.cision.com/new-q3-2026.pdf'},
   {'company':'Gjensidige','year':2025,'quarter':3,'scope':'group','metric':'insurance_revenue','period_type':'quarter','source_type':'official_quarterly_report','source_url':'https://mb.cision.com/new-q3-2026.pdf','source_document_period':'Q3 2026'}]}
  with tempfile.TemporaryDirectory() as directory:
   output=Path(directory)/'data.json';output.write_text(json.dumps(source))
   calls=[]
   def download(url):
    calls.append(url)
    return b'%PDF-2025' if '2025' in url else b'%PDF-2026'
   def extract(blob,company,year,quarter):
    self.assertIn(str(year).encode(),blob)
    return 5,191.0 if year==2025 else 190.0
   def write(path,data):Path(path).write_text(json.dumps(data))
   with patch.object(imp,'DATA',output),patch.object(imp,'COMPANIES',('Gjensidige',)),\
       patch.object(imp,'download',side_effect=download),\
       patch.object(imp,'extract',side_effect=extract),\
       patch.object(imp,'audit',return_value={'ok':True}),\
       patch.object(imp,'atomic_write',side_effect=write),\
       patch('gjensidige_publish.discover_quarter',return_value='https://www.gjensidige.se/Q3-2025.pdf'):
    imp.run()
   rows=[r for r in json.loads(output.read_text())['observations'] if r['metric']=='solvency_ratio']
   self.assertEqual({r['year']:r['value'] for r in rows},{2025:191.0,2026:190.0})
   self.assertEqual(len(set(calls)),2)

if __name__=='__main__':unittest.main()
