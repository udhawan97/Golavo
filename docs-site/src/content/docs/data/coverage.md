---
title: Coverage
description: The exact data coverage implemented by Phase 0, with gaps stated explicitly.
---

Phase 0 is intentionally narrow: **men's senior full internationals only**. It vendors a pinned snapshot of `martj42/international_results` under CC0-1.0. The snapshot is reproducible, not live.

**Phase 1** adds one club competition — the **English Premier League** — as a **historical** backbone from a pinned `openfootball` snapshot (CC0-1.0), accepted only for **completed seasons** after a coverage audit. It is reproducible and backtested, **not live**.

## Phase 0 coverage

| Data type | Coverage | Engine use |
|---|---|---|
| Full-international results | date, teams, score, tournament, city, country, neutral flag | ✅ ingest, train, evaluate, seal, score |
| Former team names | dated former/current name intervals | ✅ canonicalize historical rows |
| International goalscorers | scorer, minute, own-goal, penalty | snapshot only; out of Phase 0 modeling |
| Shootouts | winner and first shooter | snapshot only; 1X2 regulation model does not use shootouts |
| Club fixtures/results (English Premier League) | 15 clean seasons 2010-11 → 2024-25 (openfootball, CC0) | ✅ Phase 1 historical backtest (not live) |
| Lineups / minutes | no accepted open source | 🚫 unavailable |
| Injuries / suspensions | no accepted open source | 🚫 unavailable |
| Corners / shots / cards | no accepted open source | 🚫 unavailable |
| xG | no accepted open source | 🚫 unavailable |

Transfermarkt-derived and DataHub football datasets are rejected. Their downstream CC0/PDDL labels do not cure upstream ToS and database-provenance risk. European Soccer DB, `eatpizzanot`, Understat, FBref, Sofascore, FotMob, and unofficial FPL endpoints are also outside the accepted source set.

## Phase 1 coverage (club — historical)

The English Premier League is accepted for **completed seasons only**, from a pinned `openfootball` snapshot (CC0-1.0), after the [coverage audit](https://github.com/udhawan97/Golavo/blob/main/docs/handoff/openfootball-audit.md). The audit found **15 clean seasons** (2010-11 → 2024-25), each a complete 380-match double round-robin; the partial 2025-26 capture (27 results absent at snapshot time, encoded as a divergent `[0, 0]`) is **excluded** and never fabricated. Live in-season club forecasting is **not certified** — openfootball's live cadence is unverified until a season is observed updating.

The same five candidate models are backtested on strictly chronological EPL 2022-23, 2023-24, and 2024-25 season folds. Every candidate beats the climatological baseline on log loss on all three folds; no model is crowned a champion.

Phase 0 evaluation uses strictly chronological World Cup 2022, Euro 2024, and World Cup 2026 tournament windows. These are test folds, not promises of a live fixture service.

See [Sources & licenses](/Golavo/data/sources/) for the source manifest contract and rejected-source rationale.
