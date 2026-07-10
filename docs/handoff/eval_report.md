# Phase 0 chronological evaluation

Log loss is primary. Each tournament is a frozen test window; model fitting and
Dixon-Coles decay selection use only rows before the stated cutoff. Candidates are
reported honestly and no test fold is used for parameter tuning.

| Fold | Matches | Model | Log loss | Brier | ECE | RPS |
|---|---:|---|---:|---:|---:|---:|
| WC2022 | 64 | climatological | 1.074249 | 0.651155 | 0.053999 | 0.235830 |
| WC2022 | 64 | elo_ordlogit | 1.015747 | 0.603744 | 0.149382 | 0.213636 |
| WC2022 | 64 | poisson_independent | 1.067719 | 0.642941 | 0.111689 | 0.229654 |
| WC2022 | 64 | dixon_coles | 1.064957 | 0.640144 | 0.075543 | 0.227483 |
| WC2022 | 64 | bivariate_poisson | 1.067719 | 0.642941 | 0.111689 | 0.229654 |
| EURO2024 | 51 | climatological | 1.142226 | 0.697113 | 0.137687 | 0.231815 |
| EURO2024 | 51 | elo_ordlogit | 1.030029 | 0.617385 | 0.062463 | 0.196514 |
| EURO2024 | 51 | poisson_independent | 1.022756 | 0.612261 | 0.088718 | 0.193882 |
| EURO2024 | 51 | dixon_coles | 0.997326 | 0.596576 | 0.089045 | 0.188424 |
| EURO2024 | 51 | bivariate_poisson | 1.022756 | 0.612261 | 0.088718 | 0.193882 |
| WC2026 | 97 | climatological | 1.056496 | 0.637083 | 0.015836 | 0.225238 |
| WC2026 | 97 | elo_ordlogit | 0.905550 | 0.531794 | 0.160250 | 0.172502 |
| WC2026 | 97 | poisson_independent | 0.959845 | 0.571654 | 0.087641 | 0.193605 |
| WC2026 | 97 | dixon_coles | 0.957076 | 0.570613 | 0.102887 | 0.192499 |
| WC2026 | 97 | bivariate_poisson | 0.959845 | 0.571654 | 0.087641 | 0.193605 |

## Interpretation

Elo is a baseline, not a declared champion. A lower log loss is better. Candidate
models that lose to Elo remain in this report; Phase 0 does not tune on test results
to manufacture a win. Reliability-bin Wilson intervals are in `eval_summary.json`.

The source supplies dates but not kickoff times; fold cutoffs use 23:59:59 UTC on
the day before each tournament window.
