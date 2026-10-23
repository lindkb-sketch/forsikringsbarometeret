# Publiseringsstandard for Forsikringsbarometeret

**Nettstedet er en kontrollutgave, ikke et godkjent investor- eller styredokument.** Fravær av tekniske feil er ikke det samme som verifiserte finansdata.

## Kildegrunnlag og tall
For hvert rapporterte nøkkeltall kreves selskap, kvartal, år, konsern/Norge, isolert kvartal/HIÅ, metrikk, verdi, enhet, offentlig URL og presis PDF-side eller XLSX-celle. Ulike selskapsspesifikke regnskapsdefinisjoner må identifiseres. Segmentpremier (APM) er ikke nødvendigvis sammenlignbare med IFRS 17 forsikringsinntekter.

## Obligatorisk kvartalskontroll
`scripts/investor_readiness.py` bygger `data/investor_readiness.json` etter oppdatering av rapporter, kalender, nyheter og sluttkurser. For siste kildeverifiserte konsernkvartal oppgis per selskap:
- tilgjengelige og manglende nøkkeltall
- siste verifiserte kvartal (ikke automatisk samme som nettstedets globale kvartal)
- forventet rapportdato og avvik mot denne
- andel av automatisering som faktisk er ende-til-ende-godkjent
- inntektsdefinisjoner som ikke er IFRS-sammenlignbare

Investorklar-status krever komplett og dokumentert kvartal for alle sju, formelt verifisert automatikk, definisjonsmessig sammenlignbarhet og daterte, rimelig ferske kurser/nyheter. Selv når automatiske tester passerer, kreves uavhengig faglig godkjenning før ekstern distribusjon. Det er **ikke** tillatt å gjøre manglende tall «komplette» med estimater.

## Teststrategi
1. Enhetstester for kildeproveniens og alle dataparsere, inkludert tomme/avvikende dokumenter.
2. End-to-end-test for generert feed, graf, HIÅ, kommentarer, nyheter, kursdatoer og kalender i originalt grensesnitt.
3. Testdata for Q4 2026 og Q1 2027 og videre, slik at rullering, neste-år-logikk, forsinkede selskaper og ufullstendige rapporter oppdages før reelle data.
4. GitHub Actions bygger investorkontroll **før publisering** og legger kontrollfilen i den publiserte dataleveransen. Publisering av kontrollutgaven kan skje dersom tekniske og kildebaserte tester går grønt. Den markeres eksplisitt **ikke investorgodkjent** når komplette resultater mangler.
5. Enhver separat leder-/investorutgave skal kunne kjøre `python scripts/investor_readiness.py --strict`, som feiler hvis kravene ikke er møtt.

## Teknisk videreføring
Når en rapportør endrer layout, må en spesifikk innhentingsmodul tilpasses og testes. Et publiseringsløp skal aldri bytte konserntall og Norge-tall, tolke HIÅ som kvartalstall eller gjenbruke eldre kvartalsdata under ny kvartalsetikett. Grensesnitt og kildedata oppdateres hver for seg og sammenstilles ved kvalitetssjekken.
