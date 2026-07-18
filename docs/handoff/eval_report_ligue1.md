# Ligue 1 chronological evaluation (historical)

Log loss is primary. Each fold is a frozen test window; model fitting and
Dixon-Coles decay selection use only rows before the stated cutoff. Candidates are
reported honestly and no test fold is used for parameter tuning.

| Fold | Matches | Model | Log loss | Brier | ECE | RPS |
|---|---:|---|---:|---:|---:|---:|
| LIGUE1-2022-23 | 380 | climatological | 1.074716 | 0.650714 | 0.013949 | 0.233451 |
| LIGUE1-2022-23 | 380 | elo_ordlogit | 1.018985 | 0.608656 | 0.054418 | 0.213539 |
| LIGUE1-2022-23 | 380 | poisson_independent | 1.021636 | 0.609350 | 0.034773 | 0.214920 |
| LIGUE1-2022-23 | 380 | dixon_coles | 1.022939 | 0.609535 | 0.023295 | 0.214951 |
| LIGUE1-2022-23 | 380 | bivariate_poisson | 1.021636 | 0.609350 | 0.034773 | 0.214920 |
| LIGUE1-2022-23 | 380 | contextual_dixon_coles | 1.022991 | 0.608716 | 0.032803 | 0.214882 |
| LIGUE1-2023-24 | 306 | climatological | 1.091744 | 0.662660 | 0.049144 | 0.233989 |
| LIGUE1-2023-24 | 306 | elo_ordlogit | 1.044521 | 0.628899 | 0.022447 | 0.217036 |
| LIGUE1-2023-24 | 306 | poisson_independent | 1.033693 | 0.620337 | 0.073742 | 0.211993 |
| LIGUE1-2023-24 | 306 | dixon_coles | 1.034938 | 0.621973 | 0.050178 | 0.213206 |
| LIGUE1-2023-24 | 306 | bivariate_poisson | 1.033693 | 0.620337 | 0.073742 | 0.211993 |
| LIGUE1-2023-24 | 306 | contextual_dixon_coles | 1.039669 | 0.624649 | 0.075223 | 0.214475 |
| LIGUE1-2024-25 | 306 | climatological | 1.053458 | 0.636318 | 0.030165 | 0.235814 |
| LIGUE1-2024-25 | 306 | elo_ordlogit | 0.995975 | 0.593816 | 0.067117 | 0.214686 |
| LIGUE1-2024-25 | 306 | poisson_independent | 0.979445 | 0.582022 | 0.059073 | 0.209890 |
| LIGUE1-2024-25 | 306 | dixon_coles | 0.984413 | 0.585296 | 0.062593 | 0.210332 |
| LIGUE1-2024-25 | 306 | bivariate_poisson | 0.979445 | 0.582022 | 0.059073 | 0.209890 |
| LIGUE1-2024-25 | 306 | contextual_dixon_coles | 0.988326 | 0.587704 | 0.065997 | 0.211444 |

## Interpretation

Historical, not live. Data is a pinned openfootball snapshot (CC0) that passed the
club-coverage gate for completed seasons only (docs/handoff/openfootball-audit.md).
The COVID-abandoned 2019-20 season is excluded as a fold (its 279 played matches remain training rows) and 2025-26 is a partial capture. Ligue 1 contracted from 20 to 18 clubs in 2023-24, so folds are 380 then 306 matches.

Elo is a baseline, not a champion. Unlike the near-neutral international folds, club
matches carry a real home advantage, so home-aware candidates have room to help — but
only if they beat Elo out-of-sample here. openfootball kickoff times are venue-local.
Each league is modeled independently from its own pack; there are no inter-league
matches, so strengths are NOT comparable across leagues.
