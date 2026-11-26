#!/usr/bin/env python3
"""Fail-closed release/KPI gate for the nine actual published issuer datasets.

A company may legitimately remain in the previous quarter while its next report
is not released. A dated release becomes due after the existing 48-hour
grace period. Undated releases are visible as unconfirmed, never as verified.
This gate does not manufacture data or certify future unattended imports.
"""
import datetime as dt
import json
import math
import re
from pathlib import Path
from zoneinfo import ZoneInfo
from quarterly_kpi_completeness import COMPANIES, METRICS, NOT_REPORTED

ROOT = Path(__file__).resolve().parents[1]
OSLO = ZoneInfo("Europe/Oslo")
VERIFIED = {"verified_quarterly_feed", "verified_official_pdf_reconciled",
            "verified_official_presentation_reconciled"}
BASELINE = (2026, 3)

def period(value):
    match = re.fullmatch(r"Q([1-4]) (20\d{2})", str(value))
    if not match:
        raise ValueError("Invalid reporting period: " + str(value))
    return int(match[2]), int(match[1])

def next_period(p):
    return (p[0] + 1, 1) if p[1] == 4 else (p[0], p[1] + 1)

def label(p):
    return f"Q{p[1]} {p[0]}"

def last_completed(today):
    q = (today.month - 1) // 3 + 1
    return (today.year - 1, 4) if q == 1 else (today.year, q - 1)

def finite(value):
    return type(value) in (float, int) and math.isfinite(value)

def assess(comparison, calendar, now, grace_hours=48):
    if now.tzinfo is None:
        raise ValueError("now must be timezone aware")
    now = now.astimezone(OSLO)
    rows = comparison.get("companies", [])
    by_company = {r["company"]: r for r in rows}
    if len(rows) != 9 or set(by_company) != set(COMPANIES):
        raise ValueError("Expected exactly nine distinct comparison issuers")
    result = {}
    for company in COMPANIES:
        row = by_company[company]
        current = period(row["period"])
        missing = []
        for view in ("metrics", "ytd_metrics"):
            values = row.get(view) or {}
            for metric in METRICS:
                value = values.get(metric)
                if value is None and metric in NOT_REPORTED.get(company, set()):
                    continue
                if not finite(value):
                    missing.append(view + ":" + metric)
        if row.get("status") not in VERIFIED or not str(row.get("source_url", "")).startswith("https://"):
            missing.append("verified_official_source")
        if current < BASELINE or current > last_completed(now.date()):
            missing.append("invalid_current_period")
        alias = "Sampo / If" if company == "Sampo" else company
        events = {}
        for event in calendar.get(alias, {}).get("events", []):
            if not event.get("date"):
                continue
            try:
                p = period(event.get("period"))
                release = dt.datetime.combine(dt.date.fromisoformat(event["date"]), dt.time(7,30), OSLO)
            except (ValueError, TypeError):
                continue
            # Do not accept a date for a quarter before it has ended.
            if p <= last_completed(release.date()):
                events[p] = min(release, events.get(p, release))
        overdue = sorted(p for p, release in events.items()
                         if p > current and p <= last_completed(now.date())
                         and now >= release + dt.timedelta(hours=grace_hours))
        upcoming = next_period(current)
        deadline = events.get(upcoming)
        if missing:
            status = "incomplete"
        elif overdue:
            status = "overdue"
        elif upcoming > last_completed(now.date()):
            status = "next_quarter_not_ended"
        elif deadline:
            status = "awaiting_release_or_import_grace"
        else:
            status = "release_date_unconfirmed"
        result[company] = {
            "status": status, "latest_verified_period": label(current),
            "missing": missing, "overdue_periods": [label(p) for p in overdue],
            "next_period": label(upcoming),
            "next_known_release": deadline.date().isoformat() if deadline else None,
        }
    return result

def main():
    comparison = json.loads((ROOT/"data/nine_insurer_comparison.json").read_text())
    calendar = json.loads((ROOT/"data/calendar.json").read_text())
    report = assess(comparison, calendar, dt.datetime.now(OSLO))
    print(json.dumps(report, ensure_ascii=False, indent=2))
    for company, item in report.items():
        if item["status"] == "release_date_unconfirmed":
            print(f"::warning::{company}: {item['next_period']} has ended; release date unconfirmed; continue issuer archive discovery")
    failed = [c for c,r in report.items() if r["status"] in ("incomplete","overdue")]
    if failed:
        raise SystemExit("Nine-insurer release/KPI gate failed: " + ", ".join(failed))

if __name__ == "__main__":
    main()
