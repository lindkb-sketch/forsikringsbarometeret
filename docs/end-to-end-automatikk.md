# Ende-til-ende dokumentasjon – automatisk kvartalsimport

## Hva som er bevist

En grønn GitHub Actions-jobb dokumenterer at registrerte kilder har passert kontroll, og at publisert JSON matcher det validerte datasettet. Dette alene dokumenterer **ikke** automatisk oppdagelse og import av en *ny* rapport for hvert selskap.

`data/report_coverage.json` har nå `e2e_evidence` per selskap med maskinlesbare trinn og `missing_e2e_evidence`. Den beholder `all_seven_automatic: false` inntil hvert obligatoriske trinn har positive, tidsstemplede kjøreevidens fra samme planlagte kjøring.

## Kjeden som må dokumenteres for hvert av de sju selskapene

1. GitHub Actions starter på planlagt tidspunkt uten `workflow_dispatch` eller kode-push.
2. Automatisk rapportoppdagelse finner en ny offisiell publikasjon med riktig selskap og kvartal; lagre URL og rapportidentifikator.
3. Dedikert importør laster rapporten ned og leser obligatoriske størrelser; lagre PDF-hash, kildeside og definisjon.
4. Datarevisjonen godkjenner importen. Manglende/uklar KPI må blokkere ny publisering, ikke fylles med oppdiktede verdier.
5. `verified_financial_feed.json` inneholder de validerte observasjonene uendret; `publication_provenance.json` bekrefter kilde-/feed-likhet.
6. Pages-deploy fullføres; `verify_public_pages.py` bekrefter likhet mellom deployet HTML, feed og commit.
7. Et separat revisjonsbevis knytter **samme** planlagte workflow-run-ID, rapportkvartal, kilde-hash, feed-hash og deploy-URL sammen.

## Hva som mangler

Per nå bekrefter systemet historiske observasjoner, automatiske importører og en vellykket Pages-verifikasjon. Det finnes ikke et dokumentert, nyrapportbasert, uovervåket importløp for alle sju selskapene. Derfor kan det ikke hevdes at framtidige kvartaler er ende-til-ende bevist.

`fresh_report_discovery_observed`, `fresh_report_ingested_without_manual_intervention` og `public_pages_parity_observed_in_same_scheduled_run` står uttrykkelig som `false` inntil tilsvarende bevis finnes. Disse skal **ikke** settes til `true` bare fordi en test er grønn.

## Kontrollkommandoer

```sh
python scripts/report_coverage.py
python scripts/publication_provenance.py
python scripts/verify_public_pages.py
python -m unittest discover -s tests -v
```

Oppsummering etter hver kjøring finnes i GitHub Actions for `.github/workflows/update.yml`. Filene under `data/` inneholder siste byggs observasjoner og dokumentasjonsstatus.

## Neste milepæl

Implementere kjøringsspesifikk discovery-/import-attestering fra hver dedikert importør, etterfulgt av en deploy-attestering når den offentlig tilgjengelige Pages-versjonen er kontrollert. En attestering må være knyttet til samme run-ID, faktisk nyrapport (ikke historisk baseline), hash og kvartal; den må feile lukket ved kildekonflikter. Først etter en vellykket planlagt nyrapportimport for hvert selskap kan `all_seven_automatic` bekreftes.
