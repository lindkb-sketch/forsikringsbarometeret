# Faktisk beviskontroll av automatisert import og publisering – 2026-10-26

## Konklusjon: IKKE BEVIST 7/7

Denne revisjonen undersøker den **faktiske** GitHub-koden, publiserte data og handlingsloggen, ikke bare syntetiske regresjonstester. Fullstendig, kildeuavhengig automatisk rapportoppdagelse → dokumentnedlasting → parser → kvalitetskontroll → publisering til nettstedet for alle sju utstedere er **ikke dokumentert** på grunnlag av tilgjengelige artefakter.

### Etterprøvbare kjøringer

- [Siste fullførte vellykkede hovedkjøring ved kontrollen, #687](https://github.com/lindkb-sketch/forsikringsbarometeret/actions/runs/40298572925): CI, integrert pipeline, feed-verifikasjon, Pages-deploy og nettlesertest var grønne.
- [Ny hovedkjøring etter dokumentasjonsmerge](https://github.com/lindkb-sketch/forsikringsbarometeret/actions/runs/40300720297): var fremdeles i gang ved denne kontrollen. Status må sjekkes etter fullføring.
- [PR #11](https://github.com/lindkb-sketch/forsikringsbarometeret/pull/11): dokumentasjon og konservative regresjonstester integrert i main; testresultat er ikke et bevis på full 7/7 live-import.

### Hva vi faktisk kan påvise

1. `.github/workflows/update.yml` er tidsstyrt med `17,47 * * * *`; arbeidsflyten kjører `scripts/run_pipeline.py`, `scripts/quarterly_import_contract.py`, `scripts/report_coverage.py`, nettlesertest og Pages-deploy.
2. `scripts/run_pipeline.py` kjører felles `ingest_official_pdf.py`, geografisk import, Tryg, Fremtind, Frende, Protector og Gjensidige sine importere og bygger feed. Koden bruker fallback ved noen utilgjengelige kilder.
3. `scripts/quarterly_import_contract.py` verifiserer **siste allerede importerte** periode for alle sju mot `data/verified_financial_feed.json`. Det er korrekt datakonsistenskontroll, men garanterer ikke oppdagelse av en faktisk *nyere offentliggjort* periode. Manglende kilde kan derfor gi grønn CI med eldre verifiserte tall.
4. `scripts/report_coverage.py` setter for øyeblikket `automatic_complete=False` eksplisitt per utsteder. Statusen er med hensikt konservativ, ikke beregnet fra et komplett løpsbevis.
5. Oppført `data/report_coverage.json` viser `all_seven_automatic=false`. Oppførte gruppe-kvartaler med grunnlagsmetrikker er henholdsvis Fremtind 2026-Q3, Gjensidige 2026-Q3, Tryg 2026-Q3, Sampo 2026-Q2, Frende ingen komplette, Protector 2026-Q3 og Storebrand ingen komplette etter rapportens strengere tre-metrikkdefinisjon. Dette betyr **ikke** at alle viste datapunkter mangler eller er feil; det betyr at rapportens konkrete fullstendighetskriterium ikke er oppfylt.
6. `docs/historical_replay_gaps_tryg_storebrand.md` beskriver ikke-rekonstruerte historiske Tryg- og Storebrand-observasjoner. Grønn produksjonsjobb løser ikke automatisk disse kildebevisene.

### Hva må dokumenteres for å kunne erklære 7/7

For **hvert** selskap kreves en ekte, periodemerkede sporbar hendelse:

| Bevisledd | Nødvendig logg/artefakt |
|---|---|
| Oppdaget | Offisiell indeks-URL, ny rapport-URL, tidspunkt og valgt kvartal |
| Innhentet | Nedlastet kilde, hash og identifisert utsteder |
| Parset | Faktiske felter, tabell/sidenummer, scope og valuta |
| Validert | Kildesamsvar, sammenligningsregler, ingen uverifiserte felt |
| Publisert | Eksakte observasjonsnøkler i git-feed og offentlig Pages-endepunkt |
| Live-kontroll | Browser- og JSON-bevis for identisk kvartal/verdi |
| Fornyet | Ny ordinær, planlagt kjøring finner og publiserer en *ny* faktisk rapport uten manuell hjelp |

Et test-fixture eller en syntetisk Q4 2026-drill teller bare som kodeberedskap. Eksisterende data i publisert feed teller ikke i seg selv som bevis på automatisk nyimport.

### Tiltak

- Utvid importkjøringen med et maskinlesbart, `run_id`-knyttet bevismanifest per utsteder, med periode, kildehash, kilde-URL, observerte verdier og publiserte nøkler.
- Sjekk siste offisielt *publiserte* periode mot siste faktisk *importerte* periode; skill `not_yet_released` fra `released_but_not_imported`.
- Legg på uavhengig nettleser-/endepunktkontroll mot den offentlige, publiserte versjonen; ikke gjenbruk et grønt CI-resultat som bevis.
- Verifiser historiske Tryg-/Storebrand-avvik fra kildedokumentene og en ren replay.
- Oppdater `automatic_complete` kun på grunnlag av eksplisitte, beståtte bevis per utsteder. Fram til da behold `all_seven_automatic=false`.

Ingen produksjonstall, kilder eller utgivelsesstatus er endret av denne revisjonen.
