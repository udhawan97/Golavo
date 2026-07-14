---
title: Roadmap
description: The capabilities that still remain, with entry criteria and kill switches stated before implementation.
---

Golavo is useful today and nowhere near finished. The deterministic engine, historical
top-5 league backtests, international forward loop, desktop distribution, signed in-app
updater, optional guarded AI, facts, exact scores, Match Cockpit, Model Lab, and My Season
are already implemented. They are documented as current product behavior instead of being
carried forward as future roadmap items.

## Remaining work

| Workstream | What remains | Entry / kill criterion |
|---|---|---|
| **Live club forecasting** | User-initiated live fixture refresh and a club seal→score loop | Enter only after a lawful source proves its license, cadence, fixture identity, and cutoff semantics. Kill if those cannot be verified without redistributing restricted data. |
| **League Outlook** | Current standings and season projections in the browse hub | Requires complete, validated live season state and forward-tested projection quality. No complete state means no projection. |
| **Observed match data** | Optional lineups, injuries, xG, scorers, corners, and cups as typed features | Every field needs a lawful licensed source, retrieval timestamp, provenance record, and evidence that it improves forward metrics. Otherwise defer it. |
| **Ledger longevity** | Cross-artifact hash chaining, verification, and migration tooling | Must preserve and recover every existing local ledger before the format changes. |
| **Distribution trust** | OS-signed Windows installers and signed/notarized macOS releases | Requires real credentials plus a green install/update/rollback matrix on both platforms. |
| **Product reach** | Team/player/manager dossiers, signed community packs, i18n, and opt-in license-isolated overlays | Each source and pack format needs its own license review, isolation boundary, and failure tests. |

Each remaining workstream needs explicit entry/exit criteria, tests, a defer list, and a
kill switch before implementation. No fabricated capabilities ship: live club fixtures,
standings, season projections, and observed xG/lineups/injuries are **not** in the product today.
