# Privat megleranalyse – oppsett og drift

Dette er en separat, autentisert Cloudflare Worker. Den offentlige nettsiden fortsetter på GitHub Pages. PDF-ene lagres i privat Cloudflare R2, med metadata/utkast i D1. Cloudflare Queue kjører OpenAI-analyse. Kun et sammendrag som administrator har godkjent, publiseres til data/broker_commentary.json.

## Brukerflyt

1. Administrator logger inn med Cloudflare Access og må være oppført i e-post-tillatelseslisten.
2. Velg selskap og kvartal. Mapper opprettes automatisk når et nytt, verifisert konsernkvartal finnes i finansfeeden.
3. Last opp tillatte PDF-er (maks 10 MiB per fil, 20 per selskap/kvartal). Du må bekrefte at rettighetene tillater privat AI-behandling hos OpenAI.
4. Queue behandler dokumentene automatisk og lager et samlet AI-utkast for selskapet og kvartalet.
5. Kontroller og rediger teksten; trykk «Godkjenn og publiser». Kun feltene reaction, drivers, outlook og selskaps-/kvartalsmetadata publiseres. Original-PDF-er, filnavn og interne analyser publiseres aldri.

**Koden er foreløpig ikke en aktivert tjeneste.** Drift krever kontoressurser og hemmelige nøkler som ikke er tilgjengelige gjennom GitHub-tilkoblingen. Ikke legg nøkler i Git eller i chat.

## Aktivering i privat Cloudflare-konto

Først: Kontroller meglerhusenes konfidensialitets- og bruksvilkår. AI-behandling av rapportene må være tillatt. Avklar databehandleravtale og retensjon med leverandøren ved behov.

1. Bruk en Cloudflare-konto med Workers, R2, D1, Queues og Zero Trust Access. Opprett en Access-applikasjon som beskytter den endelige Worker-URL-en og eventuelle preview-adresser. Kun dine e-postadresser skal ha tilgang.
2. Kjør i mappen broker-admin:
    npm install
    npx wrangler login
    npx wrangler r2 bucket create forsikringsbarometeret-broker-private
    npx wrangler d1 create forsikringsbarometeret-broker-db
    npx wrangler queues create forsikringsbarometeret-broker-analysis
    npx wrangler queues create forsikringsbarometeret-broker-deadletter
3. Erstatt database_id med UUID-en fra D1-opprettelsen i wrangler.toml. La R2-bøtten være privat; aktiver aldri r2.dev/offentlig domene.
4. Kjør npm test og npm run check, deretter:
    npx wrangler d1 migrations apply forsikringsbarometeret-broker-db --remote
5. Legg inn følgende med npx wrangler secret put NAVN eller Workers-dashboard:
    ACCESS_TEAM_DOMAIN = team-domene.cloudfareaccess.com, uten protokoll (bruk det faktiske Cloudflare-teamdomenet)
    ACCESS_AUD = Cloudflare Access-applikasjonens AUD-tag
    ADMIN_EMAILS = komma-separert liste med tillatte e-poster
    OPENAI_API_KEY = OpenAI API-prosjektnøkkel
    GITHUB_TOKEN = finavgrenset token med Contents Read/Write kun for lindkb-sketch/forsikringsbarometeret
   (Cloudflare-teamdomenet slutter normalt med cloudflareaccess.com.)
6. Kjør npx wrangler deploy. Verifiser at uautoriserte og utløpte innlogginger får avslag, og at en godkjent konto får tilgang.
7. Test med en ikke-konfidensiell PDF du har rett til å bruke. Bekreft at Queue lager utkast og at ingen tekst publiseres før du trykker «Godkjenn».
8. Etter vellykket test, sett enabled=true og url til din faktiske, Access-beskyttede HTTPS-arbeideradresse i data/broker_admin_config.json på main. Lenken blir synlig i nettstedets ?admin=1-visning. Ingen hemmelig verdi legges i denne offentlige konfigurasjonsfilen.

## Sikkerhet og driftskrav

- Adminlenken på den offentlige siden er ikke autentisering. Kun Cloudflare Access, validering av signert JWT/AUD/issuer/e-post og same-origin-kontroll håndterer tilgang.
- PDF-er forblir i private R2-objekter. Ingen PDF-nedlastingsrute finnes på den offentlige nettsiden. Unngå offentlig R2-domene.
- Originalrapportene sendes til OpenAI for analyse bare ved eksplisitt tillatelse. API-et bruker store:false, men det er IKKE en garanti for null lagring hos leverandøren; se API-avtale og retensjonsvilkår.
- AI-genererte sammendrag kan ha feil. Godkjenning av et menneske er obligatorisk. Ikke gjengi lange sitater fra proprietære meglerhusrapporter.
- Nye PDF-er gjør tidligere utkast foreldet, og publisering krever ferdiganalyserte rapporter i mappen. Ved feil kan administrator forsøke igjen.
- D1/R2 trenger egen backup-, retensjons-, nøkkelrotasjons- og tilgangskontroll. Slettes en PDF, beholdes et allerede godkjent offentlig sammendrag inntil det endres bevisst.
- Et GitHub-token som skriver direkte på main kan bli blokkert av branch-protection; bruk i så fall et PR-basert godkjenningsløp før produksjon.
- Godkjenning oppdaterer kun data/broker_commentary.json. GitHub Pages republiseres via eksisterende publiseringsjobb; det kan ta flere minutter før teksten er synlig.

**Fullført i drift først når ressursene er opprettet, hemmelige innstillinger er satt inn og en ende-til-ende-test med ekte innlogging, AI-behandling og publisering er bestått.**
