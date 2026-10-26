# Full automasjon – verifikasjon og gjenstående arbeid

Oppdatert: 2026-10-26. Omfang: alle syv selskaper i Forsikringsbarometeret.

## Hva statusen betyr

`data/report_coverage.json` genereres av `scripts/report_coverage.py`. Feltet `automatic_complete` settes **eksplisitt til false** for hvert selskap. `all_seven_automatic` er `all(...)` over disse feltene og er derfor også false. Dette er en **konservativ ikke-sertifisert status**, ikke et empirisk bevis for at samtlige importløp feiler.

En grønn `.github/workflows/update.yml` viser at den planlagte jobben, enhetstestene, den integrerte kvartalspipelinen og publiseringen er gjennomført. Den dokumenterer **ikke** i seg selv uavhengig kildeoppdagelse, komplett kildeverifisert historikk eller løpende automatisk publisering av ny rapport for hvert selskap. Ikke beskriv grønn CI som 7/7 sertifisering.

## Etterprøvbar godkjenningsstandard (per selskap)

1. **Oppdagelse:** En faktisk ny, offisiell perioderapport oppdages automatisk fra utsteders kilde, med stabil dokument-URL og oppdagelseslogg. En indeksert lenke alene er ikke godkjent import.
2. **Innhenting og opprinnelse:** Kildedokumentets identitet, rapportperiode, selskap, konsern/Norge-segment, valuta, side/tabell og ved behov hash lagres etter etterprøvbar kontroll. Nedlastingssvikt og feil format håndteres uten å fabrikkere tall.
3. **Uttrekk:** Faktiske rapportverdier for inntekter, forsikringsresultat og nøkkeltall trekkes ut og avstemmes mot korrekt periode og omfang. «Rapport finnes» er ikke det samme som «tall importert».
4. **Kvartal mot HIÅ:** Isolerte kvartal og akkumulert HIÅ beregnes og vises separat. Foregående år sammenlignes bare med samme periode, samme scope, enhet og konsistent inntektsbegrep. Manglende tidligere år skal vises som utilgjengelig, ikke beregnes eller gjenbrukes.
5. **Publisering:** Ny verifisert observasjon kommer inn i generert feed og faktisk offentlig GitHub Pages-nettsted uten manuell inngripen. Gjentatt kjøring skal være idempotent.
6. **Feilmodus:** Uverifisert eller ufullstendig rapport må ikke overskrive sist verifiserte data eller oppnå sertifisering. Status må vise nøyaktig manglende ledd og lenke til kjøring/bevis.
7. **Reproduserbarhet:** En isolert test på ren grunnlinje, pluss normal planlagt kjøring, verifiserer hele kjeden for en ny periode. Testfixturer/syntetisk framtidskvartal dokumenterer kodeberedskap, men teller ikke som ekte rapportimport.

`automatic_complete=true` skal først være mulig etter at uavhengige, maskinlesbare bevis for **alle** kravene over finnes for det konkrete selskapet. Aggregeringsfeltet kan bli true først når alle sju er kvalifisert. Ingen endring av sertifiseringsstatus skal skje bare fordi testene forventer true.

## Nåværende observasjoner

| Selskap | Seneste verifiserte publiserte periode observert 2026-10-26 | Åpen sertifisering |
| --- | --- | --- |
| Fremtind | Q3 2026 | Ende-til-ende automatisering ikke dokumentert |
| Gjensidige | Q3 2026 | Ende-til-ende automatisering ikke dokumentert |
| Tryg | Q3 2026 | Ende-til-ende automatisering ikke dokumentert; historiske Norge-kilder må avstemmes |
| Sampo | Q2 2026 | Q3-data ikke kvalifisert; manglende verifiserte kilder må ikke fylles ut |
| Frende | Q2 2026 | Offisiell rapportdato/datadekning ufullstendig |
| Protector | Q3 2026 | Ende-til-ende automatisering ikke dokumentert |
| Storebrand | Q3 2026 | Kvartalsdekning og enkelte historiske tall ikke fullt dokumentert |

Dette er et øyeblikksbilde, ikke en permanent konklusjon. Autoritativ, oppdatert status er `data/report_coverage.json` og audit-/workflow-artefaktene.

Historiske begrensninger, beviskrav og særskilte Tryg/Storebrand-avvik: [historical_replay_gaps_tryg_storebrand.md](historical_replay_gaps_tryg_storebrand.md). Det dokumentet rapporterte sist 27 ikke rekonstruerte historiske observasjoner (25 Tryg Norge, 2 Storebrand ROE), og tallet kan bare oppdateres etter ny verifisert replay.

## Teknisk kjede og kontrollpunkter

- Tidsplan: `.github/workflows/update.yml`, `17,47 * * * *` (GitHub Actions cron i UTC).
- Ordinær pipeline: `scripts/run_pipeline.py`; importkontrakt: `scripts/quarterly_import_contract.py`; dekningsrapport: `scripts/report_coverage.py`.
- Tester: `python -m unittest discover -s tests -v`; `tests/test_report_coverage.py` beskytter nå mot falsk sertifisering.
- Publiseringskontroll: `scripts/verify_feed_coverage.py`, `scripts/verify_public_pages.py`, `tests/live_browser_e2e.cjs`.
- Revisjon: `data/financial_audit.json`, `data/report_coverage.json` og `data/investor_readiness.json`.

## Anbefalt implementering i prioritert rekkefølge

1. Introduser et eksplisitt **bevismanifest per selskap og periode**, generert fra ekte oppdagelse/import/publisering, ikke fra håndskrevet godkjenningsflagg.
2. Skill `discovered`, `downloaded`, `parsed`, `validated`, `published` og `historical_replay_verified`. Skriv `missing_evidence` for hvert selskap.
3. Lag ren-grunnlinje integrasjonstester for hver utsteder med kilde- og periodekontroll; oppdater sertifisering **først** når ekte kjøringer oppfyller manifestkravene.
4. Avstem åpne historiske Tryg-/Storebrand-avvik uten ommerking av konserntall til Norge eller antagelse om tidligere perioder.
5. Vis dekningsstatus separat fra grønn CI på nettstedet / i Actions-oppsummering. Feile sikkert ved feil verdier; manglende ennå ikke publiserte rapporter er ikke i seg selv CI-feil.

**Sikkerhetsregel:** Ikke endre produksjonstall, tvinge `automatic_complete=true` eller omgå kvalitetssperrene for å få grønn status.
