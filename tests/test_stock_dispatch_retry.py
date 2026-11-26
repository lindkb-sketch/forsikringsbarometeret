import datetime as dt
import sys
import unittest
import urllib.error
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from check_stock_schedule import check
NOW=dt.datetime(2026,11,6,9,28,tzinfo=dt.timezone.utc)
class RetryTests(unittest.TestCase):
    def execute(self,accepted):
        calls=[]
        def fetch(url,token,data=None):
            calls.append((url,data))
            if data is None:
                return {"workflow_runs":[{"status":"queued"}] if accepted and len(calls)>1 else []}
            if len([c for c in calls if c[1] is not None])==1:
                raise urllib.error.HTTPError(url,500,"server error",None,None)
        result=check(NOW,fetch,"test","owner/repo",sleeper=lambda _:None)
        return result,calls
    def test_retry_after_500(self):
        result,calls=self.execute(False)
        self.assertEqual(result,"dispatched")
        self.assertEqual([x[1] is not None for x in calls],[False,True,False,True])
    def test_no_duplicate_after_ambiguous_500(self):
        result,calls=self.execute(True)
        self.assertEqual(result,"active")
        self.assertEqual([x[1] is not None for x in calls],[False,True,False])
