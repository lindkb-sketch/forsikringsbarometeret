import sys,unittest,tempfile,zipfile,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from geographic_excel import parse
from audit_financials import audit
class GeographicTests(unittest.TestCase):
 def make(self,ambiguous=False):
  t=tempfile.TemporaryDirectory();p=Path(t.name)/'test.xlsx'
  rows=['<row r="1"><c r="B1" t="inlineStr"><is><t>Q2 2026</t></is></c></row>','<row r="2"><c r="A2" t="inlineStr"><is><t>Norway</t></is></c></row>','<row r="3"><c r="A3" t="inlineStr"><is><t>Insurance revenue</t></is></c><c r="B3"><v>123</v></c></row>','<row r="4"><c r="A4" t="inlineStr"><is><t>Sweden</t></is></c></row>']
  if ambiguous:rows.insert(1,'<row r="5"><c r="C5" t="inlineStr"><is><t>Q2 2026</t></is></c></row>')
  ns='http://schemas.openxmlformats.org/spreadsheetml/2006/main'
  with zipfile.ZipFile(p,'w') as z:
   z.writestr('xl/workbook.xml',f'<workbook xmlns="{ns}" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Geographical - Quarterly Outline" sheetId="1" r:id="rId1"/></sheets></workbook>')
   z.writestr('xl/_rels/workbook.xml.rels','<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Target="worksheets/sheet1.xml" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet"/></Relationships>')
   z.writestr('xl/worksheets/sheet1.xml',f'<worksheet xmlns="{ns}"><sheetData>{"".join(rows)}</sheetData></worksheet>')
  return t,p
 def test_norway_not_sweden(self):
  t,p=self.make()
  try:
   d=parse(p,'Tryg',2026,2,'https://tryg.com/tables.xlsx','https://tryg.com/report.pdf')
   self.assertEqual(d['observations'][0]['value'],123)
   self.assertEqual(d['observations'][0]['source_cell'],'B3')
   self.assertTrue(audit(d)['ok'])
  finally:t.cleanup()
 def test_ambiguous_header_blocks(self):
  t,p=self.make(True)
  try:
   with self.assertRaises(ValueError):parse(p,'Gjensidige',2026,2,'https://gjensidige.com/tables.xlsx','https://gjensidige.com/report.pdf')
  finally:t.cleanup()
 def test_group_workbook_not_allowed(self):
  row={'company':'Sampo','scope':'group','source_type':'official_investor_tables','source_url':'https://sampo.com/t.xlsx','source_document_url':'https://sampo.com/r.pdf','source_sheet':'x','source_cell':'B3','year':2026,'quarter':2,'period_type':'quarter','metric':'insurance_revenue','value':1,'source_page':1}
  self.assertFalse(audit({'observations':[row]})['ok'])
