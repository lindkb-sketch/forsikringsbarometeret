#!/usr/bin/env python3
"""Track overdue quarterly publications independently for all nine insurers.

A missing date is UNSCHEDULED, not evidence of success. A scheduled released
quarter with incomplete verified metrics is OVERDUE. No data are modified.
"""
import datetime as dt
import json
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[1]
OSLO=ZoneInfo('Europe/Oslo')
COMPANIES=('Fremtind','Gjensidige','Tryg','Sampo','Frende','Protector','Storebrand','KLP Skadeforsikring','Alm. Brand')
METRICS={'insurance_revenue','combined_ratio','loss_ratio','expense_ratio'}
RESULT_REQUIRED={'Fremtind','Gjensidige','Tryg','Sampo','Protector','Alm. Brand'}
SEGMENTS=('Private Nordic','Nordic Commercial')


def assess(calendar,rows,now,year=2026,quarter=4,grace_hours=48):
    if now.tzinfo is None:
        raise ValueError('now must contain timezone')
    now=now.astimezone(OSLO)
    period=f'Q{quarter} {year}'
    result={}
    for company in COMPANIES:
        alias='Sampo / If' if company=='Sampo' else company
        dates=[event.get('date') for event in calendar.get(alias,{}).get('events',[])
               if event.get('period')==period and event.get('date')]
        if not dates:
            result[company]={'status':'unscheduled','period':period,'missing':[],
                             'reason':'No confirmed release date in issuer calendar'}
            continue
        release=dt.datetime.combine(dt.date.fromisoformat(min(dates)),dt.time(7,30),OSLO)
        deadline=release+dt.timedelta(hours=grace_hours)
        if now<deadline:
            result[company]={'status':'not_due','period':period,'missing':[],
                             'deadline':deadline.isoformat()}
            continue
        required=METRICS|({'insurance_service_result'} if company in RESULT_REQUIRED else set())
        def verified(scope='group',segment=None):
            return {r.get('metric') for r in rows if
                    r.get('company')==company and r.get('year')==year
                    and r.get('quarter')==quarter and r.get('period_type')=='quarter'
                    and r.get('scope')==scope and r.get('segment')==segment
                    and r.get('status')=='reported'
                    and r.get('source_type')=='official_quarterly_report'
                    and str(r.get('source_url','')).startswith('https://')
                    and r.get('source_page') and r.get('source_sha256')}
        missing=['group:'+metric for metric in sorted(required-verified())]
        if company=='Sampo':
            for segment in SEGMENTS:
                missing.extend(segment+':'+metric for metric in sorted(required-verified('reported_segment',segment)))
        result[company]={'status':'overdue' if missing else 'complete','period':period,
                         'missing':missing,'deadline':deadline.isoformat()}
    return result


def target_period(now):
    """Monitor Q4 2026 before release, then roll to each future reporting quarter.

    During Q1 the latest completed reporting period is previous-year Q4.
    From Q2 onward it is the quarter that ended in the prior calendar quarter.
    """
    local = now.astimezone(OSLO)
    if local.year == 2026:
        return 2026, 4
    if local.month <= 3:
        return local.year - 1, 4
    return local.year, (local.month - 1) // 3


def main():
    calendar=json.loads((ROOT/'data/calendar.json').read_text(encoding='utf-8'))
    feed=json.loads((ROOT/'data/verified_financial_feed.json').read_text(encoding='utf-8'))
    now=dt.datetime.now(OSLO)
    year,quarter=target_period(now)
    report=assess(calendar,feed['observations'],now,year=year,quarter=quarter)
    print(json.dumps(report,ensure_ascii=False,indent=2))
    missing={k:v for k,v in report.items() if v['status']=='overdue' and k not in ('KLP Skadeforsikring','Alm. Brand')}
    # Extended issuers use their own audited comparison dataset; see check_nine_release.py.
    if missing:
        raise SystemExit('Released quarterly reports not imported: '+', '.join(missing))


if __name__=='__main__':
    main()
