# Meglerhusenes kvartalskommentarer

## Bruk på Forsikringsbarometeret

Den offentlige startsiden har et tekstpanel **Meglerhusenes vurderinger** under
**Utvikling i lønnsomhet**. Panelet vises bare dersom det er publisert et sammendrag
for valgt selskap og kvartal. Data hentes fra `data/broker_commentary.json`,
og kontrolleres på nytt hvert femte minutt. Verken PDF-filer, PDF-filnavn eller
private mapper vises i panelet eller inngår i den offentlige datafilen.

Åpne nettstedets administrasjonsvisning med `?admin=1` og velg
**Meglerkommentarer (privat)**. Velg selskap, kvartal og meglerhus, og legg til
PDF-ene. Flere PDF-er kan lagres i samme kvartalsmappe. Når finansfeeden
oppdager et nytt verifisert kvartal, opprettes en ny, lokal kvartalsmappe
automatisk for kommende opplastinger. Mappene ligger i nettleserens IndexedDB,
ikke på GitHub Pages.

**Viktig sikkerhetsgrense:** `?admin=1` skjuler knappen for lesere, men er
ikke autentisering. De lokale PDF-ene synkroniseres ikke mellom enheter og er
ikke sikkerhetskopiert. De kan være tilgjengelige for kode som kjører på
samme nettsted/opprinnelse og for nettleserutvidelser. Ikke behandle dette
som en sikret dokumentportal for dokumenter med strenge konfidensialitetskrav.
For slike rapporter kreves separat innlogging, privat lagring og tilgangskontroll.

## AI-oppsummering og publisering

GitHub Pages er en statisk tjeneste uten sikker server-side AI-nøkkel eller
privat opplasting. **Fullautomatisk AI-generering ved hver PDF-opplasting er
ikke aktivert i denne fasen.** Bruk knappen **Kopier instruks for ChatGPT**,
last opp meglerhusenes PDF-er i ChatGPT, og lim et kontrollert, sammenskrevet
sammendrag inn i feltene for resultatreaksjon, viktigste forhold og utsikter.

Brukeren kontrollerer faglig innhold, sammenligningsgrunnlag,
forventninger, kvartal og rettighetene til å publisere sammendrag før godkjenning.
Knappen **Last ned offentlig sammendrag** genererer kun
`broker_commentary.json`. Publiser denne som
`data/broker_commentary.json` på `main` i GitHub. Dette gjøres på samme
måte som administratorens nåværende nedlasting/publisering fra Finans Norge.
Original-PDF-ene skal **aldri** legges i `data/`, Git-repositoriet eller
noen mappe under GitHub Pages.

Kun begrensede, selvstendige sammendrag – ikke gjengitte analyser eller lange
sitater – skal publiseres. Skille mellom rapportert resultat, analytikernes
forventninger og deres fremoverskuende vurderinger.

## Fremtidig full automatisering

For at brukeren skal kunne laste opp en PDF på nettstedet og få et nytt
AI-sammendrag publisert helt automatisk, må det opprettes en egen tjeneste
med autentisert administrator, privat PDF-lagring, AI-analyse med serverbasert
API-nøkkel, kildekontroll og publiseringsgodkjenning. Ingen slik nøkkel,
upublisert rapport eller privat mappe må eksponeres i HTML/JavaScript/GitHub Pages.
