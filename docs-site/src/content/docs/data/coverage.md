---
title: Coverage
description: The exact data coverage implemented by Phase 0, with gaps stated explicitly.
---

Phase 0 is intentionally narrow: **men's senior full internationals only**. It vendors a pinned snapshot of `martj42/international_results` under CC0-1.0. The snapshot is reproducible, not live.

## Phase 0 coverage

| Data type | Coverage | Engine use |
|---|---|---|
| Full-international results | date, teams, score, tournament, city, country, neutral flag | ✅ ingest, train, evaluate, seal, score |
| Former team names | dated former/current name intervals | ✅ canonicalize historical rows |
| International goalscorers | scorer, minute, own-goal, penalty | snapshot only; out of Phase 0 modeling |
| Shootouts | winner and first shooter | snapshot only; 1X2 regulation model does not use shootouts |
| Club fixtures/results | — | 🚫 out of Phase 0 |
| Lineups / minutes | no accepted open source | 🚫 unavailable |
| Injuries / suspensions | no accepted open source | 🚫 unavailable |
| Corners / shots / cards | no accepted open source | 🚫 unavailable |
| xG | no accepted open source | 🚫 unavailable |

Transfermarkt-derived and DataHub football datasets are rejected. Their downstream CC0/PDDL labels do not cure upstream ToS and database-provenance risk. European Soccer DB, `eatpizzanot`, Understat, FBref, Sofascore, FotMob, and unofficial FPL endpoints are also outside the accepted source set.

Phase 0 evaluation uses strictly chronological World Cup 2022, Euro 2024, and World Cup 2026 tournament windows. These are test folds, not promises of a live fixture service.

See [Sources & licenses](/Golavo/data/sources/) for the source manifest contract and rejected-source rationale.
