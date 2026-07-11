---
title: Model cards & calibration
description: Per-competition model cards with the real backtest metrics (log loss, Brier, ECE, RPS) and reliability diagrams.
---

These cards report the **actual** out-of-sample backtest metrics Golavo emits, one card per competition. They are generated from the schema-validated `eval_summary*.json` artifacts by `scripts/build_model_cards.py` — never hand-edited — so the numbers here match what CI validates. **Log loss is primary.** No model is a declared champion; forward evidence (the [calibration record](/Golavo/prediction-ledger/)) is kept separate from these historical folds.

:::note[How to read a card]
Each card lists the five deterministic candidates against the climatological baseline. Metrics are out-of-sample on strictly chronological folds. League strengths are **not** comparable across competitions — each league is modeled independently from its own pack.
:::

## Men's senior full internationals

- **Scope:** Men's senior full internationals (forward seal→score surface plus these historical test folds).
- **Source snapshot:** martj42/international_results `ddd7249ac0c2`, retrieved 2026-07-10 (CC0-1.0).
- **Folds:** WC2022, EURO2024, WC2026 — strictly chronological; fitting and decay selection use only rows before each fold's cutoff.

**Log loss by fold** (primary metric; lower is better; **bold** = best in fold):

| Model | WC2022 | EURO2024 | WC2026 |
|---|---:|---:|---:|
| climatological (baseline) | 1.0742 | 1.1422 | 1.0565 |
| Elo ordinal-logit | **1.0157** | 1.0300 | **0.9055** |
| independent Poisson | 1.0677 | 1.0228 | 0.9598 |
| time-decayed Dixon-Coles | 1.0650 | **0.9973** | 0.9571 |
| bivariate Poisson | 1.0677 | 1.0228 | 0.9598 |

Every candidate beats the climatological baseline on log loss on every fold; the best model varies by fold and none is crowned a champion.

**Calibration — most recent fold (WC2026):**

| Model | Brier | ECE | RPS |
|---|---:|---:|---:|
| climatological (baseline) | 0.6371 | 0.0158 | 0.2252 |
| Elo ordinal-logit | 0.5318 | 0.1603 | 0.1725 |
| independent Poisson | 0.5717 | 0.0876 | 0.1936 |
| time-decayed Dixon-Coles | 0.5706 | 0.1029 | 0.1925 |
| bivariate Poisson | 0.5717 | 0.0876 | 0.1936 |

**Reliability — Elo ordinal-logit on WC2026** (Wilson 95% intervals; empty bins omitted):

| Confidence bin | n | Empirical | Wilson 95% |
|---|---:|---:|---|
| 0.3–0.4 | 17 | 0.529 | [0.31, 0.74] |
| 0.4–0.5 | 34 | 0.588 | [0.42, 0.74] |
| 0.5–0.6 | 28 | 0.786 | [0.60, 0.90] |
| 0.6–0.7 | 15 | 0.733 | [0.48, 0.89] |
| 0.7–0.8 | 3 | 0.667 | [0.21, 0.94] |

## English Premier League

- **Scope:** English Premier League (historical, completed seasons only — **not live**).
- **Source snapshot:** openfootball `a5dd38b3bcbe`, retrieved 2026-07-11 (CC0-1.0).
- **Folds:** EPL2022-23, EPL2023-24, EPL2024-25 — strictly chronological; fitting and decay selection use only rows before each fold's cutoff.

**Log loss by fold** (primary metric; lower is better; **bold** = best in fold):

| Model | EPL2022-23 | EPL2023-24 | EPL2024-25 |
|---|---:|---:|---:|
| climatological (baseline) | 1.0495 | 1.0551 | 1.0822 |
| Elo ordinal-logit | **1.0064** | 0.9634 | **1.0075** |
| independent Poisson | 1.0250 | **0.9494** | 1.0451 |
| time-decayed Dixon-Coles | 1.0272 | 0.9587 | 1.0452 |
| bivariate Poisson | 1.0250 | 0.9494 | 1.0451 |

Every candidate beats the climatological baseline on log loss on every fold; the best model varies by fold and none is crowned a champion.

**Calibration — most recent fold (EPL2024-25):**

| Model | Brier | ECE | RPS |
|---|---:|---:|---:|
| climatological (baseline) | 0.6565 | 0.0437 | 0.2358 |
| Elo ordinal-logit | 0.6025 | 0.0362 | 0.2092 |
| independent Poisson | 0.6296 | 0.0601 | 0.2229 |
| time-decayed Dixon-Coles | 0.6292 | 0.0536 | 0.2228 |
| bivariate Poisson | 0.6296 | 0.0601 | 0.2229 |

**Reliability — Elo ordinal-logit on EPL2024-25** (Wilson 95% intervals; empty bins omitted):

| Confidence bin | n | Empirical | Wilson 95% |
|---|---:|---:|---|
| 0.3–0.4 | 82 | 0.354 | [0.26, 0.46] |
| 0.4–0.5 | 160 | 0.475 | [0.40, 0.55] |
| 0.5–0.6 | 85 | 0.588 | [0.48, 0.69] |
| 0.6–0.7 | 42 | 0.643 | [0.49, 0.77] |
| 0.7–0.8 | 11 | 0.909 | [0.62, 0.98] |

## La Liga

- **Scope:** La Liga (historical, completed seasons only — **not live**).
- **Source snapshot:** openfootball `a5dd38b3bcbe`, retrieved 2026-07-11 (CC0-1.0).
- **Folds:** LALIGA2021-22, LALIGA2022-23, LALIGA2023-24 — strictly chronological; fitting and decay selection use only rows before each fold's cutoff.

**Log loss by fold** (primary metric; lower is better; **bold** = best in fold):

| Model | LALIGA2021-22 | LALIGA2022-23 | LALIGA2023-24 |
|---|---:|---:|---:|
| climatological (baseline) | 1.0811 | 1.0519 | 1.0767 |
| Elo ordinal-logit | 1.0058 | 1.0006 | 1.0030 |
| independent Poisson | 1.0089 | **0.9863** | 0.9743 |
| time-decayed Dixon-Coles | **1.0045** | 0.9936 | **0.9694** |
| bivariate Poisson | 1.0089 | 0.9863 | 0.9743 |

Every candidate beats the climatological baseline on log loss on every fold; the best model varies by fold and none is crowned a champion.

**Calibration — most recent fold (LALIGA2023-24):**

| Model | Brier | ECE | RPS |
|---|---:|---:|---:|
| climatological (baseline) | 0.6512 | 0.0219 | 0.2240 |
| Elo ordinal-logit | 0.5986 | 0.0711 | 0.1991 |
| independent Poisson | 0.5795 | 0.0272 | 0.1904 |
| time-decayed Dixon-Coles | 0.5765 | 0.0458 | 0.1894 |
| bivariate Poisson | 0.5795 | 0.0272 | 0.1904 |

**Reliability — time-decayed Dixon-Coles on LALIGA2023-24** (Wilson 95% intervals; empty bins omitted):

| Confidence bin | n | Empirical | Wilson 95% |
|---|---:|---:|---|
| 0.3–0.4 | 73 | 0.342 | [0.24, 0.46] |
| 0.4–0.5 | 132 | 0.508 | [0.42, 0.59] |
| 0.5–0.6 | 84 | 0.512 | [0.41, 0.62] |
| 0.6–0.7 | 53 | 0.660 | [0.53, 0.77] |
| 0.7–0.8 | 23 | 0.870 | [0.68, 0.95] |
| 0.8–0.9 | 15 | 0.867 | [0.62, 0.96] |

## Bundesliga

- **Scope:** Bundesliga (historical, completed seasons only — **not live**).
- **Source snapshot:** openfootball `a5dd38b3bcbe`, retrieved 2026-07-11 (CC0-1.0).
- **Folds:** BUNDESLIGA2022-23, BUNDESLIGA2023-24, BUNDESLIGA2024-25 — strictly chronological; fitting and decay selection use only rows before each fold's cutoff.

**Log loss by fold** (primary metric; lower is better; **bold** = best in fold):

| Model | BUNDESLIGA2022-23 | BUNDESLIGA2023-24 | BUNDESLIGA2024-25 |
|---|---:|---:|---:|
| climatological (baseline) | 1.0569 | 1.0754 | 1.0930 |
| Elo ordinal-logit | 0.9947 | 1.0264 | **1.0237** |
| independent Poisson | **0.9931** | **1.0197** | 1.0353 |
| time-decayed Dixon-Coles | 0.9970 | 1.0287 | 1.0338 |
| bivariate Poisson | 0.9931 | 1.0197 | 1.0353 |

Every candidate beats the climatological baseline on log loss on every fold; the best model varies by fold and none is crowned a champion.

**Calibration — most recent fold (BUNDESLIGA2024-25):**

| Model | Brier | ECE | RPS |
|---|---:|---:|---:|
| climatological (baseline) | 0.6643 | 0.0662 | 0.2379 |
| Elo ordinal-logit | 0.6140 | 0.0189 | 0.2130 |
| independent Poisson | 0.6217 | 0.0886 | 0.2174 |
| time-decayed Dixon-Coles | 0.6206 | 0.0837 | 0.2173 |
| bivariate Poisson | 0.6217 | 0.0886 | 0.2174 |

**Reliability — Elo ordinal-logit on BUNDESLIGA2024-25** (Wilson 95% intervals; empty bins omitted):

| Confidence bin | n | Empirical | Wilson 95% |
|---|---:|---:|---|
| 0.3–0.4 | 59 | 0.390 | [0.28, 0.52] |
| 0.4–0.5 | 139 | 0.432 | [0.35, 0.51] |
| 0.5–0.6 | 73 | 0.548 | [0.43, 0.66] |
| 0.6–0.7 | 30 | 0.733 | [0.56, 0.86] |
| 0.7–0.8 | 5 | 0.800 | [0.38, 0.96] |

## Serie A

- **Scope:** Serie A (historical, completed seasons only — **not live**).
- **Source snapshot:** openfootball `a5dd38b3bcbe`, retrieved 2026-07-11 (CC0-1.0).
- **Folds:** SERIEA2021-22, SERIEA2022-23, SERIEA2023-24 — strictly chronological; fitting and decay selection use only rows before each fold's cutoff.

**Log loss by fold** (primary metric; lower is better; **bold** = best in fold):

| Model | SERIEA2021-22 | SERIEA2022-23 | SERIEA2023-24 |
|---|---:|---:|---:|
| climatological (baseline) | 1.0900 | 1.0792 | 1.0880 |
| Elo ordinal-logit | 1.0052 | **1.0040** | 1.0182 |
| independent Poisson | 1.0065 | 1.0120 | 1.0029 |
| time-decayed Dixon-Coles | **1.0045** | 1.0091 | **0.9985** |
| bivariate Poisson | 1.0065 | 1.0120 | 1.0029 |

Every candidate beats the climatological baseline on log loss on every fold; the best model varies by fold and none is crowned a champion.

**Calibration — most recent fold (SERIEA2023-24):**

| Model | Brier | ECE | RPS |
|---|---:|---:|---:|
| climatological (baseline) | 0.6587 | 0.0144 | 0.2245 |
| Elo ordinal-logit | 0.6109 | 0.0337 | 0.2010 |
| independent Poisson | 0.6003 | 0.0279 | 0.1958 |
| time-decayed Dixon-Coles | 0.5989 | 0.0342 | 0.1957 |
| bivariate Poisson | 0.6003 | 0.0279 | 0.1958 |

**Reliability — time-decayed Dixon-Coles on SERIEA2023-24** (Wilson 95% intervals; empty bins omitted):

| Confidence bin | n | Empirical | Wilson 95% |
|---|---:|---:|---|
| 0.3–0.4 | 65 | 0.385 | [0.28, 0.51] |
| 0.4–0.5 | 121 | 0.488 | [0.40, 0.58] |
| 0.5–0.6 | 95 | 0.495 | [0.40, 0.59] |
| 0.6–0.7 | 68 | 0.662 | [0.54, 0.76] |
| 0.7–0.8 | 30 | 0.700 | [0.52, 0.83] |
| 0.8–0.9 | 1 | 0.000 | [0.00, 0.79] |

## Ligue 1

- **Scope:** Ligue 1 (historical, completed seasons only — **not live**).
- **Source snapshot:** openfootball `a5dd38b3bcbe`, retrieved 2026-07-11 (CC0-1.0).
- **Folds:** LIGUE1-2022-23, LIGUE1-2023-24, LIGUE1-2024-25 — strictly chronological; fitting and decay selection use only rows before each fold's cutoff.

**Log loss by fold** (primary metric; lower is better; **bold** = best in fold):

| Model | LIGUE1-2022-23 | LIGUE1-2023-24 | LIGUE1-2024-25 |
|---|---:|---:|---:|
| climatological (baseline) | 1.0747 | 1.0917 | 1.0535 |
| Elo ordinal-logit | **1.0190** | 1.0445 | 0.9960 |
| independent Poisson | 1.0216 | **1.0337** | **0.9794** |
| time-decayed Dixon-Coles | 1.0229 | 1.0349 | 0.9844 |
| bivariate Poisson | 1.0216 | 1.0337 | 0.9794 |

Every candidate beats the climatological baseline on log loss on every fold; the best model varies by fold and none is crowned a champion.

**Calibration — most recent fold (LIGUE1-2024-25):**

| Model | Brier | ECE | RPS |
|---|---:|---:|---:|
| climatological (baseline) | 0.6363 | 0.0302 | 0.2358 |
| Elo ordinal-logit | 0.5938 | 0.0671 | 0.2147 |
| independent Poisson | 0.5820 | 0.0591 | 0.2099 |
| time-decayed Dixon-Coles | 0.5853 | 0.0626 | 0.2103 |
| bivariate Poisson | 0.5820 | 0.0591 | 0.2099 |

**Reliability — independent Poisson on LIGUE1-2024-25** (Wilson 95% intervals; empty bins omitted):

| Confidence bin | n | Empirical | Wilson 95% |
|---|---:|---:|---|
| 0.3–0.4 | 40 | 0.425 | [0.29, 0.58] |
| 0.4–0.5 | 143 | 0.483 | [0.40, 0.56] |
| 0.5–0.6 | 76 | 0.645 | [0.53, 0.74] |
| 0.6–0.7 | 35 | 0.714 | [0.55, 0.84] |
| 0.7–0.8 | 10 | 0.700 | [0.40, 0.89] |
| 0.8–0.9 | 2 | 1.000 | [0.34, 1.00] |

## Promotion criteria for challengers

A black-box challenger (e.g. gradient boosting on engineered features, including Dixon-Coles outputs) may be considered only after: (1) at least **two full forward seasons** of evaluation, (2) better RPS **and** log loss (paired bootstrap, p < 0.05), (3) no calibration regression, and (4) a feature-attribution audit. Until then it stays a lab exhibit, not a shipped model.

Full method, leakage controls, and references: [Prediction methodology](/Golavo/methodology/prediction/).
