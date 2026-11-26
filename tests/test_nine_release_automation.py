import datetime as dt
import sys
import unittest
from pathlib import Path
from zoneinfo import ZoneInfo
from copy import deepcopy

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from check_nine_release import assess,COMPANIES,METRICS,NOT_REPORTED
from nine_import_receipt import build

TZ=ZoneInfo("Europe/Oslo")
def comparison():
    rows=[]
    for company in COMPANIES:
        values={m: None if m in NOT_REPORTED.get(company,set()) else 1.0 for m in METRICS}
        rows.append(dict(company=company,period="Q3 2026",status="verified_quarterly_feed",
                         source_url="https://example.com/"+company,metrics=values,ytd_metrics=values.copy()))
    return {"count":9,"companies":rows}

def calendar():
    return {("Sampo / If" if c=="Sampo" else c):{"events":[{"period":"Q4 2026","date":"2027-02-01"}]} for c in COMPANIES}

class NineReleaseTests(unittest.TestCase):
    def test_no_false_alarm_before_release(self):
        r=assess(comparison(),calendar(),dt.datetime(2027,1,20,tzinfo=TZ))
        self.assertEqual({x["status"] for x in r.values()},{"awaiting_release_or_import_grace"})
    def test_all_nine_overdue(self):
        r=assess(comparison(),calendar(),dt.datetime(2027,2,4,tzinfo=TZ))
        self.assertEqual({x["status"] for x in r.values()},{"overdue"})
    def test_staggered_actual_imports_extended_issuers(self):
        for company in COMPANIES:
            with self.subTest(company=company):
                data=comparison()
                next(x for x in data["companies"] if x["company"]==company)["period"]="Q4 2026"
                r=assess(data,calendar(),dt.datetime(2027,2,4,tzinfo=TZ))
                self.assertEqual(r[company]["status"],"next_quarter_not_ended")
                self.assertEqual(sum(x["status"]=="overdue" for x in r.values()),8)
    def test_every_required_metric_and_both_views(self):
        for c in COMPANIES:
            for view in ("metrics","ytd_metrics"):
                data=comparison()
                row=next(x for x in data["companies"] if x["company"]==c)
                row[view]["insurance_revenue"]=None
                r=assess(data,calendar(),dt.datetime(2026,11,26,tzinfo=TZ))
                self.assertEqual(r[c]["status"],"incomplete")
    def test_missing_calendar_never_certified(self):
        cal=calendar();cal["KLP Skadeforsikring"]["events"]=[]
        r=assess(comparison(),cal,dt.datetime(2027,2,4,tzinfo=TZ))
        self.assertEqual(r["KLP Skadeforsikring"]["status"],"release_date_unconfirmed")
    def test_receipts_only_advance_on_schedule_and_exact_public(self):
        before=comparison();after=deepcopy(before)
        after["companies"][-1]["period"]="Q4 2026"
        for event in ("schedule","workflow_dispatch"):
            receipt=build(before,after,after,event,"123","a"*40)
            self.assertEqual(sum(x["scheduled_advance_observed"] for x in receipt["companies"]),int(event=="schedule"))
        with self.assertRaisesRegex(ValueError,"Public"):
            build(before,after,before,"schedule","123","a"*40)
    def test_receipts_never_certify_no_change(self):
        data=comparison()
        self.assertFalse(any(x["scheduled_advance_observed"] for x in build(data,data,data,"schedule","123","a"*40)["companies"]))

if __name__=="__main__":
    unittest.main()
