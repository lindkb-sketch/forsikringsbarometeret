#!/usr/bin/env python3
"""Unified ingestion, validation, editorial, calendar and publishable data generation."""
import argparse,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def run(offline=False):
 steps=[] if offline else ['ingest_official_pdf.py']
 # Import all issuer data before producing any feed or dashboard artifacts.
 for name in steps:
  print('RUN',name,flush=True)
  subprocess.run([sys.executable,str(ROOT/'scripts'/name)],cwd=ROOT,check=True)
 if not offline:
  print('RUN publish_geographic_workbooks.py (optional external workbook; preserve audited baseline on unavailable source)',flush=True)
  attempt=subprocess.run([sys.executable,str(ROOT/'scripts'/'publish_geographic_workbooks.py')],cwd=ROOT)
  if attempt.returncode:
   print('WARNING: Official geographical XLSX unavailable; no workbook values imported; existing audited records preserved.',flush=True)
 if not offline:
  print('RUN discover_tryg.py (official Tryg group PDF and Norway XLSX)',flush=True)
  subprocess.run([sys.executable,str(ROOT/'scripts'/'discover_tryg.py')],cwd=ROOT,check=True)
  print('RUN import_tryg.py (fail-closed group and Norway)',flush=True)
  subprocess.run([sys.executable,str(ROOT/'scripts'/'import_tryg.py')],cwd=ROOT,check=True)
 if not offline:
  print('RUN discover_frende_fremtind.py (refresh issuer-linked report URLs)',flush=True)
  discovery=subprocess.run([sys.executable,str(ROOT/'scripts'/'discover_frende_fremtind.py')],cwd=ROOT)
  if discovery.returncode:
   print('WARNING: Issuer discovery unavailable; importer uses last verified archive snapshot.',flush=True)
  print('RUN import_fremtind_holding.py (verified official issuer PDFs only)',flush=True)
  subprocess.run([sys.executable,str(ROOT/'scripts'/'import_fremtind_holding.py')],cwd=ROOT,check=True)
  print('RUN import_frende_holding.py (verified official issuer publisher tables only)',flush=True)
  subprocess.run([sys.executable,str(ROOT/'scripts'/'import_frende_holding.py')],cwd=ROOT,check=True)
 if not offline:
  print('RUN protector_publish.py (official KPI and PDF-verified prior-year comparisons)',flush=True)
  subprocess.run([sys.executable,str(ROOT/'scripts'/'protector_publish.py')],cwd=ROOT,check=True)
 if not offline:
  print('RUN import_gjensidige_latest.py (issuer-linked verified quarterly PDF)',flush=True)
  subprocess.run([sys.executable,str(ROOT/'scripts'/'import_gjensidige_latest.py')],cwd=ROOT,check=True)
 if not offline:
  print('RUN storebrand_2024_official_backfill.py (official 2025 Q3 Insurance comparator)',flush=True)
  attempt=subprocess.run([sys.executable,str(ROOT/'scripts'/'storebrand_2024_official_backfill.py')],cwd=ROOT)
  if attempt.returncode:
   print('::warning::Storebrand 2024 Insurance comparative could not be source-verified; preserving audited baseline',flush=True)
 for name in ['enforce_source_policy.py','audit_financials.py','build_verified_feed.py','refresh_report_commentary.py','build_editorial.py','build_strategic_market.py','update.py','verify_feed_coverage.py']:
  print('RUN',name,flush=True)
  subprocess.run([sys.executable,str(ROOT/'scripts'/name)],cwd=ROOT,check=True)
 print('Pipeline complete. Coverage is reported separately; it is not implied.')
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--offline',action='store_true');run(ap.parse_args().offline)
