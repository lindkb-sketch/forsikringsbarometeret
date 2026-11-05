# Cloudflare reserveplanlegger for aksjekurser

Dette er en **valgfri reserve**, ikke en erstatning for GitHub Actions. GitHub fortsetter å hente, validere og publisere kurser. Cloudflare kontrollerer hvert 15. minutt (fem minutter etter GitHub-planen) om GitHub har startet en vellykket eller aktiv kjøring de siste 20 minuttene. Hvis ikke, sendes `workflow_dispatch` til `stock-prices.yml`.

## Aktivering (krever Cloudflare-konto)

1. Installer Wrangler lokalt med `npx wrangler login` og gå til denne mappen.
2. Lag et **finkornet GitHub-token** begrenset til repositoriet `lindkb-sketch/forsikringsbarometeret`, med **Actions: Read and write**. Ingen Contents- eller admin-rettigheter kreves for reserveplanleggeren.
3. Lagre tokenet som en hemmelighet: `npx wrangler secret put GITHUB_TOKEN`. Ikke legg tokenet i Git, logger eller chat.
4. Kjør `npx wrangler deploy` fra denne mappen og bekreft at cron-triggeren er aktiv i Cloudflare.
5. Kontroller Worker-logger og GitHub Actions-historikk etter første planlagte tidspunkt. Deaktiver Worker-triggeren hvis du opplever doble starter.

Cloudflare Workerens oppgaver krever ikke at nettstedet flyttes fra GitHub Pages. Dette oppsettet er ikke aktivt før eieren har gjennomført deploy og lagt inn hemmeligheten.

## Sikkerhet og begrensninger

- Ingen offentlige HTTP-endepunkter er aktivert (`workers_dev = false`).
- GitHub API-feil stopper reservejobben; den sender ikke en blind ny dispatch.
- Arbeidstid kontrolleres i nordiske tidssoner. Børshelligdager kontrolleres fortsatt av datakilden, og den eksisterende GitHub-workflowen avgjør om data kan publiseres.
- GitHub `workflow_dispatch` overstyrer workflowens eksisterende tidsvindusfilter. Reservejobben må derfor selv kontrollere tidsvinduet, slik koden gjør.
- GitHub Actions er ikke sanntidsdataleverandør; forsinkede markedsdata merkes fortsatt som forsinkede.
