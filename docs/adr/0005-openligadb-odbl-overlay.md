# ADR-0005: isolate OpenLigaDB as an optional display-only ODbL overlay

Status: accepted for implementation (2026-07-15)

Golavo may fetch current-season OpenLigaDB data only after explicit user consent.
The service is keyless, community-maintained, and publishes its API data under
ODbL 1.0. Golavo therefore stores every raw response and derived database in a
separate per-user `overlays/openligadb` tree with its own immutable generations,
active pointer, attribution and deletion lifecycle.

The first release allowlisted only `api.openligadb.de`, GET, the four path shapes
recorded in `packs/overlay-odbl/policy.json`, and the `bl1`, `bl2`, `bl3`, `dfb`
shortcuts for the current European season. Arbitrary URLs, team filters, logos,
and community-created competitions are rejected.

Amendment (2026-08-25): the same frozen identity gate now includes `ffb1`, the
current 2026-27 Frauen-Bundesliga shortcut published by OpenLigaDB. The 2025
shortcut `fbl1` is not accepted for the current-season fetch because OpenLigaDB
retired it. This adds women's club coverage without changing any consent,
storage, attribution, identity, export, or display-only boundary in this ADR.

V1 is display-only. It creates no core ids, performs no fuzzy reconciliation,
and cannot feed the CC0 match index, model training, forecast sealing,
settlement, calibration, artifacts or exports. A newer community fact does not
override a CC0 fact. Internal ambiguity or duplicate/conflicting source rows
invalidates the candidate generation; the previous verified generation remains
active.

No helper, LaunchAgent or always-running daemon is installed. Launch and
periodic refresh requests originate in the visible UI and are permitted by the
backend only when the stored overlay policy allows them. Closing Golavo stops
the daemon worker thread and leaves staging inactive.

Operational amendment (2026-08-25): the allowlisted network adapter retries
transient HTTP 429 and 503 responses in place. It honors a valid `Retry-After`
value up to 30 seconds, fails closed when the provider requests a longer wait,
otherwise uses bounded 1/2/4-second backoff, and permits cancellation during
every wait. Attempts, waits, and response reads share a 60-second request budget.
Four failed attempts still fail the candidate closed and preserve the previous
verified generation.
