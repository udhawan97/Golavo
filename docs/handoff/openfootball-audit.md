# openfootball top-league coverage audit (club gate)

- **Source:** openfootball/football.json pinned at `a5dd38b3bcbe3aa2477cf400f569264253d51431` (committed 2026-05-30), CC0-1.0
- **Scope:** men's top-5 European leagues, HISTORICAL completed seasons only — not live
- **Live in-season updating:** UNVERIFIED until the 2026-27 season starts
- **Independent cross-source correctness:** DEFERRED (footballcsv stale to ~2020/21; divergent team names)
- **Cross-league calibration:** NONE — domestic files carry no inter-league matches, so each league is modeled independently and strengths are NOT comparable across leagues

| League | Verdict | Clean seasons | Flagged | Backtest folds |
|---|---|---|---|---|
| Bundesliga | **ACCEPT_HISTORICAL** | 15 (2010-11 → 2024-25) | 2025-26 | 2022-23, 2023-24, 2024-25 |
| English Premier League | **ACCEPT_HISTORICAL** | 15 (2010-11 → 2024-25) | 2025-26 | 2022-23, 2023-24, 2024-25 |
| La Liga | **ACCEPT_HISTORICAL** | 12 (2012-13 → 2023-24) | 2024-25, 2025-26 | 2021-22, 2022-23, 2023-24 |
| Ligue 1 | **ACCEPT_HISTORICAL** | 10 (2014-15 → 2024-25) | 2019-20, 2025-26 | 2022-23, 2023-24, 2024-25 |
| Serie A | **ACCEPT_HISTORICAL** | 11 (2013-14 → 2023-24) | 2024-25, 2025-26 | 2021-22, 2022-23, 2023-24 |

A season is **clean** only when, with n = the actual number of teams in the file:
it has exactly n·(n−1) fixtures, every one carrying a well-formed two-integer
`score.ft`; every team plays exactly n−1 home and n−1 away; there are no
self-matches, duplicate ordered pairs, or negative scores; and n equals the
league's constitutional size for that season (20 for the Premier League, La Liga,
Serie A; 18 for the Bundesliga; 20 for Ligue 1 through 2022-23, 18 from 2023-24 —
the last check catches a season that silently dropped a whole club, which the
derived-n arithmetic alone cannot see).

## Recurring anomalies (why seasons are excluded)

- **Partial 2025-26 captures (every league).** The pin was taken 2026-05-30;
  unfinalized results appear either as a divergent `[0, 0]` LIST encoding (seen
  in no completed season, uniformly zero — the signature of placeholders, not real
  goalless draws) or as empty `{}` scores. Golavo treats both as INCOMPLETE and
  never fabricates them as results.
- **La Liga & Serie A 2024-25.** The entire final Matchday 38 (10 fixtures each,
  played 2025-05-23/25) has empty `{}` scores at this capture — the seasons were
  completed in reality, but this snapshot's record of them is incomplete, so they
  are excluded rather than patched from a second source.
- **Ligue 1 2019-20.** Abandoned early in the COVID-19 pandemic: 101 of 380
  listed fixtures (Matchday 28 onward) were never played. Excluded as a test
  fold; its 279 played matches remain legitimate training evidence.

Incomplete seasons are excluded from the clean set, never fabricated. Played
matches inside them still count as training rows — they really happened; what is
missing is the remainder of the season, which only disqualifies the season as a
*test fold*.

## Bundesliga (`de.1`) — **ACCEPT_HISTORICAL**

- **Pack:** `packs/openfootball-deu-bl`
- **Seasons vendored:** 16
- **Clean seasons:** 15 (2010-11 → 2024-25)
- **Flagged seasons:** 2025-26
- **Backtest folds (3 most recent clean):** 2022-23, 2023-24, 2024-25

| Criterion | Result | Basis |
|---|---|---|
| Usable clean seasons (≥10) | PASS | 15 complete double-round-robin seasons |
| Structural consistency (all seasons) | PASS | no self-matches, negative scores, duplicate ordered pairs, or team-count mismatches |
| Latest clean season present | PASS | 2024-25 |
| Three recent clean folds | PASS | 2022-23, 2023-24, 2024-25 |

**Excluded seasons and why:**

- `2025-26` — 12 of 306 results missing; 12 divergent [0, 0] list-encoded scores

| Season | Fixtures | Complete | Anomalous | Teams | Home/team | Away/team | Clean |
|---|--:|--:|--:|--:|:--:|:--:|:--:|
| 2010-11 | 306 | 306 | 0 | 18 | 17–17 | 17–17 | yes |
| 2011-12 | 306 | 306 | 0 | 18 | 17–17 | 17–17 | yes |
| 2012-13 | 306 | 306 | 0 | 18 | 17–17 | 17–17 | yes |
| 2013-14 | 306 | 306 | 0 | 18 | 17–17 | 17–17 | yes |
| 2014-15 | 306 | 306 | 0 | 18 | 17–17 | 17–17 | yes |
| 2015-16 | 306 | 306 | 0 | 18 | 17–17 | 17–17 | yes |
| 2016-17 | 306 | 306 | 0 | 18 | 17–17 | 17–17 | yes |
| 2017-18 | 306 | 306 | 0 | 18 | 17–17 | 17–17 | yes |
| 2018-19 | 306 | 306 | 0 | 18 | 17–17 | 17–17 | yes |
| 2019-20 | 306 | 306 | 0 | 18 | 17–17 | 17–17 | yes |
| 2020-21 | 306 | 306 | 0 | 18 | 17–17 | 17–17 | yes |
| 2021-22 | 306 | 306 | 0 | 18 | 17–17 | 17–17 | yes |
| 2022-23 | 306 | 306 | 0 | 18 | 17–17 | 17–17 | yes |
| 2023-24 | 306 | 306 | 0 | 18 | 17–17 | 17–17 | yes |
| 2024-25 | 306 | 306 | 0 | 18 | 17–17 | 17–17 | yes |
| 2025-26 | 306 | 294 | 12 | 18 | 17–17 | 17–17 | NO |

## English Premier League (`en.1`) — **ACCEPT_HISTORICAL**

- **Pack:** `packs/openfootball-eng-pl`
- **Seasons vendored:** 16
- **Clean seasons:** 15 (2010-11 → 2024-25)
- **Flagged seasons:** 2025-26
- **Backtest folds (3 most recent clean):** 2022-23, 2023-24, 2024-25

| Criterion | Result | Basis |
|---|---|---|
| Usable clean seasons (≥10) | PASS | 15 complete double-round-robin seasons |
| Structural consistency (all seasons) | PASS | no self-matches, negative scores, duplicate ordered pairs, or team-count mismatches |
| Latest clean season present | PASS | 2024-25 |
| Three recent clean folds | PASS | 2022-23, 2023-24, 2024-25 |

**Excluded seasons and why:**

- `2025-26` — 27 of 380 results missing; 27 divergent [0, 0] list-encoded scores

| Season | Fixtures | Complete | Anomalous | Teams | Home/team | Away/team | Clean |
|---|--:|--:|--:|--:|:--:|:--:|:--:|
| 2010-11 | 380 | 380 | 0 | 20 | 19–19 | 19–19 | yes |
| 2011-12 | 380 | 380 | 0 | 20 | 19–19 | 19–19 | yes |
| 2012-13 | 380 | 380 | 0 | 20 | 19–19 | 19–19 | yes |
| 2013-14 | 380 | 380 | 0 | 20 | 19–19 | 19–19 | yes |
| 2014-15 | 380 | 380 | 0 | 20 | 19–19 | 19–19 | yes |
| 2015-16 | 380 | 380 | 0 | 20 | 19–19 | 19–19 | yes |
| 2016-17 | 380 | 380 | 0 | 20 | 19–19 | 19–19 | yes |
| 2017-18 | 380 | 380 | 0 | 20 | 19–19 | 19–19 | yes |
| 2018-19 | 380 | 380 | 0 | 20 | 19–19 | 19–19 | yes |
| 2019-20 | 380 | 380 | 0 | 20 | 19–19 | 19–19 | yes |
| 2020-21 | 380 | 380 | 0 | 20 | 19–19 | 19–19 | yes |
| 2021-22 | 380 | 380 | 0 | 20 | 19–19 | 19–19 | yes |
| 2022-23 | 380 | 380 | 0 | 20 | 19–19 | 19–19 | yes |
| 2023-24 | 380 | 380 | 0 | 20 | 19–19 | 19–19 | yes |
| 2024-25 | 380 | 380 | 0 | 20 | 19–19 | 19–19 | yes |
| 2025-26 | 380 | 353 | 27 | 20 | 19–19 | 19–19 | NO |

## La Liga (`es.1`) — **ACCEPT_HISTORICAL**

- **Pack:** `packs/openfootball-esp-ll`
- **Seasons vendored:** 14
- **Clean seasons:** 12 (2012-13 → 2023-24)
- **Flagged seasons:** 2024-25, 2025-26
- **Backtest folds (3 most recent clean):** 2021-22, 2022-23, 2023-24

| Criterion | Result | Basis |
|---|---|---|
| Usable clean seasons (≥10) | PASS | 12 complete double-round-robin seasons |
| Structural consistency (all seasons) | PASS | no self-matches, negative scores, duplicate ordered pairs, or team-count mismatches |
| Latest clean season present | PASS | 2023-24 |
| Three recent clean folds | PASS | 2021-22, 2022-23, 2023-24 |

**Excluded seasons and why:**

- `2024-25` — 10 of 380 results missing
- `2025-26` — 15 of 380 results missing; 15 divergent [0, 0] list-encoded scores

| Season | Fixtures | Complete | Anomalous | Teams | Home/team | Away/team | Clean |
|---|--:|--:|--:|--:|:--:|:--:|:--:|
| 2012-13 | 380 | 380 | 0 | 20 | 19–19 | 19–19 | yes |
| 2013-14 | 380 | 380 | 0 | 20 | 19–19 | 19–19 | yes |
| 2014-15 | 380 | 380 | 0 | 20 | 19–19 | 19–19 | yes |
| 2015-16 | 380 | 380 | 0 | 20 | 19–19 | 19–19 | yes |
| 2016-17 | 380 | 380 | 0 | 20 | 19–19 | 19–19 | yes |
| 2017-18 | 380 | 380 | 0 | 20 | 19–19 | 19–19 | yes |
| 2018-19 | 380 | 380 | 0 | 20 | 19–19 | 19–19 | yes |
| 2019-20 | 380 | 380 | 0 | 20 | 19–19 | 19–19 | yes |
| 2020-21 | 380 | 380 | 0 | 20 | 19–19 | 19–19 | yes |
| 2021-22 | 380 | 380 | 0 | 20 | 19–19 | 19–19 | yes |
| 2022-23 | 380 | 380 | 0 | 20 | 19–19 | 19–19 | yes |
| 2023-24 | 380 | 380 | 0 | 20 | 19–19 | 19–19 | yes |
| 2024-25 | 380 | 370 | 0 | 20 | 19–19 | 19–19 | NO |
| 2025-26 | 380 | 365 | 15 | 20 | 19–19 | 19–19 | NO |

## Ligue 1 (`fr.1`) — **ACCEPT_HISTORICAL**

- **Pack:** `packs/openfootball-fra-l1`
- **Seasons vendored:** 12
- **Clean seasons:** 10 (2014-15 → 2024-25)
- **Flagged seasons:** 2019-20, 2025-26
- **Backtest folds (3 most recent clean):** 2022-23, 2023-24, 2024-25

| Criterion | Result | Basis |
|---|---|---|
| Usable clean seasons (≥10) | PASS | 10 complete double-round-robin seasons |
| Structural consistency (all seasons) | PASS | no self-matches, negative scores, duplicate ordered pairs, or team-count mismatches |
| Latest clean season present | PASS | 2024-25 |
| Three recent clean folds | PASS | 2022-23, 2023-24, 2024-25 |

**Excluded seasons and why:**

- `2019-20` — 101 of 380 results missing
- `2025-26` — 24 of 306 results missing; 23 divergent [0, 0] list-encoded scores

| Season | Fixtures | Complete | Anomalous | Teams | Home/team | Away/team | Clean |
|---|--:|--:|--:|--:|:--:|:--:|:--:|
| 2014-15 | 380 | 380 | 0 | 20 | 19–19 | 19–19 | yes |
| 2015-16 | 380 | 380 | 0 | 20 | 19–19 | 19–19 | yes |
| 2016-17 | 380 | 380 | 0 | 20 | 19–19 | 19–19 | yes |
| 2017-18 | 380 | 380 | 0 | 20 | 19–19 | 19–19 | yes |
| 2018-19 | 380 | 380 | 0 | 20 | 19–19 | 19–19 | yes |
| 2019-20 | 380 | 279 | 0 | 20 | 19–19 | 19–19 | NO |
| 2020-21 | 380 | 380 | 0 | 20 | 19–19 | 19–19 | yes |
| 2021-22 | 380 | 380 | 0 | 20 | 19–19 | 19–19 | yes |
| 2022-23 | 380 | 380 | 0 | 20 | 19–19 | 19–19 | yes |
| 2023-24 | 306 | 306 | 0 | 18 | 17–17 | 17–17 | yes |
| 2024-25 | 306 | 306 | 0 | 18 | 17–17 | 17–17 | yes |
| 2025-26 | 306 | 282 | 23 | 18 | 17–17 | 17–17 | NO |

## Serie A (`it.1`) — **ACCEPT_HISTORICAL**

- **Pack:** `packs/openfootball-ita-sa`
- **Seasons vendored:** 13
- **Clean seasons:** 11 (2013-14 → 2023-24)
- **Flagged seasons:** 2024-25, 2025-26
- **Backtest folds (3 most recent clean):** 2021-22, 2022-23, 2023-24

| Criterion | Result | Basis |
|---|---|---|
| Usable clean seasons (≥10) | PASS | 11 complete double-round-robin seasons |
| Structural consistency (all seasons) | PASS | no self-matches, negative scores, duplicate ordered pairs, or team-count mismatches |
| Latest clean season present | PASS | 2023-24 |
| Three recent clean folds | PASS | 2021-22, 2022-23, 2023-24 |

**Excluded seasons and why:**

- `2024-25` — 10 of 380 results missing
- `2025-26` — 36 of 380 results missing; 36 divergent [0, 0] list-encoded scores

| Season | Fixtures | Complete | Anomalous | Teams | Home/team | Away/team | Clean |
|---|--:|--:|--:|--:|:--:|:--:|:--:|
| 2013-14 | 380 | 380 | 0 | 20 | 19–19 | 19–19 | yes |
| 2014-15 | 380 | 380 | 0 | 20 | 19–19 | 19–19 | yes |
| 2015-16 | 380 | 380 | 0 | 20 | 19–19 | 19–19 | yes |
| 2016-17 | 380 | 380 | 0 | 20 | 19–19 | 19–19 | yes |
| 2017-18 | 380 | 380 | 0 | 20 | 19–19 | 19–19 | yes |
| 2018-19 | 380 | 380 | 0 | 20 | 19–19 | 19–19 | yes |
| 2019-20 | 380 | 380 | 0 | 20 | 19–19 | 19–19 | yes |
| 2020-21 | 380 | 380 | 0 | 20 | 19–19 | 19–19 | yes |
| 2021-22 | 380 | 380 | 0 | 20 | 19–19 | 19–19 | yes |
| 2022-23 | 380 | 380 | 0 | 20 | 19–19 | 19–19 | yes |
| 2023-24 | 380 | 380 | 0 | 20 | 19–19 | 19–19 | yes |
| 2024-25 | 380 | 370 | 0 | 20 | 19–19 | 19–19 | NO |
| 2025-26 | 380 | 344 | 36 | 20 | 19–19 | 19–19 | NO |
