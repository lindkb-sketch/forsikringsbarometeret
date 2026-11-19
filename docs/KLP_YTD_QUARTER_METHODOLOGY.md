# KLP: issuer-reported isolated quarters and HIÅ-consistent ratios

KLP reports isolated quarterly financial amounts in its result table. These amounts are the authoritative source for the quarter. Do **not** derive them by subtracting consecutive HIÅ columns.

For loss ratio, expense ratio and combined ratio, use the issuer's HIÅ metric definitions and apply the **same numerator, denominator, adjustment and sign conventions** to the directly reported isolated-quarter amounts. Do not subtract or average HIÅ percentages.

Reconcile the methodology by independently reproducing the reported HIÅ KPIs using the cumulative amounts and issuer definitions. A mismatch beyond documented rounding tolerance blocks publication. Do not assume a simple claims/revenue ratio where KLP's actual definition includes additional adjustments.

Require matching entity, fiscal year, scope, currency, units and page-located official PDF evidence. Do not derive ROE or solvency by HIÅ subtraction. Missing definitions, numerator or denominator components fail closed.

The current module is a calculation contract and synthetic test suite, not a verified live KLP PDF importer or end-to-end certification.

## Verified issuer definition detail

KLP's official Q1 2026 Skadeforsikring report, Note 10, explicitly distinguishes
*Skadeprosent brutto*, *Gjenforsikringsprosent*, *Skadeprosent etter gjenforsikring*,
*Kostnadsprosent* and *Totalskadeprosent*. Its Q1 HIÅ ratios are 82.8%, 3.7%,
86.5%, 13.8% and 100.4%, respectively (displayed rounding).
Thus using gross claims plus operating expenses alone is **not** KLP's
total-claims/combined-ratio definition. The reinsurance component is essential.
The dedicated reconciliation module enforces the issuer's gross + reinsurance +
expenses construction, including tolerance for reported rounding.

The 2026 Q1 report is available at:
https://www.klp.no/om-klp/finans-og-ir/rapporter-og-presentasjoner/_/attachment/inline/003381a3-7e8d-44bc-84e4-6de354b1fc79%3Aee97b842e57469c4897509abea3bee80331904b3/Kvartalsrapport%20KLP%20Skadeforsikring%20AS%20Q1%202026.pdf

**Still blocking live import:** page-specific extraction of the isolated quarter
result columns and all numerator/denominator components from the real PDFs,
and observed end-to-end production publication. No investor-grade approval is claimed.
