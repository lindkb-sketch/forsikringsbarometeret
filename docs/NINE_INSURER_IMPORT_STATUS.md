# Nine-insurer integration: evidence and release contract

Updated: 2026-11-18.

## Implemented
- Nine-company source registry and calendar checks are enforced by the finance workflow.
- A conservative PDF discovery utility is available for KLP Skadeforsikring and Alm. Brand. It restricts URLs to approved issuer hosts, checks PDF signatures and sizes, and can return SHA-256 fingerprints and page numbers for keyword-bearing PDF pages.
- A nine-company comparison JSON is generated from the existing audited seven-company feed and the separately attributed Alm. Brand issuer announcement. Missing KLP values remain null. Different currencies and non-equivalent revenue definitions must not be aggregated.
- Tests cover hostile URLs, PDF discovery, missing KLP values, and nine-company membership.

## Not certified / blocking work
- KLP's financial metrics have **not** been imported and page-verified from an official quarterly PDF.
- Alm. Brand's Q3 values are verified from an issuer announcement, **not** from page-located PDF financial statements.
- Future-quarter PDF parsing is **not** certified. New document layouts need explicit issuer-specific metric mapping, unit/period/scope checks, and independent verification.
- End-to-end certification requires an observed newly published report to be discovered, fetched, fingerprinted, parsed, validated, inserted into the audited financial feed, published, and confirmed on public Pages **in the same scheduled run**. A synthetic test or green workflow alone cannot satisfy this requirement.
- Investor readiness remains NOT_APPROVED_FOR_INVESTOR_USE until those requirements and the existing seven-company automation evidence are fulfilled.

## Reproducibility
- `python -m unittest discover -s tests -p 'test_nine_insurer_import_readiness.py' -v`
- `python scripts/import_extended_pdfs.py` (diagnostic; does not publish financial values)
- `python scripts/build_nine_insurer_comparison.py`
- `python scripts/check_extended_insurer_evidence.py`

Do not remove the investor-readiness gate or mark missing values as zero. The comparison is a coverage view, not an investment-grade nine-company ranking.
