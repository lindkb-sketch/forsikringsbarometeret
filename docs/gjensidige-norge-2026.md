# Gjensidige Norge – Excel-kontroll (2026)

## Kilde og metode
Gjensidige publiserer «Key figures» Excel for Q1 og Q2 på https://www.gjensidige.com/investor-relations/reports-and-presentations .
Norge er summen av arkene **General Insurance Private Norway** og **General Insurance Commercial Norway**, ikke konsern, Danmark eller Sverige.
Tallene i arbeidsboken er NOK (divider med 1 000 000 for MNOK), mens prosenter er desimaltall (multipliser med 100).
For combined, loss og cost ratio brukes forsikringsinntektsvektet gjennomsnitt; de to segmentprosentene skal aldri summeres direkte.

## Gjennomgått Q2 2026-arbeidsbok
Gjennomgang av tilgjengelig Excel-arbeidsbok med fanene «General Insurance Private Norwa» og «General Insurance Commercial No» gir:

| Periode | Inntekter MNOK | Forsikringsresultat MNOK | Skadeprosent % | Kostnadsprosent % | Combined ratio % |
| --- | ---: | ---: | ---: | ---: | ---: |
| Q2 2026 | 8 145,16 | 2 773,30 | 56,597 | 9,354 | 65,952 |
| YTD Q2 2026 | 15 865,73 | 4 522,54 | 62,110 | 9,385 | 71,495 |

Kildeceller: Private Norway og Commercial Norway, rad 5 (revenue), 11 (service result), 20 (loss ratio), 21 (cost ratio), 22 (combined ratio), kolonne B (Q2) og D (YTD).
Disse er kontrollberegninger, **ikke publiseringsbekreftelse**. Originalfilens direkte offentlige nedlastingsadresse og byteidentitet er ikke fastslått.

## Status
- Konsern: Q1/Q2 automatisk publisert og live-kontrollert.
- Norge: Skript `scripts/gjensidige_norway_excel.py` er lagt til med streng cellekontroll og kildekrav.
- Norge-importen er **ikke koblet til aktiv arbeidsflyt og ikke live-verifisert**. Det er ikke dokumentert at offisiell rapportside eksponerer direkte Excel-URL i statisk HTML.
- Ingen Norge-observasjoner skal publiseres før direkte offisiell XLSX-lenke, korrekt kvartal, riktige ark, revisjon av beregninger og vellykket Actions-kjøring er kontrollert.

## Definisjon av Norge og separate segmenter
Norge totalt = **PM Norge (General Insurance Private Norway)** + **BM Norge (General Insurance Commercial Norway)**. Forsikringsinntekter og forsikringsresultat summeres; combined ratio, skadeprosent og kostnadsprosent beregnes som inntektsvektede forholdstall. Ingen konsernverdier blandes inn. Importøren leser PM/BM direkte fra egne Excel-ark og produserer også `data/gjensidige_norway_segments.json` med hvert segments kildeark og kildecelle. Segmentfilen produseres bare når importøren kjøres; den er foreløpig ikke bekreftet publisert.

## Oppdatert kontrollprosedyre 22.10.2026
Importen er nå koblet til GitHub Actions. Den skal rekonstruere netto combined ratio separat for PM og BM fra signerte forsikringskostnader og reassuranseresultat og sammenligne mot hvert segments publiserte combined ratio (toleranse 0,15 prosentpoeng). Bare når begge kontroller består beregnes Norge totalt fra summerte beløp. `openpyxl` er lagt til avhengighetene. Netto skadeprosent Norge er fortsatt ikke implementert fordi underliggende skadekostnadsrader ennå ikke er identifisert og validert. Kjøring og live-publisering må bekreftes i Actions-loggen; kode alene er ikke godkjenning.

## Q2 2026 – kontroll mot faktiske norske segmenttabeller
Kilde: Gjensidige offisiell Q2-rapport (se PDF https://mb.cision.com/Public/1122/4373892/b3fb98691b4814f0.pdf ), avsnittene «General Insurance Private Norway» og «General Insurance Commercial Norway».

Alle tall i MNOK. PM: revenue 4093.4, incurred claims -2288.2, other expenses -434.6, reinsurance premiums -36.1, recovered 24.8, service result 1359.5. BM: revenue 4051.7, incurred claims -2513.3, other expenses -327.3, reinsurance premiums -143.5, recovered 346.3, service result 1413.9.

PM kontroll: netto skadeprosent = (2288.2+36.1-24.8)/4093.4 = 56.18 % (rapport 56.2); kostnadsprosent = 434.6/4093.4 = 10.62 % (rapport 10.6); CR = 66.80 % (rapport 66.8).
BM kontroll: netto skadeprosent = (2513.3+143.5-346.3)/4051.7 = 57.02 % (rapport 57.0); kostnadsprosent = 327.3/4051.7 = 8.08 % (rapport 8.1); CR = 65.10 % (rapport 65.1).
Norge Q2: revenue 8145.1, incurred claims -4801.5, other expenses -761.9, reinsurance premiums -179.6, recoveries +371.1. Netto skadeprosent 56.60 %, kostnadsprosent 9.35 %, CR netto 65.95 %. Tallene er kontrollert mot publiserte PDF-segmenttabeller, **ikke mot XLSX-bytefil**. En eksakt offisiell XLSX-URL og vellykket importkjøring mangler fremdeles. Ikke erklær fullført på denne kontrollen alene.
