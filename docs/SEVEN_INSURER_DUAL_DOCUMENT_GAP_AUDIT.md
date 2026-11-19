# Delmål 3 – Kildeinventar for syv etablerte forsikringsselskaper

Periode: Q3 2026. Dette er en **ikke-destruktiv inventarkontroll**, ikke en attestasjon av at begge offisielle dokumenter er undersøkt. Kildegrunnlaget er `data/verified_financial_feed.json` og `data/report_candidates.json` på `main` ved oppstart.

| Selskap | Verifiserte kjerne-KPIer i kvartalsfeed | Kildeobservasjoner fra rapport | Kildeobservasjoner fra presentasjon | Uverifiserte rapportkandidater (alle perioder) | Uverifiserte presentasjonskandidater (alle perioder) |
| --- | --- | ---: | ---: | ---: | ---: |
| Fremtind | 5/5 | 7 | 0 | 0 | 0 |
| Gjensidige | 5/5 | 7 | 0 | 0 | 0 |
| Tryg | 5/5 | 7 | 0 | 6 | 3 |
| Sampo | 5/5 | 5 | 0 | 2 | 1 |
| Frende | 5/5 | 5 | 0 | 28 | 0 |
| Protector | 5/5 | 7 | 0 | 0 | 0 |
| Storebrand | 5/5 | 7 | 0 | 0 | 0 |

**Funn:** Alle syv har fem sentrale Q3-gruppenøkkeltall med eksisterende rapportkilde og kildehash. Ingen av de 45 eksisterende Q3-gruppeobservasjonene er merket som hentet fra resultatpresentasjon. Dette beviser **ikke** at presentasjoner er undersøkt eller at de mangler relevante KPIer. Kandidatlisten er diagnostisk, kan være ufullstendig, og kandidatene kan gjelde andre perioder. En tom liste betyr ikke at selskapet ikke har presentasjoner.

**Identifiserte gap:** Sampo og Frende mangler ROE og solvensgrad i de isolerte Q3-gruppeobservasjonene. Øvrige fem har disse feltene. Ingen av de syv har eksplisitt `profit_before_tax` eller `insurance_revenue_growth` som kildeobservasjon for Q3 i den isolerte feeden (sammenligningsbyggeren kan beregne sistnevnte fra årssammenlignbare kvartaler). Disse feltene er **ikke dokumentert fraværende hos utsteder** før begge offisielle dokumenter er undersøkt.

**Viktig kildeskille:** Frendes eksisterende gruppeobservasjoner refererer til `frende.wrep.it`-HTML-seksjoner, ikke direkte PDF-adresser, selv om `source_type` er `official_quarterly_report`. En SHA256-streng i metadata alene beviser ikke at en bestemt PDF er verifisert. Eksisterende verdier endres ikke i dette delmålet; delmål 4 må bevise faktisk dokumentbytes og kildeidentitet.

**Neste delmål:** Perioderiktig oppdagelse og nedlasting fra autoriserte offisielle utstederdomener/CDNer; verifiserte PDF-bytes og SHA256, sidetall, valuta og omfang; sammenlign rapport og presentasjon; importer komplementære KPIer og stopp ved motstrid. Ikke merk et felt manglende før begge kilder er kontrollert.

Kjør `python scripts/audit_seven_document_sources.py` for et maskinlesbart øyeblikksbilde. Skriptet endrer ingen finansielle observasjoner.
