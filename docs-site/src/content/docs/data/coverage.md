---
title: Coverage
description: Golavo's exact data coverage across internationals, the top-5 leagues, and UEFA club competitions, with gaps stated explicitly.
---

Golavo's **forward** forecasting surfaces are men's senior full internationals and fixtures in
the five pinned 2026–27 domestic schedules. Internationals use retained snapshots of
`martj42/international_results` under CC0-1.0, so a fixture can be sealed before its conservative
day-proxy kickoff and scored from a later snapshot. Club fixtures use the published OpenFootball
schedule for identity and cutoff-safe training from that league's own results; automatic grading
requires two independent result sources to agree, so a one-source result remains pending.

The **English Premier League, La Liga, Bundesliga, Serie A, and Ligue 1** use a pinned
`openfootball` history (CC0-1.0) plus separately pinned 2026–27 schedules. Only completed seasons
that pass the per-league coverage audit train a model; future scheduled rows never do. Every
league is modeled independently, so there is **no cross-league strength calibration** and
strengths are not comparable across leagues.

The **UEFA Champions League, Europa League, and Conference League** are also
historical-only. Their main-competition editions come from a separately pinned
`openfootball/champions-league` commit (CC0-1.0). Qualifiers are excluded, and each
competition has its own explicit coverage ceiling. These matches power browsing plus
competition-local strength and rest/congestion analytics, not report cards or season
simulations.

The pinned domestic schedules make a bounded club forward loop possible without claiming a live
feed: they supply fixture identity and local kickoff only, never training truth. The general
international source publishes dates without kickoff times, so those seals close at a conservative
00:00 UTC day-before cutoff; the pinned World Cup 2026 overlay carries exact kickoffs for its
fixtures. Snapshots are immutable, retained, and registered in `packs/snapshots.json`. See
[The Prediction Ledger](/Golavo/prediction-ledger/).

## Coverage by data type

| Data type | Coverage | Engine use |
|---|---|---|
| Full-international results | date, teams, score, tournament, city, country, neutral flag | ✅ ingest, train, evaluate, seal, score |
| Former team names | dated former/current name intervals | ✅ canonicalize historical rows |
| International goalscorers | scorer, minute, own-goal, penalty | snapshot only; not used by the forecast model |
| Shootouts | winner and first shooter | snapshot only; 1X2 regulation model does not use shootouts |
| Club fixtures/results (English Premier League) | accepted completed history plus a certified 2026–27 schedule (openfootball, CC0) | ✅ train/backtest on completed history; seal scheduled fixtures; two-source grading |
| Club fixtures/results (La Liga) | accepted completed history plus a certified 2026–27 schedule (openfootball, CC0) | ✅ train/backtest on completed history; seal scheduled fixtures; two-source grading |
| Club fixtures/results (Bundesliga) | accepted completed history plus a certified 2026–27 schedule (openfootball, CC0) | ✅ train/backtest on completed history; seal scheduled fixtures; two-source grading |
| Club fixtures/results (Serie A) | accepted completed history plus a certified 2026–27 schedule (openfootball, CC0) | ✅ train/backtest on completed history; seal scheduled fixtures; two-source grading |
| Club fixtures/results (Ligue 1) | accepted completed history plus a certified 2026–27 schedule (openfootball, CC0) | ✅ train/backtest on completed history; seal scheduled fixtures; two-source grading |
| UEFA Champions League results | 6 complete main-competition editions 2020-21 → 2025-26 (openfootball, CC0) | ✅ browse + competition-local strength/rest analytics |
| UEFA Europa League results | 5 complete main-competition editions 2020-21 → 2024-25 (openfootball, CC0) | ✅ browse + competition-local strength/rest analytics |
| UEFA Conference League results | 4 complete main-competition editions 2021-22 → 2024-25 (openfootball, CC0) | ✅ browse + competition-local strength/rest analytics |
| World Cup 2026 fixture overlay | exact knockout kickoffs and bracket context (openfootball, CC0) | ✅ seal timing + exact four-team outlook; excluded from model training |
| Historical event research | 1,941 matches / 3,251,294 events: 2017/18 big five, Euro 2016, World Cup 2018 (Pappalardo/Wyscout, CC BY 4.0) | ✅ isolated team-only summaries; never train, seal, or simulate |
| Conditions context | city, timezone, elevation, rest, travel routes (GeoNames + Natural Earth) | ✅ display only; not a model input |
| Pre-kickoff weather | user-triggered Open-Meteo forecast for an eligible upcoming fixture | ✅ retained only when fetched before kickoff; display only; never a model input |
| Historical weather forecasts | no accepted issued-before-kickoff source | 🚫 blocked; observed weather is not substituted |
| Club half-time scores | recorded on many rows across EPL/Bundesliga 2010-11 → 2025-26, La Liga 2012-13 → 2025-26, Serie A 2013-14 → 2025-26, and Ligue 1 2014-15 → 2025-26 | ✅ descriptive comeback/lead facts only; missing HT rows are excluded |
| Men's World Cup history | tournaments, standings, team appearances, and individual awards, 1930–2022 (Fjelstul, CC-BY-SA-4.0) | ✅ isolated descriptive facts only; never joined to the forecast index |
| Lineups / minutes | no accepted open source | 🚫 unavailable |
| Injuries / suspensions | no accepted open source | 🚫 unavailable |
| Live corners / shots / cards | no accepted open source | 🚫 unavailable; historical research shot rates are era-scoped separately |
| Observed xG | no accepted open source | 🚫 unavailable; Golavo's historical research xT is not xG |

Transfermarkt-derived and DataHub football datasets are rejected. Their downstream CC0/PDDL labels do not cure upstream ToS and database-provenance risk. European Soccer DB, `eatpizzanot`, Understat, FBref, Sofascore, FotMob, and unofficial FPL endpoints are also outside the accepted source set.

## Historical club coverage

The men's top-5 European leagues are accepted for **completed seasons only**, from pinned
CC0-1.0 OpenFootball data after the per-league
[coverage audit](https://github.com/udhawan97/Golavo/blob/main/docs/handoff/openfootball-audit.md).
Premier League history before 2010-11 and Bundesliga history before 2010-11 come from the
footballcsv flat-file mirror; the later seasons come from football.json. The ranges do not
overlap. A season is clean only if it is a complete double round-robin at the league's
constitutional size with every result present. Live in-season club forecasting is **not
certified** — openfootball's live cadence is unverified until a season is observed updating.

| League | Verdict | Clean seasons | Excluded, and why |
|---|---|---|---|
| English Premier League | ACCEPT_HISTORICAL | 33 (1992-93 → 2024-25) | 2025-26 partial capture (27 unfinalized `[0, 0]`-encoded results) |
| La Liga | ACCEPT_HISTORICAL | 12 (2012-13 → 2023-24) | 2024-25 missing its final matchday (10 results); 2025-26 partial capture |
| Bundesliga | ACCEPT_HISTORICAL | 62 (1963-64 → 2024-25) | 2025-26 partial capture |
| Serie A | ACCEPT_HISTORICAL | 11 (2013-14 → 2023-24) | 2024-25 missing its final matchday (10 results); 2025-26 partial capture |
| Ligue 1 | ACCEPT_HISTORICAL | 10 (2014-15 → 2024-25) | 2019-20 abandoned in the COVID-19 pandemic (101 fixtures unplayed); 2025-26 partial capture |

Missing results are **excluded, never fabricated**. Ligue 1 contracted from 20 to 18 clubs in 2023-24; the audit derives each season's expected match count from its actual team count and also checks that count against the league's constitutional size.

## Historical UEFA club coverage

Golavo retains 2,271 declared main-competition rows from the pinned European source.
The parser reconciles every row against the count embedded in its season file and fails
closed on unrecognized match syntax. Two cancelled 2021-22 Europa League ties remain in
the hashed source bytes for auditability but are excluded from the match index, leaving
2,269 complete results.

| Competition | Included editions | Indexed results | Not included |
|---|---:|---:|---|
| UEFA Champions League | 2020-21 → 2025-26 | 878 | qualifiers; future schedules beyond the pin |
| UEFA Europa League | 2020-21 → 2024-25 | 815 | 2 cancelled ties; qualifiers; 2025-26 main competition |
| UEFA Conference League | 2021-22 → 2024-25 | 576 | qualifiers; 2025-26 main competition |

Upstream supplies venue-local clock labels without timezones. Golavo therefore indexes
these rows at a day-only 00:00 UTC proxy and does not present the local clock as an exact
kickoff. Complete historical editions do **not** certify a future fixture feed, schedule
difficulty, report card, or tournament simulation. Those capabilities remain partial,
planned, or blocked in the competition catalog.

Half-time coverage is **row-level, not season-complete**. The openfootball files carry a recorded
`score.ht` for many matches in every packed club season, but gaps remain — especially in older
history, and also in partial recent captures. The Second-half story therefore counts only matches
with two valid half-time scores. It never infers a half-time result from the final score.

The same five candidate models are backtested on each league's three most recent clean seasons as strictly chronological folds (EPL, Bundesliga, Ligue 1: 2022-23 → 2024-25; La Liga, Serie A: 2021-22 → 2023-24). Every candidate beats the climatological baseline on log loss on every fold; the best model varies by fold and no model is crowned a champion. Each league is modeled independently — there is no cross-league strength calibration.

International evaluation uses strictly chronological World Cup 2022, Euro 2024, and World Cup 2026 tournament windows. These are test folds, not promises of a live fixture service.

See [Sources & licenses](/Golavo/data/sources/) for the source manifest contract and rejected-source rationale.
