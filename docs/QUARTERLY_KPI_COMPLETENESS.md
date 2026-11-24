# Automatisk KPI-kompletthet for ni selskaper

Denne kontrollen sammenligner de ni nøkkeltallene som vises i
`data/nine_insurer_comparison.json` for alle ni utstedere.

Kjør `python scripts/build_nine_insurer_comparison.py` og deretter
`python scripts/quarterly_kpi_completeness.py`. Resultatet ligger i
`data/quarterly_kpi_completeness.json` og viser hvilke felter som fremdeles
mangler per selskap og siste publiserte kvartal.

**Viktig:** Ikke-null betyr bare at sammenligningsfeeden har en verdi.
Det beviser ikke at en ny kvartalsrapport ble oppdaget, PDF-en lastet ned,
rapport og presentasjon sammenlignet, eller at tallene ble importert
uten manuell hjelp i samme planlagte Actions-kjøring.

Manglende tall skal ikke nullfylles, anslås eller erstattes av tall
med annet scope, inntektsbegrep, valuta eller periode. Et nøkkeltall
som ikke oppgis i utstederens rapporter, må markeres eksplisitt som
ikke tilgjengelig etter dokumentert kontroll av relevante kilder.

Neste steg for faktisk fullautomatisering er utstederspesifikke
rapport- og presentasjonsadaptere med sporbar kildehash, side/tabell,
kvartal/HIÅ, avstemming, og publiseringsattestering fra samme workflow-run.
Denne statusrapporten er bevisst ikke en sertifisering av dette.

## Rapporteringsregler fra prosjekteier

- KLP og Frende: ROE er ikke påkrevd. Frende: solvensgrad er ikke påkrevd.
- Sampo: Solvency II ratio og Return on equity own funds, med original definisjon.
- Solvensgrad er et balansetidspunktstall ved kvartalsslutt. For samme år, kvartal og scope skal kvartalsvisning og HIÅ vise identisk verdi. Ingen summering, gjennomsnitt, annualisering eller fremføring fra tidligere kvartal. Manglende kildeverifisert verdi for valgt kvartal skal forbli null.
