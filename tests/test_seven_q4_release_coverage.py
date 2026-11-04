"""Q4 2026 all-insurer scheduled release gate and missing-data scenarios."""
import datetime as dt
import sys
import unittest
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from check_seven_q4_release_coverage import assess,COMPANIES
TZ=ZoneInfo('Europe/Oslo')

def calendar():
    return {('Sampo / If' if name=='Sampo' else name):
            {'events':[{'period':'Q4 2026','date':'2027-01-01'}]}
            for name in COMPANIES}

def observations():
    rows=[]
    for company in COMPANIES:
        scopes=[('group',None)]
        if company=='Sampo':
            scopes += [('reported_segment','Private Nordic'),('reported_segment','Nordic Commercial')]
        metrics=['insurance_revenue','combined_ratio','loss_ratio','expense_ratio']
        if company in ('Fremtind','Gjensidige','Tryg','Sampo','Protector'):
            metrics+=['insurance_service_result']
        for scope,segment in scopes:
            for metric in metrics:
                rows.append(dict(company=company,year=2026,quarter=4,scope=scope,
                    segment=segment,period_type='quarter',status='reported',metric=metric,
                    source_type='official_quarterly_report',source_url='https://example.com/report.pdf',
                    source_page=1,source_sha256='a'*64))
    return rows

class Q4ReleaseTests(unittest.TestCase):
    def test_no_false_alarm_before_deadline(self):
        statuses=assess(calendar(),[],dt.datetime(2027,1,2,7,29,tzinfo=TZ))
        self.assertEqual({v['status'] for v in statuses.values()},{'not_due'})

    def test_all_seven_missing_issued_reports_fail(self):
        statuses=assess(calendar(),[],dt.datetime(2027,1,4,tzinfo=TZ))
        self.assertEqual(set(statuses),set(COMPANIES))
        self.assertEqual({v['status'] for v in statuses.values()},{'overdue'})

    def test_all_seven_verified_reports_pass(self):
        statuses=assess(calendar(),observations(),dt.datetime(2027,1,4,tzinfo=TZ))
        self.assertEqual({v['status'] for v in statuses.values()},{'complete'})

    def test_each_insurer_missing_one_metric_is_detected(self):
        all_rows=observations()
        for company in COMPANIES:
            with self.subTest(company=company):
                rows=[r for r in all_rows if not
                      (r['company']==company and r['scope']=='group' and r['metric']=='insurance_revenue')]
                statuses=assess(calendar(),rows,dt.datetime(2027,1,4,tzinfo=TZ))
                self.assertEqual(statuses[company]['status'],'overdue')
                self.assertEqual(sum(x['status']=='complete' for x in statuses.values()),6)

    def test_sampo_missing_one_segment_is_detected(self):
        rows=[r for r in observations() if not
              (r['company']=='Sampo' and r['segment']=='Private Nordic')]
        statuses=assess(calendar(),rows,dt.datetime(2027,1,4,tzinfo=TZ))
        self.assertEqual(statuses['Sampo']['status'],'overdue')
        self.assertEqual(statuses['Gjensidige']['status'],'complete')

    def test_unconfirmed_publication_date_is_not_reported_as_success(self):
        cal=calendar()
        cal['Frende']['events']=[]
        statuses=assess(cal,observations(),dt.datetime(2027,1,4,tzinfo=TZ))
        self.assertEqual(statuses['Frende']['status'],'unscheduled')
        self.assertNotEqual(statuses['Frende']['status'],'complete')

    def test_unverified_source_is_rejected(self):
        rows=observations()
        rows[0]['source_url']='http://unofficial.example/report.pdf'
        statuses=assess(calendar(),rows,dt.datetime(2027,1,4,tzinfo=TZ))
        self.assertEqual(statuses[rows[0]['company']]['status'],'overdue')

if __name__=='__main__':
    unittest.main()
