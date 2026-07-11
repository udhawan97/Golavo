---
title: Coverage
description: The exact data coverage implemented by Phase 0, with gaps stated explicitly.
---

Phase 0 is intentionally narrow: **men's senior full internationals only**. It vendors a pinned snapshot of `martj42/international_results` under CC0-1.0. The snapshot is reproducible, not live.

**Phase 1** adds one club competition — the **English Premier League** — as a **historical** backbone from a pinned `openfootball` snapshot (CC0-1.0), accepted only for **completed seasons** after a coverage audit. It is reproducible and backtested, **not live**.

**Phase 2** extends the same pinned `openfootball` snapshot to the rest of the men's **top-5 European leagues** — **La Liga, Bundesliga, Serie A, and Ligue 1** — each gated by its own per-league audit verdict, each **historical only**. Every league is modeled independently from its own pack: domestic season files carry no inter-league matches, so there is **no cross-league strength calibration** and strengths are not comparable across leagues.

**Phase 3** adds the forward sealed-forecast loop — for **internationals only**. `martj42/international_results` is CC0, refreshes within days, and carries upcoming fixtures as scheduled rows, so a real fixture can be sealed before its (day-proxy) kickoff and scored from a later retained snapshot. The openfootball club packs are season-lagged captures with no verified live cadence, so a **club forward loop is an explicit non-goal** — club coverage stays historical backtesting. The source publishes dates without kickoff times, so seals close at a conservative 00:00 UTC day-before cutoff; snapshots are immutable, retained, and registered in `packs/snapshots.json`. See [The Prediction Ledger](/Golavo/prediction-ledger/).

## Phase 0 coverage

| Data type | Coverage | Engine use |
|---|---|---|
| Full-international results | date, teams, score, tournament, city, country, neutral flag | ✅ ingest, train, evaluate, seal, score |
| Former team names | dated former/current name intervals | ✅ canonicalize historical rows |
| International goalscorers | scorer, minute, own-goal, penalty | snapshot only; out of Phase 0 modeling |
| Shootouts | winner and first shooter | snapshot only; 1X2 regulation model does not use shootouts |
| Club fixtures/results (English Premier League) | 15 clean seasons 2010-11 → 2024-25 (openfootball, CC0) | ✅ Phase 1 historical backtest (not live) |
| Club fixtures/results (La Liga) | 12 clean seasons 2012-13 → 2023-24 (openfootball, CC0) | ✅ Phase 2 historical backtest (not live) |
| Club fixtures/results (Bundesliga) | 15 clean seasons 2010-11 → 2024-25 (openfootball, CC0) | ✅ Phase 2 historical backtest (not live) |
| Club fixtures/results (Serie A) | 11 clean seasons 2013-14 → 2023-24 (openfootball, CC0) | ✅ Phase 2 historical backtest (not live) |
| Club fixtures/results (Ligue 1) | 10 clean seasons 2014-15 → 2024-25 (openfootball, CC0) | ✅ Phase 2 historical backtest (not live) |
| Lineups / minutes | no accepted open source | 🚫 unavailable |
| Injuries / suspensions | no accepted open source | 🚫 unavailable |
| Corners / shots / cards | no accepted open source | 🚫 unavailable |
| xG | no accepted open source | 🚫 unavailable |

Transfermarkt-derived and DataHub football datasets are rejected. Their downstream CC0/PDDL labels do not cure upstream ToS and database-provenance risk. European Soccer DB, `eatpizzanot`, Understat, FBref, Sofascore, FotMob, and unofficial FPL endpoints are also outside the accepted source set.

## Phases 1–2 coverage (club — historical)

The men's top-5 European leagues are accepted for **completed seasons only**, from one pinned `openfootball` snapshot (CC0-1.0), after the per-league [coverage audit](https://github.com/udhawan97/Golavo/blob/main/docs/handoff/openfootball-audit.md). A season is clean only if it is a complete double round-robin at the league's constitutional size with every result present. Live in-season club forecasting is **not certified** — openfootball's live cadence is unverified until a season is observed updating.

| League | Verdict | Clean seasons | Excluded, and why |
|---|---|---|---|
| English Premier League | ACCEPT_HISTORICAL | 15 (2010-11 → 2024-25) | 2025-26 partial capture (27 unfinalized `[0, 0]`-encoded results) |
| La Liga | ACCEPT_HISTORICAL | 12 (2012-13 → 2023-24) | 2024-25 missing its final matchday (10 results); 2025-26 partial capture |
| Bundesliga | ACCEPT_HISTORICAL | 15 (2010-11 → 2024-25) | 2025-26 partial capture |
| Serie A | ACCEPT_HISTORICAL | 11 (2013-14 → 2023-24) | 2024-25 missing its final matchday (10 results); 2025-26 partial capture |
| Ligue 1 | ACCEPT_HISTORICAL | 10 (2014-15 → 2024-25) | 2019-20 abandoned in the COVID-19 pandemic (101 fixtures unplayed); 2025-26 partial capture |

Missing results are **excluded, never fabricated**. Ligue 1 contracted from 20 to 18 clubs in 2023-24; the audit derives each season's expected match count from its actual team count and also checks that count against the league's constitutional size.

The same five candidate models are backtested on each league's three most recent clean seasons as strictly chronological folds (EPL, Bundesliga, Ligue 1: 2022-23 → 2024-25; La Liga, Serie A: 2021-22 → 2023-24). Every candidate beats the climatological baseline on log loss on every fold; the best model varies by fold and no model is crowned a champion. Each league is modeled independently — there is no cross-league strength calibration.

Phase 0 evaluation uses strictly chronological World Cup 2022, Euro 2024, and World Cup 2026 tournament windows. These are test folds, not promises of a live fixture service.

See [Sources & licenses](/Golavo/data/sources/) for the source manifest contract and rejected-source rationale.
