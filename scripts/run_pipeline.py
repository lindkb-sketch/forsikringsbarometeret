#!/usr/bin/env python3
"""Unified ingestion, validation, editorial, calendar and publishable data generation."""
import argparse,subprocess,sys
from datetime import date
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def run(offline=False):
 steps=[] if offline else ['ingest_official_pdf.py']
 # Import all issuer data before producing any feed or dashboard artifacts.
 for name in steps:
  print('RUN',name,flush=True)
  subprocess.run([sys.executable,str(ROOT/'scripts'/name)],cwd=ROOT,check=True)
 if not offline:
  print('RUN discover_tryg.py (official Tryg PDF reports only)',flush=True)
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
  print('RUN protector_2024_official_backfill.py (official historical quarter and HIÅ)',flush=True)
  attempt=subprocess.run([sys.executable,str(ROOT/'scripts'/'protector_2024_official_backfill.py')],cwd=ROOT)
  if attempt.returncode:
   print('::warning::Protector historical source unavailable or invalid; preserving verified baseline',flush=True)
 if not offline:
  # Sampo and Storebrand must be part of the scheduled ingestion path, not
  # only diagnostic workflows. Failures keep previously audited observations.
  # The profitability coverage report marks missing quarters explicitly.
  today=date.today()
  latest_completed=today.year*4+(today.month-1)//3-1
  latest_year,latest_quarter=divmod(latest_completed,4)
  latest_quarter+=1
  for filename in ['sampo_publish.py', 'storebrand_q4_group.py', 'storebrand_publish_q3.py']:
   print('RUN',filename,'(official report import; preserves audited baseline if unavailable)',flush=True)
   command=[sys.executable,str(ROOT/'scripts'/filename)]
   if filename=='storebrand_publish_q3.py' and (latest_year,latest_quarter)>=(2026,3):
    command+=['--year',str(latest_year),'--quarter',str(latest_quarter)]
   attempt=subprocess.run(command,cwd=ROOT)
   if attempt.returncode:
    print('::warning::'+filename+' blocked by missing/changed official report; no invented figures published',flush=True)
 if not offline:
  print('RUN import_gjensidige_latest.py (issuer-linked verified quarterly PDF)',flush=True)
  subprocess.run([sys.executable,str(ROOT/'scripts'/'import_gjensidige_latest.py')],cwd=ROOT,check=True)
  print('RUN import_gjensidige_excel_auto.py (discover official issuer Excel and verify Norway PM/BM)',flush=True)
  attempt=subprocess.run([sys.executable,str(ROOT/'scripts'/'import_gjensidige_excel_auto.py')],cwd=ROOT)
  if attempt.returncode:
   print('::warning::Gjensidige official Excel discovery/import failed; strict coverage gate will block missing published figures',flush=True)
  print('RUN import_gjensidige_pdf_norway.py (verified Norway PM/BM from official quarterly PDF)',flush=True)
  subprocess.run([sys.executable,str(ROOT/'scripts'/'import_gjensidige_pdf_norway.py')],cwd=ROOT,check=True)
  print('RUN import_gjensidige_segments.py (official Norway PM/BM; independently reconciled)',flush=True)
  subprocess.run([sys.executable,str(ROOT/'scripts'/'import_gjensidige_segments.py')],cwd=ROOT,check=True)
 if not offline:
  print('RUN storebrand_2024_official_backfill.py (official 2025 Q3 Insurance comparator)',flush=True)
  attempt=subprocess.run([sys.executable,str(ROOT/'scripts'/'storebrand_2024_official_backfill.py')],cwd=ROOT)
  if attempt.returncode:
   print('::warning::Storebrand 2024 Insurance comparative could not be source-verified; preserving audited baseline',flush=True)
 for name in ['enforce_source_policy.py','audit_financials.py','build_verified_feed.py','refresh_report_commentary.py','build_editorial.py','build_strategic_market.py','update.py','verify_feed_coverage.py','verify_expected_published_quarters.py']:
  print('RUN',name,flush=True)
  subprocess.run([sys.executable,str(ROOT/'scripts'/name)],cwd=ROOT,check=True)
 print('Pipeline complete. Coverage is reported separately; it is not implied.')
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--offline',action='store_true');run(ap.parse_args().offline)
