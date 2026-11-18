# KLP: isolated-quarter methodology from HIÅ

KLP reports cumulative year-to-date (HIÅ) figures. Do **not** label cumulative figures as standalone quarters.

For additive monetary flows: Q1 = HIÅ Q1; Q2 = HIÅ Q2 − HIÅ Q1; Q3 = HIÅ Q3 − HIÅ Q2; Q4 = full-year − HIÅ Q3. Never subtract a previous fiscal year.

For loss, expense and combined ratios, first calculate the isolated-quarter claims, expense and revenue amounts, then divide by isolated-quarter revenue. Never subtract HIÅ percentages or average quarterly percentages.

A KLP-specific report parser must verify that all cumulative source values use the same definitions, accounting scope, currency, units, expense sign conventions and year. Use the precise numerator/denominator definitions in KLP's own report, including any adjustments to the combined ratio. The generic computation is only applicable where the issuer's ratio definitions match the mapped amounts.

Report provenance must include PDF URL, SHA-256 and page references for both the current and preceding cumulative observations. Missing documents, inconsistent definitions, unavailable numerators, denominator <= 0, or unsupported non-additive metrics must fail closed. ROE and solvency are not derived by cumulative subtraction.

**Certification:** This calculation module and synthetic unit tests do not prove that live KLP PDFs have been imported. Investor approval remains blocked until actual issuer report mapping, reconciliation to reported HIÅ figures and live end-to-end publication are verified.
