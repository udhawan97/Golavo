# Phase 1 English Premier League chronological evaluation

Log loss is primary. Each fold is a frozen test window; model fitting and
Dixon-Coles decay selection use only rows before the stated cutoff. Candidates are
reported honestly and no test fold is used for parameter tuning.

| Fold | Matches | Model | Log loss | Brier | ECE | RPS |
|---|---:|---|---:|---:|---:|---:|
| EPL2022-23 | 380 | climatological | 1.049541 | 0.632828 | 0.036040 | 0.228052 |
| EPL2022-23 | 380 | elo_ordlogit | 1.006378 | 0.600932 | 0.051814 | 0.212361 |
| EPL2022-23 | 380 | poisson_independent | 1.024987 | 0.613954 | 0.043703 | 0.219230 |
| EPL2022-23 | 380 | dixon_coles | 1.027237 | 0.614652 | 0.044961 | 0.219346 |
| EPL2022-23 | 380 | bivariate_poisson | 1.024987 | 0.613954 | 0.043703 | 0.219230 |
| EPL2023-24 | 380 | climatological | 1.055077 | 0.637613 | 0.009586 | 0.233857 |
| EPL2023-24 | 380 | elo_ordlogit | 0.963359 | 0.570622 | 0.098605 | 0.200565 |
| EPL2023-24 | 380 | poisson_independent | 0.949398 | 0.560502 | 0.058911 | 0.196998 |
| EPL2023-24 | 380 | dixon_coles | 0.958672 | 0.567280 | 0.059794 | 0.199310 |
| EPL2023-24 | 380 | bivariate_poisson | 0.949398 | 0.560502 | 0.058911 | 0.196998 |
| EPL2024-25 | 380 | climatological | 1.082152 | 0.656510 | 0.043730 | 0.235823 |
| EPL2024-25 | 380 | elo_ordlogit | 1.007546 | 0.602476 | 0.036183 | 0.209211 |
| EPL2024-25 | 380 | poisson_independent | 1.045107 | 0.629649 | 0.060095 | 0.222870 |
| EPL2024-25 | 380 | dixon_coles | 1.045201 | 0.629177 | 0.053599 | 0.222792 |
| EPL2024-25 | 380 | bivariate_poisson | 1.045107 | 0.629649 | 0.060095 | 0.222870 |

## Interpretation

Historical, not live. Data is openfootball (CC0), which passed the Phase 1 gate for
completed seasons only (docs/handoff/openfootball-audit.md). The partial 2025-26
capture is excluded; each fold trains on all prior clean seasons from 2010-11.

Elo is a baseline, not a champion. Unlike the near-neutral international folds, club
matches carry a real home advantage, so home-aware candidates have room to help — but
only if they beat Elo out-of-sample here. openfootball kickoff times are venue-local.

