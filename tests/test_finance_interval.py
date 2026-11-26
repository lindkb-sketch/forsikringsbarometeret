import datetime as dt
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from finance_interval import arm,wait_next

NOW=dt.datetime(2026,11,26,11,0,tzinfo=dt.timezone.utc)
class TimerTests(unittest.TestCase):
    def test_arm_dispatches_only_timer(self):
        calls=[]
        arm('123','secret',fetch=lambda *a:calls.append(a))
        self.assertEqual(calls[0][2],{'event_type':'finance_next_check','client_payload':{'source_run_id':'123'}})
    def test_wait_and_dispatch_missing_run(self):
        current=[NOW]
        calls=[]
        source={'id':123,'head_branch':'main','path':'.github/workflows/update.yml',
                'created_at':(NOW-dt.timedelta(minutes=10)).isoformat(),'status':'completed','conclusion':'success'}
        def fetch(url,token,data=None):
            calls.append((url,data))
            if url.endswith('/123'):return source
            if data is None:return {'workflow_runs':[source]}
        def sleep(seconds):current[0]+=dt.timedelta(seconds=seconds)
        self.assertEqual(wait_next('123','secret',fetch=fetch,clock=lambda:current[0],sleep=sleep),'dispatched')
        self.assertEqual(calls[-1][1],{'ref':'main'})
        self.assertGreaterEqual(current[0],NOW+dt.timedelta(minutes=20))
    def test_wrong_source_is_rejected(self):
        with self.assertRaisesRegex(ValueError,'not a main finance workflow'):
            wait_next('123','secret',fetch=lambda *a:{'id':123,'head_branch':'other'},clock=lambda:NOW)
    def test_newer_active_run_not_duplicated(self):
        source={'id':123,'head_branch':'main','path':'.github/workflows/update.yml',
                'created_at':(NOW-dt.timedelta(minutes=31)).isoformat(),'status':'completed','conclusion':'success'}
        active={'head_branch':'main','created_at':NOW.isoformat(),'status':'in_progress'}
        def fetch(url,token,data=None):
            if data is not None:self.fail('Unexpected duplicate dispatch')
            if url.endswith('/123'):return source
            return {'workflow_runs':[source,active]}
        self.assertEqual(wait_next('123','secret',fetch=fetch,clock=lambda:NOW,sleep=lambda _:None),'active')
if __name__=='__main__':unittest.main()
