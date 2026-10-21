#!/usr/bin/env python3
"""Check complete isolated Storebrand workflow inputs before attempting live download."""
from pathlib import Path
import importlib.util
import sys
ROOT=Path(__file__).resolve().parents[1]
required=[
 '.github/workflows/storebrand-test.yml',
 'scripts/storebrand_preflight.py',
 'scripts/storebrand_sources.py',
 'scripts/storebrand_automation_check.py',
 'scripts/import_storebrand_reports.py',
 'scripts/audit_financials.py',
 'tests/test_storebrand_sources.py',
 'tests/test_storebrand_automation.py',
 'tests/test_storebrand_pdf_parser.py',
 'tests/test_storebrand_migration.py',
 'tests/fixtures/storebrand_forsikring_q3_2026.pdf',
 'tests/fixtures/storebrand_asa_q3_2026.pdf',
 'data/financial_observations.json',
 'requirements-reports.txt',
]
missing=[p for p in required if not (ROOT/p).is_file()]
for name in ('pdfplumber',):
 if importlib.util.find_spec(name) is None:missing.append('Python dependency: '+name)
if missing:
 print('STOREBRAND PREFLIGHT FAILED: missing required files/dependencies:',file=sys.stderr)
 for p in missing:print(' - '+p,file=sys.stderr)
 sys.exit(1)
print('STOREBRAND PREFLIGHT OK: all',len(required),'required project files exist')
