# English Premier League chronological evaluation (historical)

Log loss is primary. Each fold is a frozen test window; model fitting and
Dixon-Coles decay selection use only rows before the stated cutoff. Candidates are
reported honestly and no test fold is used for parameter tuning.

| Fold | Matches | Model | Log loss | Brier | ECE | RPS |
|---|---:|---|---:|---:|---:|---:|
| EPL2023-24 | 380 | climatological | 1.055077 | 0.637613 | 0.009586 | 0.233857 |
| EPL2023-24 | 380 | elo_ordlogit | 0.963359 | 0.570622 | 0.098605 | 0.200565 |
| EPL2023-24 | 380 | poisson_independent | 0.949396 | 0.560501 | 0.058908 | 0.196998 |
| EPL2023-24 | 380 | dixon_coles | 0.958670 | 0.567279 | 0.059791 | 0.199310 |
| EPL2023-24 | 380 | bivariate_poisson | 0.949396 | 0.560501 | 0.058908 | 0.196998 |
| EPL2023-24 | 380 | contextual_dixon_coles | 0.958191 | 0.567001 | 0.064334 | 0.199055 |
| EPL2024-25 | 380 | climatological | 1.082152 | 0.656510 | 0.043730 | 0.235823 |
| EPL2024-25 | 380 | elo_ordlogit | 1.007546 | 0.602476 | 0.036183 | 0.209211 |
| EPL2024-25 | 380 | poisson_independent | 1.045108 | 0.629649 | 0.060097 | 0.222871 |
| EPL2024-25 | 380 | dixon_coles | 1.045202 | 0.629177 | 0.053602 | 0.222792 |
| EPL2024-25 | 380 | bivariate_poisson | 1.045108 | 0.629649 | 0.060097 | 0.222871 |
| EPL2024-25 | 380 | contextual_dixon_coles | 1.042780 | 0.626800 | 0.058828 | 0.221732 |
| EPL2025-26 | 380 | climatological | 1.082289 | 0.655095 | 0.022395 | 0.227597 |
| EPL2025-26 | 380 | elo_ordlogit | 1.048672 | 0.632167 | 0.039041 | 0.216368 |
| EPL2025-26 | 380 | poisson_independent | 1.037008 | 0.623581 | 0.043849 | 0.211982 |
| EPL2025-26 | 380 | dixon_coles | 1.029763 | 0.618285 | 0.059102 | 0.210025 |
| EPL2025-26 | 380 | bivariate_poisson | 1.037008 | 0.623581 | 0.043849 | 0.211982 |
| EPL2025-26 | 380 | contextual_dixon_coles | 1.033556 | 0.621455 | 0.080621 | 0.211747 |

## Interpretation

Historical, not live. Data is a pinned openfootball snapshot (CC0) that passed the
club-coverage gate for completed seasons only (docs/handoff/openfootball-audit.md).
All 16 seasons from 2010-11 are clean, so the folds are the three most recent of them and each trains on every prior season.

Elo is a baseline, not a champion. Unlike the near-neutral international folds, club
matches carry a real home advantage, so home-aware candidates have room to help — but
only if they beat Elo out-of-sample here. openfootball kickoff times are venue-local.
Each league is modeled independently from its own pack; there are no inter-league
matches, so strengths are NOT comparable across leagues.
