# Historical replay gaps — Tryg and Storebrand

Evidence: [GitHub Actions run 40006793715](https://github.com/lindkb-sketch/forsikringsbarometeret/actions/runs/40006793715), uploaded artifact `live-historical-import-replay`, specifically `missing_keys` and `missing_by_scope_period`. This is a **read-only documentation of replay coverage**, not a change to financial observations or a claim that the stored values are wrong.

## Tryg — 30 historical Norway observations

The clean-baseline test reconstructed **90 of 120** observations. Exactly 30 were absent: five `scope=norway`, `period_type=quarter` metrics for each of six quarters.

| Quarter | Missing metrics | Count |
| --- | --- | ---: |
| Q3 2024 | insurance_revenue, insurance_service_result, combined_ratio, loss_ratio, expense_ratio | 5 |
| Q4 2024 | same five | 5 |
| Q1 2025 | same five | 5 |
| Q2 2025 | same five | 5 |
| Q3 2025 | same five | 5 |
| Q4 2025 | same five | 5 |
| **Total** | | **30** |

The importer `scripts/import_tryg.py` deliberately skips issuer candidate pairs with `year < 2026`. During the tested discovery, the source index returned Q3 2025 and Q1–Q3 2026 candidates; no independently registered eligible XLSX/PDF pairs exist for each of these six older quarters in `data/geographic_workbooks.json`. The historical Norway records in `data/financial_observations.json` all reference the **same** Nasdaq attachment URL (`https://attachment.news.eu.nasdaq.com/a43872b6ebf83b3f2e6e25abb98b16226`), which is insufficient by itself to prove an independent quarter-specific PDF/XLSX provenance chain for all six. Do **not** relabel group figures as Norway or invent missing per-quarter workbook links.

**Needed for full certification:** identify issuer-linked original investor XLSX and corresponding official PDF for each relevant historical period, parse them in a disposable clean baseline, check the five numbers against existing source-provenanced records and audit, then rerun the isolated browser test.

## Storebrand — 12 historical observations

The replay reconstructed **51 of 63** observations. All twelve missing keys are:

| Period | Scope | Missing metrics | Count |
| --- | --- | --- | ---: |
| Q2 2025 | group | return_on_equity | 1 |
| Q4 2025 | group | return_on_equity | 1 |
| Q1 2026 | norway | insurance_revenue, insurance_service_result, combined_ratio, loss_ratio, solvency_ratio | 5 |
| Q2 2026 | norway | same five | 5 |
| **Total** | | | **12** |

`scripts/storebrand_publish_q3.py` is a strict **Q3 2026** publication importer. It correctly reconstructed its Q3-linked 51 rows but was not asked to import the separately published Q1 and Q2 Norway subsidiary PDFs or the Q2 2026 ASA report's comparative return-on-equity rows. Existing source evidence points to:

- Q1 2026 Norway: `https://www.storebrand.com/welcome/investor-relations/quarterly-reporting/storebrand-forsikring-as/_/attachment/inline/14c9b4ed-09ca-4a91-b471-1583f8805cb6:99434cef1dcb6d4af35c0959884b29793e418c9c/2026-q1-interim-report-storebrand-forsikring.pdf`
- Q2 2026 Norway: `https://www.storebrand.com/welcome/investor-relations/quarterly-reporting/storebrand-forsikring-as/_/attachment/inline/987dbe4a-bc14-43a4-b3c3-7ca9011365f0:908282930661462633398c99469914c6961ececc/2026-q2-interim-report-storebrand-forsikring.pdf`
- Q2/Q4 2025 group comparison ROE: existing observations reference the Q2 2026 Storebrand ASA report, `https://www.storebrand.com/welcome/investor-relations/quarterly-reporting/storebrand-asa/2026/_/attachment/inline/4237d035-d763-4991-b204-bc1f67cf23ea%3Ad3110f016fb66573dd897fa09fdf013b05a792df/2026-q2-interim-report-storebrand-asa.pdf`.

**Needed for full certification:** replay the strict Storebrand Q1 and Q2 historical parsers using these issuer reports in a clean disposable dataset and reconcile all ten Norway figures and both ROE figures against the existing golden data. If the older parser cannot account for the reported values, stop and report the unsupported period without importing guessed values.

## Current claims and controls

- True complete historical clean-baseline recovery from this run: **5 of 7 issuers** (Fremtind, Gjensidige, Sampo, Frende and Protector).
- Missing historic observations: **42 total**: Tryg 30; Storebrand 12.
- A successful GitHub workflow, a zero exit code or successful browser checks **must not** be interpreted as 7/7 complete historical reconstruction.
- This document changes **no** production financial data, source values or `17,47 * * * *` schedule.


## Update 2026-10-23 — exact last 27 unrecovered observations

The newer [isolated historical replay run 40008005697](https://github.com/lindkb-sketch/forsikringsbarometeret/actions/runs/40008005697) produced 379/406 (five fully restored issuers). These exact missing keys were read from the uploaded `live-historical-import-replay` artifact's `missing_keys` entries, not inferred from a green workflow.

**Tryg: 25 Norway quarter observations** (the five metrics below for **each** of Q3 2024, Q4 2024, Q1 2025, Q2 2025 and Q4 2025). Historical stored values in `data/financial_observations.json` are recorded for comparison, **not independently re-certified** by this replay. Monetary unit is DKK millions; ratios are percent.

| Metric | Q3 2024 | Q4 2024 | Q1 2025 | Q2 2025 | Q4 2025 |
| --- | ---: | ---: | ---: | ---: | ---: |
| insurance_revenue (DKKm) | 2083 | 2125 | 2059 | 2175 | 2305 |
| insurance_service_result (DKKm) | 311 | 130 | 96 | 389 | 297 |
| combined_ratio (%) | 85.1 | 93.9 | 95.3 | 82.1 | 87.1 |
| loss_ratio (%) | 72.5 | 80.3 | 82.8 | 70.1 | 75.8 |
| expense_ratio (%) | 12.5 | 13.6 | 12.5 | 12.0 | 11.3 |

For these 25 records, the historical source metadata identifies [Nasdaq attachment a43872b6ebf83b3f2e6e25abb98b16226](https://attachment.news.eu.nasdaq.com/a43872b6ebf83b3f2e6e25abb98b16226), **page 36**, for all five periods. The latest replay attempted issuer-linked PDF/XLSX discovery: **Q3 2025 recovered 5/5**; **Q3 2024 returned `Historical Norway golden mismatch`**; **Q4 2024, Q1 2025, Q2 2025 and Q4 2025 each returned `Issuer-linked paired PDF/XLSX not discovered`**. These outcomes must not be treated as verified values or silently replaced by group data. The Q3 2024 mismatch needs cell-level reconciliation between the original investor workbook, scope, and archived numbers.

**Storebrand: 2 group quarterly observations** (`metric=return_on_equity`, `period_type=quarter`, `scope=group`):

| Period | Stored reference value | Source |
| --- | ---: | --- |
| Q2 2025 | 18.1% | Storebrand ASA Q2 2026 interim report, p. 5 |
| Q4 2025 | 17.4% | Storebrand ASA Q2 2026 interim report, p. 5 |

Both reference rows identify the [official Storebrand ASA Q2 2026 PDF](https://www.storebrand.com/welcome/investor-relations/quarterly-reporting/storebrand-asa/2026/_/attachment/inline/4237d035-d763-4991-b204-bc1f67cf23ea%3Ad3110f016fb66573dd897fa09fdf013b05a792df/2026-q2-interim-report-storebrand-asa.pdf). The isolated Storebrand Q3 + Q1/Q2 2026 replay recovered **61/63**; it does not reconstruct these two earlier quarterly comparatives. Before certifying them, parse the PDF's relevant explicitly labelled ROE columns and check period attribution; do not assume either is the ROE for Q2/Q4 merely because the PDF contains these values.

**Certification requirement:** exact source and historical scope/period verification for all 27 keys, clean-baseline import + golden comparisons, source SHA/page provenance, followed by the replay-only website feed/browser test. A green workflow is not equivalent to complete 406/406 recovery. No stored production values or scheduled cron were modified by this documentation.
