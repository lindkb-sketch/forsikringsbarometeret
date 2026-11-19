# Dual-document quarterly source policy

All nine insurers (Fremtind, Gjensidige, Tryg, Sampo, Frende, Protector,
Storebrand, KLP Skadeforsikring and Alm. Brand) require review of **both**
the official quarterly report and the official results presentation.

A metric may originate in either document. For every value preserve issuer-
verified HTTPS document URL, SHA256 of actual PDF bytes, page number, year,
quarter, period type, reporting scope, metric, unit and value. Matching
values may be reconciled; disagreements must block automatic publication.
Never infer group ROE from investment return, or substitute YTD for quarter.
Never classify a metric as unavailable until both document types were checked.

The reusable validator is `scripts/dual_document_evidence.py`. It does **not**
automatically discover presentations, authenticate an issuer, download PDFs,
or modify published financial values. Existing issuer-specific importers and
production pipeline must be integrated separately before claiming automated
end-to-end coverage.

Alm. Brand Q3 2026: user-provided presentation screenshot, slide 19, reports
SCR ratio **238%**, own funds **DKK 4,685m**, SCR **DKK 1,970m**.
The screenshot alone does not supply a verifiable official document URL or
PDF digest; therefore the production record must not be silently upgraded
until the original presentation is retrieved and verified.
