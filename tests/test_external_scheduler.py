import datetime as dt
import sys
import unittest
import urllib.error
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from external_scheduler import finance_check,tick
NOW=dt.datetime(2026,11,26,10,0,tzinfo=dt.timezone.utc)

def row(minutes,status="completed",conclusion="success"):
    return {"head_branch":"main","created_at":(NOW-dt.timedelta(minutes=minutes)).isoformat(),
            "status":status,"conclusion":conclusion}

class ExternalSchedulerTests(unittest.TestCase):
    def check(self,rows,**kwargs):
        calls=[]
        def fetch(url,token,data=None):
            calls.append((url,data))
            if data is None:return {"workflow_runs":rows}
        out=finance_check(NOW,"test",fetch=fetch,sleeper=lambda _:None,**kwargs)
        return out,calls
    def test_finance_stale_success_triggers(self):
        out,calls=self.check([row(31)])
        self.assertEqual(out,"dispatched")
        self.assertEqual(calls[-1][1],{"ref":"main"})
    def test_recent_success_not_duplicated(self):
        out,calls=self.check([row(29)])
        self.assertEqual((out,len(calls)),("recent",1))
    def test_active_not_duplicated(self):
        out,calls=self.check([row(40,"in_progress",None)])
        self.assertEqual((out,len(calls)),("active",1))
    def test_stale_active_fails(self):
        with self.assertRaises(RuntimeError):self.check([row(61,"queued",None)])
    def test_failed_finance_retried_after_backoff(self):
        self.assertEqual(self.check([row(11,conclusion="failure")])[0],"dispatched")
        self.assertEqual(self.check([row(3,conclusion="failure")])[0],"recent")
    def test_dry_run_no_post(self):
        out,calls=self.check([],dry_run=True)
        self.assertEqual((out,len(calls)),("would_dispatch",1))
    def test_ambiguous_http_500_rechecks_history(self):
        calls=[]
        def fetch(url,token,data=None):
            calls.append(data)
            if data is not None:raise urllib.error.HTTPError(url,500,"error",None,None)
            return {"workflow_runs":[row(0,"queued",None)] if len(calls)>1 else []}
        self.assertEqual(finance_check(NOW,"test",fetch=fetch,sleeper=lambda _:None),"active")
        self.assertEqual(calls,[None,{"ref":"main"},None])
    def test_one_failure_does_not_prevent_other_recovery(self):
        def fetch(url,token,data=None):
            if "update.yml" in url:raise RuntimeError("mock finance error")
            if data is None:return {"workflow_runs":[]}
        report=tick(NOW,"test",fetch=fetch,sleeper=lambda _:None)
        self.assertEqual(report["finance"],"error:RuntimeError")
        self.assertEqual(report["stock"],"dispatched")
    def test_unknown_history_fail_closed(self):
        with self.assertRaises(ValueError):
            finance_check(NOW,"test",fetch=lambda *a:{})
    def test_other_branch_history_rejected(self):
        r=row(31);r["head_branch"]="feature"
        with self.assertRaises(ValueError):self.check([r])

if __name__=="__main__":
    unittest.main()
