"""The GitHub-only backup must not dispatch duplicate or out-of-hours jobs."""
import datetime as dt,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import check_stock_schedule as watch
NOW=dt.datetime(2026,11,6,9,28,tzinfo=dt.timezone.utc)

class StockWatchdogTests(unittest.TestCase):
 def execute(self,runs,now=NOW):
  calls=[]
  def fetch(url,token,data=None):
   calls.append((url,data))
   return {'workflow_runs':runs} if data is None else None
  return watch.check(now,fetch=fetch,token='test',repo='owner/repo'),calls
 def test_dispatch_after_missing_schedule(self):
  outcome,calls=self.execute([{'status':'completed','created_at':'2026-11-05T21:12:23Z'}])
  self.assertEqual(outcome,'dispatched')
  self.assertEqual(calls[-1][1],{'ref':'main'})
  self.assertTrue(calls[-1][0].endswith('stock-prices.yml/dispatches'))
 def test_active_run_never_duplicated(self):
  outcome,calls=self.execute([{'status':'queued','created_at':'2026-11-06T08:00:00Z'}])
  self.assertEqual((outcome,len(calls)),('active',1))
 def test_recent_success_and_recent_failure_do_not_retrigger(self):
  for conclusion in ('success','failure'):
   outcome,calls=self.execute([{'status':'completed','conclusion':conclusion,'created_at':'2026-11-06T09:22:00Z'}])
   self.assertEqual((outcome,len(calls)),('recent',1))
 def test_closed_exchange_skips_all_network(self):
  outcome,calls=self.execute([],dt.datetime(2026,11,7,9,28,tzinfo=dt.timezone.utc))
  self.assertEqual((outcome,len(calls)),('closed',0))
 def test_unknown_api_response_fails_closed(self):
  with self.assertRaisesRegex(ValueError,'Invalid GitHub'):
   watch.check(NOW,fetch=lambda *a:{},token='test',repo='owner/repo')
 def test_watchdog_is_scheduled_in_existing_workflow(self):
  workflow=(ROOT/'.github/workflows/scheduled-import-watchdog.yml').read_text()
  self.assertIn('28,43,58 6-18 * * 1-5',workflow)
  self.assertIn('python scripts/check_stock_schedule.py',workflow)
  self.assertIn('actions: write',workflow)

if __name__=='__main__':unittest.main()
