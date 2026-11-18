#!/usr/bin/env python3
"""KLP isolated-quarter KPIs from issuer-reported isolated quarterly amounts.

All amounts must be independently extracted from official reports with matching
definitions, unit, currency, entity and fiscal year. Percentages are NEVER
subtracted. Solvency/ROE and other stock or non-additive KPIs are not derived.
"""
from decimal import Decimal, InvalidOperation

AMOUNTS = ('insurance_revenue', 'insurance_service_result',
           'claims_cost', 'operating_expenses')
RATIOS = ('loss_ratio', 'expense_ratio', 'combined_ratio')
BASIS = ('company', 'year', 'scope', 'currency', 'unit',
         'revenue_definition', 'claims_definition', 'expenses_definition')


def number(value):
    if isinstance(value, bool) or value is None:
        raise ValueError('Missing or invalid reported amount')
    try:
        n = Decimal(str(value))
    except (InvalidOperation, TypeError) as exc:
        raise ValueError('Invalid reported amount') from exc
    if not n.is_finite():
        raise ValueError('Non-finite reported amount')
    return n


def isolated(current, previous=None):
    """Return quarter flows and ratios, or raise instead of guessing."""
    quarter = current.get('quarter')
    if type(quarter) is not int or quarter not in (1, 2, 3, 4):
        raise ValueError('Invalid current quarter')
    if current.get('company') != 'KLP Skadeforsikring':
        raise ValueError('Wrong issuer')
    if not current.get('source_url') or not current.get('source_sha256') or not current.get('source_pages'):
        raise ValueError('Missing official source provenance')
    if previous is not None:
        raise ValueError('Quarterly amounts must come directly from the reported quarter column')
    if any(not current.get(field) for field in BASIS):
        raise ValueError('Incomplete reporting basis')
    if current.get('period_type') != 'quarter':
        raise ValueError('KLP source must be an isolated quarter column')
    current_values = current.get('amounts') or {}
    if set(current_values) != set(AMOUNTS):
        raise ValueError('Missing required quarterly numerators or denominators')
    amounts = {key: number(current_values[key]) for key in AMOUNTS}
    revenue = amounts['insurance_revenue']
    if revenue <= 0:
        raise ValueError('Isolated quarterly revenue must be positive')
    # Claims and expenses must be normalized to positive expense magnitudes
    # by the issuer-specific source parser before calling this function.
    if amounts['claims_cost'] < 0 or amounts['operating_expenses'] < 0:
        raise ValueError('Expected positive expense magnitude convention')
    loss = amounts['claims_cost'] / revenue * 100
    expense = amounts['operating_expenses'] / revenue * 100
    combined = (amounts['claims_cost'] + amounts['operating_expenses']) / revenue * 100
    return {
        'company': current['company'], 'year': current['year'], 'quarter': quarter,
        'scope': current['scope'], 'currency': current['currency'], 'unit': current['unit'],
        'period_type': 'quarter', 'status': 'calculated_from_reported_quarter',
        'amounts': {k: float(v) for k, v in amounts.items()},
        'ratios': {k: float(v) for k, v in zip(RATIOS, (loss, expense, combined))},
        'source_documents': [dict(source_url=r['source_url'], source_sha256=r['source_sha256'],
                                  source_pages=r['source_pages'])
                             for r in [current]],
        'calculation': 'Quarterly amounts taken directly from KLP isolated quarter column; ratios recomputed using issuer HIÅ definitions applied to quarterly numerators and denominators',
        'revenue_definition': current['revenue_definition'],
        'claims_definition': current['claims_definition'],
        'expenses_definition': current['expenses_definition'],
    }
