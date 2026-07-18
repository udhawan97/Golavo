# La Liga chronological evaluation (historical)

Log loss is primary. Each fold is a frozen test window; model fitting and
Dixon-Coles decay selection use only rows before the stated cutoff. Candidates are
reported honestly and no test fold is used for parameter tuning.

| Fold | Matches | Model | Log loss | Brier | ECE | RPS |
|---|---:|---|---:|---:|---:|---:|
| LALIGA2021-22 | 380 | climatological | 1.081100 | 0.654087 | 0.028249 | 0.222733 |
| LALIGA2021-22 | 380 | elo_ordlogit | 1.005811 | 0.601319 | 0.038731 | 0.197364 |
| LALIGA2021-22 | 380 | poisson_independent | 1.008897 | 0.601734 | 0.058214 | 0.197139 |
| LALIGA2021-22 | 380 | dixon_coles | 1.004475 | 0.599440 | 0.043291 | 0.196757 |
| LALIGA2021-22 | 380 | bivariate_poisson | 1.008897 | 0.601734 | 0.058214 | 0.197139 |
| LALIGA2021-22 | 380 | contextual_dixon_coles | 1.003988 | 0.599630 | 0.047798 | 0.196663 |
| LALIGA2022-23 | 380 | climatological | 1.051916 | 0.634221 | 0.019310 | 0.227247 |
| LALIGA2022-23 | 380 | elo_ordlogit | 1.000621 | 0.596800 | 0.056706 | 0.209005 |
| LALIGA2022-23 | 380 | poisson_independent | 0.986303 | 0.587275 | 0.049762 | 0.204959 |
| LALIGA2022-23 | 380 | dixon_coles | 0.993632 | 0.592335 | 0.056334 | 0.206674 |
| LALIGA2022-23 | 380 | bivariate_poisson | 0.986303 | 0.587275 | 0.049762 | 0.204959 |
| LALIGA2022-23 | 380 | contextual_dixon_coles | 0.998638 | 0.596056 | 0.039907 | 0.208661 |
| LALIGA2023-24 | 380 | climatological | 1.076666 | 0.651199 | 0.021918 | 0.224008 |
| LALIGA2023-24 | 380 | elo_ordlogit | 1.003028 | 0.598633 | 0.071145 | 0.199097 |
| LALIGA2023-24 | 380 | poisson_independent | 0.974282 | 0.579453 | 0.027212 | 0.190379 |
| LALIGA2023-24 | 380 | dixon_coles | 0.969400 | 0.576471 | 0.045845 | 0.189391 |
| LALIGA2023-24 | 380 | bivariate_poisson | 0.974282 | 0.579453 | 0.027212 | 0.190379 |
| LALIGA2023-24 | 380 | contextual_dixon_coles | 0.972536 | 0.578493 | 0.022714 | 0.190414 |

## Interpretation

Historical, not live. Data is a pinned openfootball snapshot (CC0) that passed the
club-coverage gate for completed seasons only (docs/handoff/openfootball-audit.md).
Folds stop at 2023-24 because the 2024-25 capture is missing its final matchday (10 results); 2025-26 is a partial capture. Training reaches back to 2012-13.

Elo is a baseline, not a champion. Unlike the near-neutral international folds, club
matches carry a real home advantage, so home-aware candidates have room to help — but
only if they beat Elo out-of-sample here. openfootball kickoff times are venue-local.
Each league is modeled independently from its own pack; there are no inter-league
matches, so strengths are NOT comparable across leagues.
