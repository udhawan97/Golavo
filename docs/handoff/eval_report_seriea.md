# Serie A chronological evaluation (historical)

Log loss is primary. Each fold is a frozen test window; model fitting and
Dixon-Coles decay selection use only rows before the stated cutoff. Candidates are
reported honestly and no test fold is used for parameter tuning.

| Fold | Matches | Model | Log loss | Brier | ECE | RPS |
|---|---:|---|---:|---:|---:|---:|
| SERIEA2021-22 | 380 | climatological | 1.090016 | 0.661707 | 0.049895 | 0.235122 |
| SERIEA2021-22 | 380 | elo_ordlogit | 1.005193 | 0.600153 | 0.035990 | 0.205079 |
| SERIEA2021-22 | 380 | poisson_independent | 1.006514 | 0.600835 | 0.047287 | 0.205287 |
| SERIEA2021-22 | 380 | dixon_coles | 1.004468 | 0.599787 | 0.035758 | 0.205112 |
| SERIEA2021-22 | 380 | bivariate_poisson | 1.006514 | 0.600835 | 0.047287 | 0.205287 |
| SERIEA2022-23 | 380 | climatological | 1.079223 | 0.653455 | 0.010146 | 0.229689 |
| SERIEA2022-23 | 380 | elo_ordlogit | 1.004013 | 0.599253 | 0.057751 | 0.203444 |
| SERIEA2022-23 | 380 | poisson_independent | 1.011996 | 0.604271 | 0.052915 | 0.205197 |
| SERIEA2022-23 | 380 | dixon_coles | 1.009124 | 0.602705 | 0.066013 | 0.204936 |
| SERIEA2022-23 | 380 | bivariate_poisson | 1.011996 | 0.604271 | 0.052915 | 0.205197 |
| SERIEA2023-24 | 380 | climatological | 1.087997 | 0.658701 | 0.014395 | 0.224477 |
| SERIEA2023-24 | 380 | elo_ordlogit | 1.018245 | 0.610878 | 0.033724 | 0.201013 |
| SERIEA2023-24 | 380 | poisson_independent | 1.002934 | 0.600315 | 0.027857 | 0.195791 |
| SERIEA2023-24 | 380 | dixon_coles | 0.998515 | 0.598882 | 0.034237 | 0.195708 |
| SERIEA2023-24 | 380 | bivariate_poisson | 1.002934 | 0.600315 | 0.027857 | 0.195791 |

## Interpretation

Historical, not live. Data is a pinned openfootball snapshot (CC0) that passed the
club-coverage gate for completed seasons only (docs/handoff/openfootball-audit.md).
Folds stop at 2023-24 because the 2024-25 capture is missing its final matchday (10 results); 2025-26 is a partial capture. Training reaches back to 2013-14.

Elo is a baseline, not a champion. Unlike the near-neutral international folds, club
matches carry a real home advantage, so home-aware candidates have room to help — but
only if they beat Elo out-of-sample here. openfootball kickoff times are venue-local.
Each league is modeled independently from its own pack; there are no inter-league
matches, so strengths are NOT comparable across leagues.

