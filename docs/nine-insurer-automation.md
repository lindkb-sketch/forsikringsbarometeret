# Nine-insurer operational controls

The production pipeline already has source-specific importers for Fremtind, Gjensidige, Tryg, Sampo/If, Frende, Protector, Storebrand, KLP Skadeforsikring and Alm. Brand. KLP and Alm. Brand use the separate extended issuer dataset, not the seven-company group feed.

- The release gate checks each issuer's latest verified quarter and HIÅ, with documented reporting exceptions, and fails if an official dated release is missing after 48 hours. Different release dates are allowed. An unknown release date is a warning, not confirmation that no report exists. The existing archive polling must continue.
- The production deployment records a per-run artifact showing all nine before/after periods, public data parity and whether a new period actually advanced on a scheduled run. No change, a manual dispatch, or a populated old snapshot is not proof of unattended new-quarter extraction.
- The independent quarterly release watchdog uses the correct nine-company comparison and keeps the older segment checks for the seven-company feed.
- Stock recovery retries transient dispatch errors only after rechecking run history. A stock API error does not block the finance importer.

## Independent scheduler (not installed by this pull request)

GitHub Actions cron and GitHub-hosted timers can both be delayed. On a separate trusted scheduler or host, run the following from a checkout of the reviewed main branch, with a repository-scoped credential supplied via its secret manager (Actions read/write, no contents write required):

```cron
*/5 * * * * cd /path/to/forsikringsbarometeret && python3 scripts/check_scheduled_runs.py
*/5 * * * * cd /path/to/forsikringsbarometeret && python3 scripts/check_stock_schedule.py
```

Use an external mutual-exclusion mechanism for each task, refresh the checkout safely, alert on failure, and never commit the credential. The existing guards reduce duplicate dispatches but an external scheduler and GitHub cron can still race; the publication concurrency controls remain required. These checks are recovery mechanisms, not a guarantee of a strict 15-/30-minute service level.

## Acceptance

Require a green PR regression, the scheduled nine-company watchdog, a production publication and its receipt. For every newly released quarter verify all nine issuer-specific source and metric audits, comparison and published JSON, and retain run links and evidence. Unconfirmed calendars and incomplete dual-document reconciliation remain outstanding; do not mark investor-ready based on these controls alone.
