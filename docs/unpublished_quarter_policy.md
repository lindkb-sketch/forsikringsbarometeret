# Publiseringsregel for nye kvartaler

**Hovedregel:** Et selskap får først vist tall i resultattabellens inntekts- og inntektsvekstfelt når et kildeverifisert **inneværende kvartal** finnes for det selskapet. Historisk sammenligningsvekst kan være beregnet og lagret i feeden på forhånd, men blir ikke synlig for brukeren før kvartalsinntekten er publisert.

## Eksempler

- Q3 2026, Frende / Sampo uten offisiell rapport: «Ikke rapportert» i inntektsfeltet, «—» i vekstfeltet. Selv om Q3 2025 mot Q3 2024 er beregnet, **ikke vis** den parenteserte prosenten.
- Når Q3 2026 er verifisert, vis aktuell vekst og foregående års vekst i parentes under; bruk pil kun hvis begge prosentsatsene finnes.
- Q1 2027 og senere: samme regel, uten årsspesifikke grener. Kvalifisering skjer per selskap og valgt kvartal.
- Manglende historisk offisielt grunnlag: parentes «(—)», ikke et oppdiktet tall. Tidligere verifiserte observasjoner blir ikke slettet.

## Dokumentkrav og robusthet

Offisielle kvartalsrapporter/årsrapporter er eneste akseptable kilde for regnskapstall. PDF-/HTML-import skal validere selskap, juridisk enhet, periode, scope, valuta, tabelloverskrift, 2025-/2024-kolonner, kilde-URL, side og dokumenthash. Kontroller mot allerede verifiserte overlappende perioder. Ikke godta en enkelt ubekreftet tabellrad eller hardkodede posisjoner uten kontroll av kolonneoverskriftene.

Eksisterende historiske hull for Fremtind, Sampo, Protector og Storebrand må behandles som **åpne kildeimportoppgaver**, ikke som frontend-feil. Ingen automasjon skal sette `all_seven_automatic=true` uten faktisk nytt utstederrapport-bevis per selskap.
