#!/usr/bin/env python3
"""Legacy compatibility entrypoint: fail closed on CURRENT investor readiness.

Historical company presence alone is not sufficient. Independent human
financial signoff remains an additional release requirement, even on success.
"""
import sys
from investor_readiness import make


def validate(report):
    required = ('financial_quarter_complete', 'all_seven_automated',
                'definitions_comparable', 'market_data_fresh', 'investor_ready')
    if not all(report.get(key) is True for key in required):
        return False
    return report.get('status') == 'automated_checks_passed_review_required'


def main():
    data = make()
    print('INVESTOR RELEASE CHECK:', data['reference_quarter'], data['status'])
    if not validate(data):
        print('NOT READY: Missing or unverified source data / automation / market freshness.')
        return 2
    print('Automated evidence checks passed. Independent financial signoff is still required.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
