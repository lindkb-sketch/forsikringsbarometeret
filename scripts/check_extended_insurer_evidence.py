#!/usr/bin/env python3
"""Fail-closed integrity gate for the two newly onboarded insurers.

This does not certify nine-company financial parity. It prevents a partial
onboarding from silently becoming an unsupported financial claim.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = {'insurance_revenue', 'insurance_service_result',
            'combined_ratio', 'loss_ratio', 'expense_ratio'}
COMPANIES = {'Fremtind', 'Gjensidige', 'Tryg', 'Sampo', 'Frende',
             'Protector', 'Storebrand', 'KLP Skadeforsikring', 'Alm. Brand'}


def validate(extended, sources, calendar):
    errors = []
    registered = {item.get('company') for item in sources.get('sources', [])}
    errors += ['Missing official source registry: ' + name
               for name in sorted(COMPANIES - registered)]
    for name in ('KLP Skadeforsikring', 'Alm. Brand'):
        if name not in calendar:
            errors.append('Missing issuer calendar: ' + name)
    insurers = extended.get('insurers', {})
    alm = insurers.get('Alm. Brand', {})
    if alm.get('status') != 'verified_issuer_announcement':
        errors.append('Alm. Brand must retain its announcement-only evidence status')
    if alm.get('source_type') != 'official_issuer_interim_announcement':
        errors.append('Alm. Brand source type must not claim PDF verification')
    if not str(alm.get('source_url', '')).startswith('https://investorrelations.almbrand.dk/'):
        errors.append('Alm. Brand official source URL missing')
    if alm.get('year') != 2026 or alm.get('quarter') != 3:
        errors.append('Alm. Brand verified snapshot is not Q3 2026')
    metrics = alm.get('metrics', {})
    if set(metrics) != REQUIRED or any(
        isinstance(v, bool) or not isinstance(v, (int, float)) for v in metrics.values()
    ):
        errors.append('Alm. Brand verified metric set is incomplete or invalid')
    klp = insurers.get('KLP Skadeforsikring', {})
    if klp.get('status') != 'awaiting_source_verified_metrics' or klp.get('metrics') != {}:
        errors.append('KLP metrics require source verification before publication')
    return errors


def main():
    extended = json.loads((ROOT / 'data/extended_insurer_financials.json').read_text())
    sources = json.loads((ROOT / 'data/report_sources.json').read_text())
    calendar = json.loads((ROOT / 'data/calendar.json').read_text())
    errors = validate(extended, sources, calendar)
    print(json.dumps({'nine_issuer_registry_checked': True,
                      'nine_company_financial_parity_certified': False,
                      'klp_metrics_verified': False,
                      'alm_brand_pdf_page_import_verified': False,
                      'errors': errors}, ensure_ascii=False, indent=2))
    if errors:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
