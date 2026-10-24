"""Watchdog should repair missed schedules without hiding the underlying delay."""
import io,json,os,runpy,tempfile,unittest,urllib.request
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
SCRIPT=ROOT/'scripts/check_scheduled_runs.py'
class Response:
 def __init__(self,data):self.data=data
 def __enter__(self):return self
 def __exit__(self,*args):return False
 def read(self):return json.dumps(self.data).encode()
class WatchdogRecoveryTests(unittest.TestCase):
 def execute(self,active):
  calls=[]
  def fake_open(req,timeout=25):
   url=req.full_url
   calls.append((url,req.get_method()))
   if 'event=schedule' in url:return Response({'workflow_runs':[{'event':'schedule','created_at':'2026-01-01T01:00:00Z'}]})
   if url.endswith('/dispatches'):return Response({})
   return Response({'workflow_runs':active})
  with tempfile.TemporaryDirectory() as d:
   summary=Path(d)/'summary.txt'
   with patch.object(urllib.request,'urlopen',side_effect=fake_open),patch.dict(os.environ,{'GITHUB_TOKEN':'test','GITHUB_STEP_SUMMARY':str(summary)}):
    runpy.run_path(str(SCRIPT),run_name='__main__')
   return calls,summary.read_text()
 def test_recovers_missing_schedule(self):
  calls,summary=self.execute([])
  self.assertTrue(any(url.endswith('/dispatches') and method=='POST' for url,method in calls))
  self.assertIn('Requested a new update.yml run',summary)
  self.assertIn('does not certify',summary)
 def test_does_not_duplicate_active_import(self):
  calls,summary=self.execute([{'status':'in_progress'}])
  self.assertFalse(any(url.endswith('/dispatches') for url,method in calls))
  self.assertIn('already running',summary)
if __name__=='__main__':unittest.main()
