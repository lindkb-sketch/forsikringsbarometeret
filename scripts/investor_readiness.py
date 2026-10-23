#!/usr/bin/env python3
"""Independent, fail-closed investor-readiness manifest for the public control edition.

A successful deployment or old reported data NEVER prove current-quarter
completeness. This diagnostic does not modify source financial observations.
"""
import argparse
import datetime as dt
import json
import math
import re
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
COMPANIES = ('Fremtind', 'Gjensidige', 'Tryg', 'Sampo', 'Frende',
             'Protector', 'Storebrand')
REQUIRED = ('insurance_revenue', 'insurance_service_result',
            'combined_ratio', 'loss_ratio', 'expense_ratio')
LISTED = ('Gjensidige', 'Protector', 'Storebrand', 'Tryg', 'Sampo / If')
APM = re.compile(r'not ifrs insurance revenue|segment premiums|premiums f\.o\.a\.', re.I)


def json_file(root, filename, default):
    path = root / 'data' / filename
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else default


def period_label(period):
    return f'Q{period[1]} {period[0]}' if period else None


def provenance_valid(row):
    page = row.get('source_page')
    location = (type(page) is int and page > 0) or (
        bool(row.get('source_sheet')) and bool(row.get('source_cell')))
    value = row.get('value')
    return (str(row.get('source_url', '')).startswith('https://')
            and location and row.get('status') in ('reported', 'calculated')
            and type(value) in (int, float) and math.isfinite(value)
            and bool(row.get('unit')))


def parse_date(raw):
    if not isinstance(raw, str):
        return None
    try:
        return dt.date.fromisoformat(raw[:10])
    except ValueError:
        return None


def make(root=ROOT, today=None):
    root = Path(root)
    today = today or dt.datetime.now(ZoneInfo('Europe/Oslo')).date()
    feed = json_file(root, 'verified_financial_feed.json', {'observations': []})
    rows = feed.get('observations', [])
    if not isinstance(rows, list):
        raise ValueError('Financial observations must be an array')
    candidates = [r for r in rows if r.get('company') in COMPANIES
                  and r.get('scope') == 'group' and r.get('period_type') == 'quarter'
                  and type(r.get('year')) is int and type(r.get('quarter')) is int
                  and 1 <= r['quarter'] <= 4 and provenance_valid(r)]
    if not candidates:
        raise ValueError('No provenance-verified group-quarter data')
    current = max((r['year'], r['quarter']) for r in candidates)
    label = period_label(current)
    calendar = json_file(root, 'calendar.json', {})
    coverage = json_file(root, 'report_coverage.json', {'companies': []})
    certified = {x.get('company'): x.get('automatic_complete') is True
                 for x in coverage.get('companies', [])}
    report = []
    for company in COMPANIES:
        history = [r for r in candidates if r['company'] == company]
        recent = max(((r['year'], r['quarter']) for r in history), default=None)
        quarter_rows = [r for r in rows if r.get('company') == company
                        and r.get('scope') == 'group' and r.get('period_type') == 'quarter'
                        and (r.get('year'), r.get('quarter')) == current]
        valid_rows = [r for r in quarter_rows if provenance_valid(r)]
        valid_metrics = {r.get('metric') for r in valid_rows}
        missing = [metric for metric in REQUIRED if metric not in valid_metrics]
        invalid = sorted({r.get('metric') for r in quarter_rows
                          if r.get('metric') in REQUIRED and not provenance_valid(r)})
        company_calendar = calendar.get('Sampo / If' if company == 'Sampo' else company, {})
        event = next((e for e in company_calendar.get('events', [])
                      if e.get('period') == label), None)
        date = parse_date(event.get('date')) if event else None
        if not quarter_rows and date and date > today:
            status = 'awaiting_official_publication'
        elif not quarter_rows and date and date <= today:
            status = 'missing_after_calendar_date'
        elif not quarter_rows:
            status = 'report_date_unconfirmed'
        elif missing or invalid:
            status = 'incomplete_quarter'
        else:
            status = 'source_located_quarter'
        apm = any(APM.search(r.get('source_definition', '') or '') for r in valid_rows
                  if r.get('metric') == 'insurance_revenue')
        report.append({
            'company': company, 'quarter': label,
            'latest_source_located_quarter': period_label(recent),
            'status': status, 'source_located_metrics': sorted(valid_metrics.intersection(REQUIRED)),
            'missing_metrics': missing, 'invalid_metrics': invalid,
            'expected_report_date': date.isoformat() if date else None,
            'revenue_not_ifrs_comparable': apm,
            'end_to_end_automation_certified': certified.get(company, False),
        })
    stocks = json_file(root, 'stock_prices.json', {})
    quotes = []
    for company in LISTED:
        x = stocks.get('prices', {}).get(company, {})
        trade_date = parse_date(x.get('trading_date'))
        lag = (today - trade_date).days if trade_date else None
        state = ('missing' if trade_date is None or type(x.get('close')) not in (int, float)
                 else 'future_timestamp' if lag < 0
                 else 'stale_delayed_close' if lag > 5
                 else 'dated_delayed_close')
        quotes.append({'company': company, 'trading_date': trade_date.isoformat() if trade_date else None,
                       'calendar_days_old': lag, 'status': state})
    news = json_file(root, 'official_news.json', {})
    dates = [parse_date(x.get('published_at')) for x in news.get('items', [])
             if x.get('approved') is True]
    last_news = max((x for x in dates if x), default=None)
    news_age = (today - last_news).days if last_news else None
    recent_news = news_age is not None and 0 <= news_age <= 14
    financial_complete = all(not x['missing_metrics'] and not x['invalid_metrics']
                             and x['status'] == 'source_located_quarter' for x in report)
    automated = all(x['end_to_end_automation_certified'] for x in report)
    comparable = not any(x['revenue_not_ifrs_comparable'] for x in report)
    market_fresh = all(x['status'] == 'dated_delayed_close' for x in quotes) and recent_news
    passed = financial_complete and automated and comparable and market_fresh
    return {
        'schema_version': 1, 'as_of': today.isoformat(), 'reference_quarter': label,
        'investor_ready': passed, 'status': ('automated_checks_passed_review_required' if passed
                  else 'NOT_APPROVED_FOR_INVESTOR_USE'),
        'financial_quarter_complete': financial_complete,
        'all_seven_automated': automated, 'definitions_comparable': comparable,
        'market_data_fresh': market_fresh, 'companies': report,
        'stocks': quotes, 'news': {
            'latest_headline_date': last_news.isoformat() if last_news else None,
            'recent_attributed_headlines': recent_news},
        'limitations': [
            'Technical verification is not independent manual review of issuer report cells.',
            'This status must not convert an unreported quarter into estimated figures.',
            'Delayed stock closes must not be described as live market prices.',
            'Independent management/investor approval is required before distribution.'
        ]
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--strict', action='store_true',
                        help='Exit nonzero if NOT ready for investor distribution')
    args = parser.parse_args()
    result = make()
    target = ROOT / 'data/investor_readiness.json'
    target.write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print('INVESTOR READINESS', result['status'], result['reference_quarter'], flush=True)
    for item in result['companies']:
        print(item['company'], item['status'], 'missing=', ','.join(item['missing_metrics']) or '-',
              'automation=', item['end_to_end_automation_certified'], flush=True)
    if args.strict and not result['investor_ready']:
        raise SystemExit('Investor-grade release blocked: automated requirements incomplete')


if __name__ == '__main__':
    main()
