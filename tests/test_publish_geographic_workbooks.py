import unittest,sys,tempfile,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from publish_geographic_workbooks import run,prepare
class PublishingTests(unittest.TestCase):
 def test_empty_registry_builds_feed(self):
  with tempfile.TemporaryDirectory() as d:
   d=Path(d);reg=d/'registry.json';data=d/'observations.json';feed=d/'feed.json'
   reg.write_text(json.dumps({'workbooks':[]}));data.write_text(json.dumps({'observations':[]}))
   self.assertEqual(run(reg,data,feed),0)
   self.assertEqual(json.loads(feed.read_text())['observation_count'],0)
 def test_failed_download_does_not_change_data_or_feed(self):
  with tempfile.TemporaryDirectory() as d:
   d=Path(d);reg=d/'registry.json';data=d/'observations.json';feed=d/'feed.json'
   reg.write_text(json.dumps({'workbooks':[{'company':'Tryg','year':2026,'quarter':2,'approved':True,'workbook_url':'https://tryg.com/file.xlsx','report_pdf_url':'https://tryg.com/report.pdf'}]}))
   data.write_text(json.dumps({'observations':[]}));feed.write_text('previous feed')
   def fail(url):raise ValueError('download failed')
   with self.assertRaises(ValueError):run(reg,data,feed,fetcher=fail)
   self.assertEqual(feed.read_text(),'previous feed')
   self.assertEqual(json.loads(data.read_text())['observations'],[])
 def test_unapproved_source_is_not_downloaded(self):
  merged,feed,count=prepare({'workbooks':[{'approved':False,'company':'Tryg'}]},{'observations':[]},fetcher=lambda _:self.fail('download must not happen'))
  self.assertEqual(count,0)
