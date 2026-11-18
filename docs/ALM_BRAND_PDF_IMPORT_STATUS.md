# Alm. Brand official PDF ingestion – step 2

## Implemented
- Issuer-host HTTPS allowlist and PDF signature gate.
- PDF page label discovery through pdfplumber.
- Fail-closed extraction contract for **isolated quarterly** group metrics,
  with exact Q/year column, DKK million versus percent units, per-metric
  page evidence and SHA-256 fingerprint.
- Synthetic regression tests covering wrong period, source, unit, missing
  and ambiguous table values. Tests are run in finance CI.

## Not implemented / certification blockers
- The report-specific PDF table reader that creates page-located
  `table_rows` from real Alm. Brand PDFs is **not yet implemented**.
- Real PDF report period, accounting scope and unit headers must be
  independently verified before table rows are admitted.
- PDF-extracted values are not promoted to `data/extended_insurer_financials.json`
  and do not replace the verified Q3 2026 issuer announcement.
- Real-PDF reconciliation, production dashboard parity, and an observed
  newly released report end-to-end test are required before certification.
- Investor readiness remains blocked.

Run `python -m unittest discover -s tests -p 'test_alm_brand_pdf.py' -v`.
