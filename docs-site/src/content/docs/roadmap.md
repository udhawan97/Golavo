---
title: Roadmap
description: The capabilities that still remain, with entry criteria and kill switches stated before implementation.
---

Golavo is useful today and nowhere near finished. The deterministic engine, historical
top-5 league backtests, international forward loop, desktop distribution, signed in-app
updater, optional guarded AI, facts, exact scores, Match Cockpit, Model Lab, My Season,
competition-local analytics, verified standings rules, the World Cup outlook, Conditions
Snapshot, and historical team research are already implemented. They are documented as
current product behavior instead of being carried forward as future roadmap items. The same is
true of approved-source refresh, the optional ODbL-isolated OpenLigaDB display overlay, local
followed-match checks, provenance-first corrections, selected-source research, and deterministic
history-support/model-gap/capability explanations, portable proof downloads, forecast
readiness, verified-generation diffs, and ephemeral conditional season scenarios.

## Remaining work

| Workstream | What remains | Entry / kill criterion |
|---|---|---|
| **Live club settlement** | Add a second independent result source so club seals can grade automatically | Eight approved repositories now refresh international and current big-five league state while the app is open. One domestic Football.TXT result remains one source; settlement stays pending until an independent source agrees. |
| **Future league continuity** | Carry the allowlisted country-repository adapters into each genuinely published season | Every new season must pass the same exact-path, license, provenance, identity, result, and complete-schedule gates. Absence or partial publication remains last-known-good, never inferred completeness. |
| **Observed match data** | Optional lineups, injuries, xG, scorers, corners, and cups as typed features | Every field needs a lawful licensed source, retrieval timestamp, provenance record, and evidence that it improves forward metrics. Otherwise defer it. |
| **Ledger longevity** | Cross-artifact hash chaining, verification, and migration tooling | Must preserve and recover every existing local ledger before the format changes. |
| **Distribution trust** | OS-signed Windows installers and signed/notarized macOS releases | Requires real credentials plus a green install/update/rollback matrix on both platforms. |
| **Product reach** | Team/player/manager dossiers, community packs, and i18n | Each source and pack format needs its own license review, isolation boundary, signature policy, and failure tests. Current-manager claims stay absent until a revision-pinned tenure source exists. |
| **Closed-app monitoring** | Optional, user-visible helper architecture, if users actually want it | Separate approval, explicit install/remove UX, power/network budgets, OS permission review, and no impact on the honest while-open v1. |

Each remaining workstream needs explicit entry/exit criteria, tests, a defer list, and a
kill switch before implementation. No fabricated capabilities ship: independent club
settlement and observed xG/lineups/injuries are **not** in the product today.
