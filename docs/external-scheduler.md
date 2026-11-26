# Independent recovery scheduler

The existing GitHub schedule and watchdogs are best effort. The optional Render
cron blueprint in the root runs the same project recovery tick outside GitHub
Actions every five minutes. It requests the existing validated finance workflow
when the most recent main attempt is 30 minutes old (10 minutes after failure);
the stock watchdog runs only in Nordic weekday market windows and guards
against an existing/recent attempt. It does not fetch or publish data itself.

## Activate (owner approval and external account required)

1. Merge this PR only after regression checks pass.
2. Use an independent scheduler: import the root render.yaml Blueprint into your
   Render account, or configure a trusted existing server with a single locked
   cron entry running python3 scripts/external_scheduler.py every five minutes.
   Render Cron Jobs are a paid service; review pricing before creating resources.
3. Supply GITHUB_TOKEN using the provider secret manager, scoped only to this
   repository, Actions read/write and default metadata read. Do not grant
   contents write, paste a token into chat, or commit it. Rotate/revoke as needed.
4. Before enabling writes run python scripts/external_scheduler.py --dry-run
   with the credential in the environment; verify both workflow histories.
5. Enable provider failure notifications, verify repeated successful ticks,
   confirm an intentionally missed scheduled run is recovered (without
   disabling the main schedule), and inspect GitHub job outcomes and public
   data parity. No unverified financial observations may be admitted.

The script checks both tasks even if one fails and exits nonzero on errors.
An already active finance run older than 60 minutes is an error for inspection,
not permission to launch an overlapping run. After HTTP 5xx re-read run history
before retrying. Run only one external scheduler instance. GitHub and external
dispatches can still race; the existing shared publication lock must remain.
No hard 15- or 30-minute SLA is asserted: GitHub queue delays, provider
downtime and source changes can still prevent completion.

No external account, credential or paid resource is created by this PR.
