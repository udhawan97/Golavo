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
The women-first World Cup history archive and current Frauen-Bundesliga OpenLigaDB
display overlay are also current product behavior, not future promises. Golavo additionally
has My Teams, exact-time followed-match calendar export, Trust Center proof
inspection and allowlisted archive/restore, data-application receipts, local ledger
checkpoints, guarded calibration slices, a checkpoint-continuity archive that accepts
legacy backups and rehearses recovery before mutation, the Match Study Desk, final-player-stat
foreground wording and a bounded provider-backed Transfer Desk. Source `main` additionally
contains Unreleased exact-identity team dossiers that separate observed record, every
season-model voice as one complete comparison, and competition-scoped evidence; the installed
v0.19.0 release does not. The same source build can open an exact-provider-identity,
selected-match player dossier from an already-fetched Sportmonks Player Lens response. That
reading stays in memory and does not become a persistent player profile or form series.

## Remaining work

| Workstream | What remains | Entry / kill criterion |
|---|---|---|
| **Live club settlement** | Add a second independent result source so club seals can grade automatically | Eight approved repositories now refresh international and current big-five league state while the app is open. One domestic Football.TXT result remains one source; settlement stays pending until an independent source agrees. |
| **Future league continuity** | Carry the allowlisted country-repository adapters into each genuinely published season | Every new season must pass the same exact-path, license, provenance, identity, result, and complete-schedule gates. Absence or partial publication remains last-known-good, never inferred completeness. |
| **Observed match data** | Multi-match player form plus optional injuries, xG, scorers, corners, cards, and cups as typed features. One-match Sportmonks player context already exists but is display-only. | Every model field needs a lawful point-in-time corpus, retrieval timestamp, provenance record, leakage controls, target-specific evaluation, and evidence that it improves forward metrics. Otherwise defer it. |
| **Transfer payment evidence** | Add transaction-specific payment components only where a primary club or issuer disclosure supplies them | Keep the current provider amount as free text. Currency, installments, add-ons, sell-ons, agent fees, training rewards, and conditional consideration remain unknown until each exact source is reviewed. |
| **Optional external checkpoint anchoring** | Decide whether an independent, opt-in anchor is worthwhile beyond local migration and recovery | Requires a provider-independent design, explicit privacy/retention/revocation policy, and proof that local-only operation remains complete. A local chain must never be described as external authenticity or timing proof. |
| **Distribution trust** | OS-signed Windows installers and signed/notarized macOS releases | Requires real credentials plus a green install/update/rollback matrix on both platforms. |
| **Product reach** | Persistent multi-match player profiles, manager dossiers, community packs, and i18n. Exact-identity team dossiers and no-store selected-match player dossiers exist on source `main` as Unreleased work. | Each additional source and pack format needs its own license review, isolation boundary, signature policy, and failure tests. Current-manager claims stay absent until a revision-pinned tenure source exists. |
| **Closed-app monitoring** | Optional, user-visible helper architecture, if users actually want it | Separate approval, explicit install/remove UX, power/network budgets, OS permission review, and no impact on the honest while-open v1. |

Each remaining workstream needs explicit entry/exit criteria, tests, a defer list, and a
kill switch before implementation. No fabricated capabilities ship: independent club
settlement and observed xG/lineups/injuries are **not** in the product today.
