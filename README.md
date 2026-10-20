# Forsikringsbarometeret – GitHub Pages

Dette er en publiserbar Q2/Q3-visning med en **ekstern kalenderstatus** (`data/live.json`) og en automatisert publiseringsjobb.

## Oppsett
1. Opprett et GitHub-repositorium og last opp **innholdet** i denne mappen til `main`.
2. Under **Settings → Pages → Build and deployment**, velg **GitHub Actions**.
3. Kjør **Actions → Kontroller og publiser kalender → Run workflow**.
4. Åpne GitHub Pages-adressen etter vellykket publisering.

## Oppdateringsregler
- Kalenderen leses ved åpning og hvert femte minutt. Nedtellingen oppdateres hvert minutt.
- Workflow kjører fire ganger daglig og ved endringer i `main`.
- `data/calendar.json` inneholder kildebelagte kalenderdatoer. **Datoer oppdateres ikke automatisk fra nettstedene i denne versjonen**; ustrukturert tekst kan gi feil dato.
- `data/locks.json` er et revisjonsspor for kvartalslås. For å låse et kvartal kreves `reviewed: true`, `locked_at` og en offisiell `source_url`. Når Q3 låses, vises Q4 automatisk hvis Q4-dato finnes.
- Datoens passering er aldri i seg selv nok til å låse et kvartal.
- Manglende rapportdato vises som «Dato ikke bekreftet».

## Kritisk begrensning
**Dette er en fungerende automatisk kalender-/publiseringsarkitektur, ikke full automatisk innhenting av finansielle nøkkeltall.** Selskapenes PDF/XLSX-rapporter trenger egne testede kildeadaptere, validering av periode, valuta, Norge-segment og Storebrand konsern-ROE. Uten disse skal tall ikke auto-låses eller publiseres som kontrollerte.

Workflowens regelmessige kjøring alene oppdager heller ikke nye kalenderdatoer; nye datoer må legges inn i `calendar.json` fra bekreftet kilde. GitHub Pages kan være offentlig tilgjengelig; bruk ikke løsningen til konfidensielle tall uten tilgangskontroll.

Test: `python -m unittest discover -s tests -v`

## Kvalitetsstatus
Visningen har et tydelig datastatusfelt. Q3 er ikke komplett og alle KPI-er er ikke ferdig kildeverifisert. Automatisk finansiell rapporttolkning er ikke implementert.
