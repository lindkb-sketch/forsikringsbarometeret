import datetime,json,subprocess,sys,tempfile,unittest
from pathlib import Path

SOURCE=Path(__file__).resolve().parents[1]/'scripts/check_sampo_release.py'

class SampoReleaseGateTests(unittest.TestCase):
 def run_gate(self, rows, date='2020-01-01'):
  with tempfile.TemporaryDirectory() as root:
   base=Path(root)
   (base/'scripts').mkdir()
   (base/'data').mkdir()
   (base/'scripts/check_sampo_release.py').write_text(SOURCE.read_text())
   (base/'data/calendar.json').write_text(json.dumps({'Sampo / If':{'events':[{'period':'Q3 2019','date':date}]}}))
   (base/'data/verified_financial_feed.json').write_text(json.dumps({'observations':rows}))
   return subprocess.run([sys.executable,str(base/'scripts/check_sampo_release.py')],capture_output=True,text=True)
 def test_missing_published_quarter_is_red(self):
  self.assertNotEqual(self.run_gate([]).returncode,0)
 def test_complete_official_quarter_is_green(self):
  rows=[]
  for scope,segment in [('group',None),('reported_segment','Private Nordic'),('reported_segment','Nordic Commercial')]:
   for metric in ['insurance_revenue','insurance_service_result','combined_ratio','loss_ratio','expense_ratio']:
    rows.append(dict(company='Sampo',year=2019,quarter=3,scope=scope,segment=segment,period_type='quarter',metric=metric,status='reported',source_sha256='abc',source_page=1,source_type='official_quarterly_report',source_url='https://www.sampo.com/report.pdf'))
  self.assertEqual(self.run_gate(rows).returncode,0)
 def test_unreleased_quarter_not_red(self):
  self.assertEqual(self.run_gate([],date='2099-11-04').returncode,0)

if __name__=='__main__':unittest.main()
