# Bundesliga chronological evaluation (historical)

Log loss is primary. Each fold is a frozen test window; model fitting and
Dixon-Coles decay selection use only rows before the stated cutoff. Candidates are
reported honestly and no test fold is used for parameter tuning.

| Fold | Matches | Model | Log loss | Brier | ECE | RPS |
|---|---:|---|---:|---:|---:|---:|
| BUNDESLIGA2022-23 | 306 | climatological | 1.056926 | 0.637581 | 0.022700 | 0.226274 |
| BUNDESLIGA2022-23 | 306 | elo_ordlogit | 0.994742 | 0.593951 | 0.067309 | 0.204428 |
| BUNDESLIGA2022-23 | 306 | poisson_independent | 0.993079 | 0.592216 | 0.033680 | 0.203599 |
| BUNDESLIGA2022-23 | 306 | dixon_coles | 0.996970 | 0.595059 | 0.048262 | 0.205367 |
| BUNDESLIGA2022-23 | 306 | bivariate_poisson | 0.993079 | 0.592216 | 0.033680 | 0.203599 |
| BUNDESLIGA2022-23 | 306 | contextual_dixon_coles | 0.990538 | 0.590718 | 0.050078 | 0.202967 |
| BUNDESLIGA2023-24 | 306 | climatological | 1.075414 | 0.650504 | 0.014993 | 0.227685 |
| BUNDESLIGA2023-24 | 306 | elo_ordlogit | 1.026377 | 0.614837 | 0.025895 | 0.211122 |
| BUNDESLIGA2023-24 | 306 | poisson_independent | 1.019685 | 0.609168 | 0.048443 | 0.207836 |
| BUNDESLIGA2023-24 | 306 | dixon_coles | 1.028728 | 0.615926 | 0.044435 | 0.211616 |
| BUNDESLIGA2023-24 | 306 | bivariate_poisson | 1.019685 | 0.609168 | 0.048443 | 0.207836 |
| BUNDESLIGA2023-24 | 306 | contextual_dixon_coles | 1.036941 | 0.621851 | 0.065310 | 0.214448 |
| BUNDESLIGA2024-25 | 306 | climatological | 1.093035 | 0.664265 | 0.066210 | 0.237946 |
| BUNDESLIGA2024-25 | 306 | elo_ordlogit | 1.023666 | 0.613969 | 0.018947 | 0.213050 |
| BUNDESLIGA2024-25 | 306 | poisson_independent | 1.035314 | 0.621655 | 0.088557 | 0.217355 |
| BUNDESLIGA2024-25 | 306 | dixon_coles | 1.033773 | 0.620569 | 0.083670 | 0.217313 |
| BUNDESLIGA2024-25 | 306 | bivariate_poisson | 1.035314 | 0.621655 | 0.088557 | 0.217355 |
| BUNDESLIGA2024-25 | 306 | contextual_dixon_coles | 1.032225 | 0.619319 | 0.096533 | 0.216982 |

## Interpretation

Historical, not live. Data is a pinned openfootball snapshot (CC0) that passed the
club-coverage gate for completed seasons only (docs/handoff/openfootball-audit.md).
The partial 2025-26 capture is excluded; each fold trains on all prior clean seasons from 2010-11. A Bundesliga season is 306 matches (18 clubs).

Elo is a baseline, not a champion. Unlike the near-neutral international folds, club
matches carry a real home advantage, so home-aware candidates have room to help — but
only if they beat Elo out-of-sample here. openfootball kickoff times are venue-local.
Each league is modeled independently from its own pack; there are no inter-league
matches, so strengths are NOT comparable across leagues.
