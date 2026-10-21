#!/usr/bin/env python3
"""Unified ingestion, validation, editorial, calendar and publishable data generation."""
import argparse,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def run(offline=False):
 steps=[] if offline else ['ingest_official_pdf.py','publish_geographic_workbooks.py']
 steps+=['enforce_source_policy.py','audit_financials.py','build_verified_feed.py','build_editorial.py','update.py']
 for name in steps:
  print('RUN',name,flush=True)
  subprocess.run([sys.executable,str(ROOT/'scripts'/name)],cwd=ROOT,check=True)
 print('Pipeline complete. Coverage is reported separately; it is not implied.')
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--offline',action='store_true');run(ap.parse_args().offline)
