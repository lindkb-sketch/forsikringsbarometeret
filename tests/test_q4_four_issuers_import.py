"""Official Q4 report-format regressions across four previously missing issuers."""
import io,sys,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from import_fremtind_holding import extract
from protector_publish import discover_pdf
from storebrand_q4_group import find_group_q4,Q4_2025
from import_tryg import download_tryg_report

class IssuerQ4Tests(unittest.TestCase):
 def test_fremtind_holding_q4_has_four_explicit_columns(self):
  class Page:
   def __init__(self,text):self.text=text
   def extract_text(self):return self.text
  class PDF:
   pages=[
    Page('Kvartalsrapport Q4 2025 Fremtind Holding'),
    Page('Innhold'),
    Page('Resultatutvikling og nøkkeltall\\nMNOK Q4 2025\\n'
         'Inntekter fra forsikringstjenester 6 134 5 531 23 510 19 276 Vekst\\n'
         'Resultat fra forsikringstjenester 1 100 900 4 400 3 200\\n'
         'Skadeprosent, netto etter gjenforsikring (%) 63,2 % 65,0 % 58,8 % 60,5 %\\n'
         'Kostnadsprosent (%) 20,1 % 20,0 % 21,9 % 21,2 %\\n'
         'Combined ratio, netto etter gjenforsikring (%) 83,3 % 85,0 % 80,7 % 81,7 %'),
    Page('Noter')]
   def __enter__(self):return self
   def __exit__(self,*args):return False
  with patch('import_fremtind_holding.pdfplumber.open',return_value=PDF()):
   rows=extract(b'%PDF-fixture','https://cdn.sanity.io/files/q4.pdf')
  self.assertEqual(len(rows),20)
  selected={(r['year'],r['period_type'],r['metric']):r['value'] for r in rows}
  self.assertEqual(selected[(2025,'quarter','insurance_revenue')],6134)
  self.assertEqual(selected[(2025,'quarter','combined_ratio')],83.3)
  self.assertEqual(selected[(2025,'ytd','insurance_revenue')],23510)
  self.assertEqual(selected[(2024,'quarter','insurance_revenue')],5531)
 def test_protector_q4_official_release_fallback_still_pdf_verified(self):
  self.assertEqual(discover_pdf(2025,4,fetch=lambda *args:b'<html></html>'),
     'https://storage.mfn.se/1bc26b42-d94f-4e91-a87f-6c3cc87478d8/interim-report-q4-2025-prot.pdf')
 def test_storebrand_group_q4_can_be_discovered_without_norway_pdf(self):
  def lookup(year):return {'reports':[{'year':year,'quarter':4,'scope':'group',
      'entity':'Storebrand ASA','document_url':'https://www.storebrand.no/q4.pdf'}]}
  self.assertEqual(find_group_q4(2026,lookup),'https://www.storebrand.no/q4.pdf')
  self.assertEqual(find_group_q4(2025,lambda year:{'reports':[]}),Q4_2025)
  self.assertIsNone(find_group_q4(2026,lambda year:{'reports':[]}))
 def test_tryg_annual_download_does_not_use_interim_size_limit(self):
  class Response:
   def geturl(self):return 'https://tryg.com/en/annual.pdf'
   def read(self,n):return b'%PDF-'+b'x'*35_000_000
   def __enter__(self):return self
   def __exit__(self,*args):return False
  with patch('import_tryg.urllib.request.urlopen',return_value=Response()):
   data=download_tryg_report('https://tryg.com/en/annual.pdf',4)
  self.assertGreater(len(data),35_000_000)
if __name__=='__main__':unittest.main()
