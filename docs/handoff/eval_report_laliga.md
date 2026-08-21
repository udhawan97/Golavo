# La Liga chronological evaluation (historical)

Log loss is primary. Each fold is a frozen test window; model fitting and
Dixon-Coles decay selection use only rows before the stated cutoff. Candidates are
reported honestly and no test fold is used for parameter tuning.

| Fold | Matches | Model | Log loss | Brier | ECE | RPS |
|---|---:|---|---:|---:|---:|---:|
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
| LALIGA2025-26 | 380 | climatological | 1.048383 | 0.631382 | 0.030929 | 0.223226 |
| LALIGA2025-26 | 380 | elo_ordlogit | 0.994619 | 0.591452 | 0.071072 | 0.204858 |
| LALIGA2025-26 | 380 | poisson_independent | 0.988350 | 0.586963 | 0.060009 | 0.203175 |
| LALIGA2025-26 | 380 | dixon_coles | 0.989069 | 0.587429 | 0.057819 | 0.203339 |
| LALIGA2025-26 | 380 | bivariate_poisson | 0.988348 | 0.586961 | 0.060006 | 0.203174 |
| LALIGA2025-26 | 380 | contextual_dixon_coles | 0.991663 | 0.589155 | 0.055710 | 0.204021 |

## Interpretation

Historical, not live. Data is a pinned openfootball snapshot (CC0) that passed the
club-coverage gate for completed seasons only (docs/handoff/openfootball-audit.md).
The folds skip 2024-25, whose capture is missing its final matchday (10 results); its played matches remain training rows. Training reaches back to 2012-13.

Elo is a baseline, not a champion. Unlike the near-neutral international folds, club
matches carry a real home advantage, so home-aware candidates have room to help — but
only if they beat Elo out-of-sample here. openfootball kickoff times are venue-local.
Each league is modeled independently from its own pack; there are no inter-league
matches, so strengths are NOT comparable across leagues.
