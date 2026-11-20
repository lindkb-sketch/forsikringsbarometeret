# Delmål 4 – automatisert dobbel dokumentkontroll (grunnlag)

Denne endringen legger til en separat, konservativ kontroll av **begge** offisielle dokumenttypene for alle ni selskaper. Den endrer ikke eksisterende syv importører, finansielle verdier eller produksjonspublisering.

1. `scripts/discover_reports.py` oppdager både rapporter og kvartalsspesifikke resultatpresentasjoner på utstederens domene og eksplisitt godkjente leveringsdomener.
2. `scripts/verify_nine_document_bytes.py` forsøker å laste ned periodemerkede PDF-kandidater, avviser eksterne videresendinger, verifiserer faktisk PDF-innhold, utstederidentitet og Q3/år, og beregner SHA256 fra nedlastede bytes.
3. `.github/workflows/verify-dual-documents.yml` kan kjøres manuelt og lagrer diagnostikk som artefakt. Den oppdaterer **ikke** publiserte finansielle observasjoner.

## Ikke ferdig

PDF-verifikasjon alene er **ikke** verifisert KPI-ekstraksjon. Kildenes kvartalskolonner, YTD/kvartal, konsern versus norsk enhet, måleenheter og krysskontroll av hver KPI må verifiseres i egne utstederspesifikke ekstraktorer. Den eksisterende `dual_document_evidence.py` kan avstemme ferdige dokumenterte KPI-observasjoner og stoppe ved motstrid, men er ikke automatisk koblet til alle ni importører. Ingen manglende KPI skal merkes definitivt fraværende før begge dokumenter er gjennomgått.

**Klareringsregel:** Delmål 4 kan ikke erklæres fullført før en reell kjøring har verifisert begge dokumenttypene, eller dokumentert at en type ikke er publisert, for hvert av de ni selskapene, og alle kildebaserte KPIer er avstemt og publisert korrekt. Et grønt dokumentkontroll-workflow betyr ikke at dette er oppnådd.
