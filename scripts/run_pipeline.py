#!/usr/bin/env python3
"""Unified ingestion, validation, editorial, calendar and publishable data generation."""
import argparse,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def run(offline=False):
 steps=[] if offline else ['ingest_official_pdf.py']
 steps+=['enforce_source_policy.py','audit_financials.py','build_verified_feed.py','build_editorial.py','update.py']
 if not offline:
  print('RUN publish_geographic_workbooks.py (optional external workbook; preserve audited baseline on unavailable source)',flush=True)
  attempt=subprocess.run([sys.executable,str(ROOT/'scripts'/'publish_geographic_workbooks.py')],cwd=ROOT)
  if attempt.returncode:
   print('WARNING: Official geographical XLSX unavailable; no workbook values imported; existing audited records preserved.',flush=True)
 if not offline:
  print('RUN import_fremtind_holding.py (verified official issuer PDFs only)',flush=True)
  subprocess.run([sys.executable,str(ROOT/'scripts'/'import_fremtind_holding.py')],cwd=ROOT,check=True)
 for name in steps:
  print('RUN',name,flush=True)
  subprocess.run([sys.executable,str(ROOT/'scripts'/name)],cwd=ROOT,check=True)
 print('Pipeline complete. Coverage is reported separately; it is not implied.')
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--offline',action='store_true');run(ap.parse_args().offline)
