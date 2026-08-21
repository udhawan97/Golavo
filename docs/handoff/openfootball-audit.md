# openfootball top-league coverage audit (club gate)

- **Source:** openfootball/football.json pinned at `a5dd38b3bcbe3aa2477cf400f569264253d51431` (committed 2026-05-30), CC0-1.0
- **Scope:** men's top-5 European leagues, HISTORICAL completed seasons only — not live
- **Live in-season updating:** UNVERIFIED until the 2026-27 season starts
- **Independent cross-source correctness:** DEFERRED (footballcsv stale to ~2020/21; divergent team names)
- **Cross-league calibration:** NONE — domestic files carry no inter-league matches, so each league is modeled independently and strengths are NOT comparable across leagues

| League | Verdict | Clean seasons | Flagged | Backtest folds |
|---|---|---|---|---|
| Bundesliga | **ACCEPT_HISTORICAL** | 16 (2010-11 → 2025-26) | none | 2023-24, 2024-25, 2025-26 |
| English Premier League | **ACCEPT_HISTORICAL** | 16 (2010-11 → 2025-26) | none | 2023-24, 2024-25, 2025-26 |
| La Liga | **ACCEPT_HISTORICAL** | 13 (2012-13 → 2025-26) | 2024-25 | 2022-23, 2023-24, 2025-26 |
| Ligue 1 | **ACCEPT_HISTORICAL** | 10 (2014-15 → 2024-25) | 2019-20, 2025-26 | 2022-23, 2023-24, 2024-25 |
| Serie A | **ACCEPT_HISTORICAL** | 12 (2013-14 → 2025-26) | 2024-25 | 2022-23, 2023-24, 2025-26 |

A season is **clean** only when, with n = the actual number of teams in the file:
it has exactly n·(n−1) fixtures, every one carrying a well-formed two-integer
full time score in either shape upstream writes it — the `score.ft` object or
the bare `score` list; every team plays exactly n−1 home and n−1 away; there are no
self-matches, duplicate ordered pairs, or negative scores; and n equals the
league's constitutional size for that season (20 for the Premier League, La Liga,
Serie A; 18 for the Bundesliga; 20 for Ligue 1 through 2022-23, 18 from 2023-24 —
the last check catches a season that silently dropped a whole club, which the
derived-n arithmetic alone cannot see).

## The 2025-26 bare-list score (corrected 2026-08-21)

- Upstream serializes a **goalless draw** as a bare `score` list from 2025-26,
  where every earlier season wrote `{"ft": [0, 0]}`. An earlier reading of this
  audit took the bare list for an unfinalized placeholder, because it appears in
  no completed season and is uniformly zero — so 114 real results across the five
  leagues, 27 of them Premier League, were discarded and every 2025-26 season was
  disqualified as a partial capture.
- It is a result, on three independent grounds. It appears in no season before
  2025-26. In the files where it appears the object-form `[0, 0]` count drops to
  exactly zero, so the two shapes are complementary rather than concurrent. And
  every one matches a played goalless draw in the Football.TXT the Premier League
  pack already co-sources, at the commit it already pins (`afc118c3`) — a second
  source that agrees with football.json on **all 380** results of that season,
  not merely the 27. No contradiction was found in any league.
- The same file at upstream HEAD additionally carries goalscorers with minutes,
  penalties and own goals: 1,045 Premier League goals across 353 scoring matches,
  the other 27 being exactly these goalless draws. That detail does not exist at
  any commit this repo pins, so it is noted here and not vendored.
- Those rows carry no half-time score, because the bare list states a full time
  score and nothing else. They are excluded from half-time facts rather than
  having one inferred from the final score.

## Recurring anomalies (why seasons are excluded)

- **Empty `{}` scores.** A fixture upstream has no result for at this capture.
  Still INCOMPLETE, and never fabricated as a result.
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
- **Clean seasons:** 16 (2010-11 → 2025-26)
- **Flagged seasons:** none
- **Backtest folds (3 most recent clean):** 2023-24, 2024-25, 2025-26

| Criterion | Result | Basis |
|---|---|---|
| Usable clean seasons (≥10) | PASS | 16 complete double-round-robin seasons |
| Structural consistency (all seasons) | PASS | no self-matches, negative scores, duplicate ordered pairs, or team-count mismatches |
| Latest clean season present | PASS | 2025-26 |
| Three recent clean folds | PASS | 2023-24, 2024-25, 2025-26 |

| Season | Fixtures | Complete | Bare-list 0-0 | Teams | Home/team | Away/team | Clean |
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
| 2025-26 | 306 | 306 | 12 | 18 | 17–17 | 17–17 | yes |

## English Premier League (`en.1`) — **ACCEPT_HISTORICAL**

- **Pack:** `packs/openfootball-eng-pl`
- **Seasons vendored:** 16
- **Clean seasons:** 16 (2010-11 → 2025-26)
- **Flagged seasons:** none
- **Backtest folds (3 most recent clean):** 2023-24, 2024-25, 2025-26

| Criterion | Result | Basis |
|---|---|---|
| Usable clean seasons (≥10) | PASS | 16 complete double-round-robin seasons |
| Structural consistency (all seasons) | PASS | no self-matches, negative scores, duplicate ordered pairs, or team-count mismatches |
| Latest clean season present | PASS | 2025-26 |
| Three recent clean folds | PASS | 2023-24, 2024-25, 2025-26 |

| Season | Fixtures | Complete | Bare-list 0-0 | Teams | Home/team | Away/team | Clean |
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
| 2025-26 | 380 | 380 | 27 | 20 | 19–19 | 19–19 | yes |

## La Liga (`es.1`) — **ACCEPT_HISTORICAL**

- **Pack:** `packs/openfootball-esp-ll`
- **Seasons vendored:** 14
- **Clean seasons:** 13 (2012-13 → 2025-26)
- **Flagged seasons:** 2024-25
- **Backtest folds (3 most recent clean):** 2022-23, 2023-24, 2025-26

| Criterion | Result | Basis |
|---|---|---|
| Usable clean seasons (≥10) | PASS | 13 complete double-round-robin seasons |
| Structural consistency (all seasons) | PASS | no self-matches, negative scores, duplicate ordered pairs, or team-count mismatches |
| Latest clean season present | PASS | 2025-26 |
| Three recent clean folds | PASS | 2022-23, 2023-24, 2025-26 |

**Excluded seasons and why:**

- `2024-25` — 10 of 380 results missing

| Season | Fixtures | Complete | Bare-list 0-0 | Teams | Home/team | Away/team | Clean |
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
| 2025-26 | 380 | 380 | 15 | 20 | 19–19 | 19–19 | yes |

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
- `2025-26` — 1 of 306 results missing

| Season | Fixtures | Complete | Bare-list 0-0 | Teams | Home/team | Away/team | Clean |
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
| 2025-26 | 306 | 305 | 23 | 18 | 17–17 | 17–17 | NO |

## Serie A (`it.1`) — **ACCEPT_HISTORICAL**

- **Pack:** `packs/openfootball-ita-sa`
- **Seasons vendored:** 13
- **Clean seasons:** 12 (2013-14 → 2025-26)
- **Flagged seasons:** 2024-25
- **Backtest folds (3 most recent clean):** 2022-23, 2023-24, 2025-26

| Criterion | Result | Basis |
|---|---|---|
| Usable clean seasons (≥10) | PASS | 12 complete double-round-robin seasons |
| Structural consistency (all seasons) | PASS | no self-matches, negative scores, duplicate ordered pairs, or team-count mismatches |
| Latest clean season present | PASS | 2025-26 |
| Three recent clean folds | PASS | 2022-23, 2023-24, 2025-26 |

**Excluded seasons and why:**

- `2024-25` — 10 of 380 results missing

| Season | Fixtures | Complete | Bare-list 0-0 | Teams | Home/team | Away/team | Clean |
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
| 2025-26 | 380 | 380 | 36 | 20 | 19–19 | 19–19 | yes |
