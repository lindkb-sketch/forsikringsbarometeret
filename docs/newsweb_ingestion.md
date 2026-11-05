# NewsWeb-import

## Kilde og identitet

Nyhetsboksen bruker kun Oslo Børs NewsWeb. Importen leser JSON fra `https://api3.oslo.oslobors.no/v1/newsreader/list` og `/message`, ikke den tomme HTML-applikasjonen. Dette er nettstedets udokumenterte datagrensesnitt, ikke en API med garantert stabilitet. Feil format skal avvises, ikke tolkes som fravær av nyheter.

Numerisk `issuerId` og eksakt `issuerSign` leses fra en identitetsmelding hvis juridiske utsteder er kontrollert på NewsWeb. Disse meldingene er kun identitetsankere, aldri hardkodede «siste nyheter»:

| Side | Juridisk utsteder | Identitetsbevis |
| --- | --- | --- |
| Fremtind | Fremtind Forsikring AS | https://newsweb.oslobors.no/message/683603 |
| Gjensidige | Gjensidige Forsikring ASA | https://newsweb.oslobors.no/message/685479 |
| Tryg | Tryg Forsikring A/S | https://newsweb.oslobors.no/message/684542 |
| Frende | Frende Skadeforsikring AS | https://newsweb.oslobors.no/message/684953 |
| Protector | Protector Forsikring ASA | https://newsweb.oslobors.no/message/685366 |
| Storebrand | Storebrand ASA | https://newsweb.oslobors.no/message/685311 |

If/Sampo har ikke en verifisert NewsWeb-utstederkobling i denne endringen. Boksen holdes skjult med intern status `unverified_issuer`. Dette er ikke en påstand om at ingen meldinger finnes. Meldinger fra for eksempel Bank Norwegian som bare nevner Sampo, skal ikke brukes som erstatning.

## Publiseringsregler

Hver kjøring søker etter utstederens meldinger de siste 92 dagene, uten kategorifilter. Ved avkortet svar deles datointervallet; et ufullstendig dagsresultat avvises. Den nyeste meldingen kontrolleres også mot meldingsdetaljene. Bare overskrift, dato, identitet og lenke lagres. Brødtekst, vedlegg og finansielle nøkkeltall kopieres ikke.

Én melding vises per selskap. Tomme bokser og meldinger eldre enn 92 dager skjules. Uendrede svar bevarer filinnhold og `updated_at`; eldre svar erstatter ikke en nyere, fortsatt gyldig melding. Kildeutfall beholder sist validerte melding frem til utløp og gir en advarsel. Feilstatus og reelt tomt svar holdes adskilt i `coverage` og `errors`.

Eksisterende `update.yml` kjører importen og inkluderer `data/newsweb_notices.json` i begge listene for lagring av genererte data. Ingen ny scheduler, konto, hemmelighet eller betalt AI-tjeneste er nødvendig.

## Kontroller før sammenslåing

```
python -m py_compile scripts/update_newsweb_notices.py
python -m unittest discover -s tests -p 'test_newsweb_import.py' -v
python -m unittest discover -s tests -p 'test_company_exchange_notices.py' -v
python scripts/update_newsweb_notices.py --probe
```

De lokale testene bruker syntetiske API-svar, ikke innhentede nyheter. Renderer-testen kjører den faktiske funksjonen fra `index.html` i Node. `--probe` bruker derimot ekte JSON-svar og den samme `update()`-funksjonen som produksjon, skriver en midlertidig `data/newsweb_notices.json`, leser den tilbake og kontrollerer at uendret innhold ikke skrives på nytt. Den krever vellykkede svar fra alle konfigurerte utstedere og minst én aktuell melding. En gammel lagret feed kan ikke få denne testen til å bestå. Produksjonsfilen endres ikke av prøven.

Et grønt lokalt testresultat er ikke dokumentasjon på vellykket ekstern innhenting. PR-ens live-probe og fulle CI må bestå før sammenslåing; etter deploy skal den offentlige JSON-filen kontrolleres.
