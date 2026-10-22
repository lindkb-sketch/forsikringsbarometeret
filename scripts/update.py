#!/usr/bin/env python3
"""Build a conservative report calendar from approved dates and locks."""
import datetime as dt
import json
import pathlib
import re
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'

def load(name):
    return json.loads((DATA / name).read_text(encoding='utf-8'))

def is_locked(locks, name, period):
    x = locks.get(name, {}).get(period, {})
    return x.get('reviewed') is True and bool(x.get('locked_at')) and bool(x.get('source_url'))

def validate_events(events):
    seen = set()
    for e in events:
        assert re.fullmatch(r'Q[1-4] 20\d{2}', e['period'])
        dt.date.fromisoformat(e['date'])
        assert e['period'] not in seen, 'Duplicate quarter'
        seen.add(e['period'])

def build(config, locks):
    result = {'updated_at': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'), 'companies': {}}
    for name, entry in config.items():
        events = sorted(entry['events'], key=lambda x: x['date'])
        validate_events(events)
        # Prefer the next upcoming issuer-published date. An old, unlocked Q3\n        # event must not hide a known Q4 publication date after Q3 passes.\n        today = dt.date.today().isoformat()\n        upcoming = [e for e in events if e['date'] >= today and not is_locked(locks, name, e['period'])]\n        next_event = upcoming[0] if upcoming else None
        result['companies'][name] = {
            'next_event': {**next_event, 'source_url': entry['calendar_url']} if next_event else None,
            'locked_periods': sorted(p for p in locks.get(name, {}) if is_locked(locks, name, p)),
            'calendar_source': entry['calendar_url'],
        }
    return result

def main():
    config, locks = load('calendar.json'), load('locks.json')
    result = build(config, locks)
    previous = load('live.json') if (DATA / 'live.json').exists() else {}
    if previous.get('companies') == result['companies']:
        print('No calendar changes'); return
    (DATA / 'live.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('Calendar updated')

if __name__ == '__main__':
    main()
