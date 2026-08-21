---
title: Model cards & calibration
description: Per-competition model cards with skill intervals, real backtest metrics, and reliability diagrams.
---

These cards report the **actual** out-of-sample backtest metrics Golavo emits, one card per competition. They are generated from the schema-validated `eval_summary*.json` artifacts by `scripts/build_model_cards.py` — never hand-edited — so the numbers here match what CI validates. **Log loss is primary.** No model is a declared champion; forward evidence (the [calibration record](/Golavo/prediction-ledger/)) is kept separate from these historical folds.

:::note[How to read a card]
Each card lists every deterministic candidate evaluated on that competition against the climatological baseline — the five seated families everywhere, plus any club-league candidate on trial in the domestic cards. Skill is `1 - model log loss / baseline log loss`; its 95% interval is a seeded, fold-stratified bootstrap over held-out matches. Metrics are out-of-sample on strictly chronological folds. League strengths are **not** comparable across competitions — each league is modeled independently from its own pack.
:::

## Men's senior full internationals

- **Scope:** Men's senior full internationals (forward seal→score surface plus these historical test folds).
- **Source snapshot:** martj42/international_results `ddd7249ac0c2`, retrieved 2026-07-10 (CC0-1.0).
- **Folds:** WC2022, EURO2024, WC2026 — strictly chronological; fitting and decay selection use only rows before each fold's cutoff.

**Competition report cards** (positive skill means lower log loss than climatology):

**FIFA World Cup report card** (2022-11-20 to 2026-07-19):

| Model | Matches / folds | Log loss | Skill vs baseline (95% CI) | ECE | Fold rank |
|---|---:|---:|---:|---:|---:|
| climatological (baseline) | 161 / 2 | 1.0636 | +0.0% (+0.0% to +0.0%) | 0.0310 | 5.0 (5–5) |
| Elo ordinal-logit | 161 / 2 | 0.9494 | +10.7% (+5.6% to +15.4%) | 0.1559 | 1.0 (1–1) |
| independent Poisson | 161 / 2 | 1.0027 | +5.7% (+0.7% to +10.6%) | 0.0972 | 3.0 (3–3) |
| time-decayed Dixon-Coles | 161 / 2 | 1.0000 | +6.0% (+0.6% to +10.9%) | 0.0920 | 2.0 (2–2) |
| bivariate Poisson | 161 / 2 | 1.0027 | +5.7% (+0.5% to +10.5%) | 0.0972 | 4.0 (4–4) |

Skill intervals use 2,000 seeded, fold-stratified match-bootstrap samples.

**UEFA Euro report card** (2024-06-14 to 2024-07-14):

| Model | Matches / folds | Log loss | Skill vs baseline (95% CI) | ECE | Fold rank |
|---|---:|---:|---:|---:|---:|
| climatological (baseline) | 51 / 1 | 1.1422 | +0.0% (+0.0% to +0.0%) | 0.1377 | 5.0 (5–5) |
| Elo ordinal-logit | 51 / 1 | 1.0300 | +9.8% (+1.3% to +17.4%) | 0.0625 | 4.0 (4–4) |
| independent Poisson | 51 / 1 | 1.0228 | +10.5% (+3.4% to +17.2%) | 0.0887 | 2.0 (2–2) |
| time-decayed Dixon-Coles | 51 / 1 | 0.9973 | +12.7% (+4.5% to +19.8%) | 0.0890 | 1.0 (1–1) |
| bivariate Poisson | 51 / 1 | 1.0228 | +10.5% (+3.6% to +17.7%) | 0.0887 | 3.0 (3–3) |

Skill intervals use 2,000 seeded, fold-stratified match-bootstrap samples.

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
- **Folds:** EPL2023-24, EPL2024-25, EPL2025-26 — strictly chronological; fitting and decay selection use only rows before each fold's cutoff.

**Competition report cards** (positive skill means lower log loss than climatology):

**English Premier League report card** (2023-08-01 to 2026-06-30):

| Model | Matches / folds | Log loss | Skill vs baseline (95% CI) | ECE | Fold rank |
|---|---:|---:|---:|---:|---:|
| climatological (baseline) | 1140 / 3 | 1.0732 | +0.0% (+0.0% to +0.0%) | 0.0252 | 6.0 (6–6) |
| Elo ordinal-logit | 1140 / 3 | 1.0065 | +6.2% (+4.6% to +7.7%) | 0.0579 | 3.7 (1–5) |
| independent Poisson | 1140 / 3 | 1.0105 | +5.8% (+4.0% to +7.6%) | 0.0543 | 2.3 (1–3) |
| time-decayed Dixon-Coles | 1140 / 3 | 1.0112 | +5.8% (+4.0% to +7.5%) | 0.0575 | 3.3 (1–5) |
| bivariate Poisson | 1140 / 3 | 1.0105 | +5.8% (+4.0% to +7.7%) | 0.0543 | 3.3 (2–4) |
| Dixon-Coles with per-club home advantage and rest days | 1140 / 3 | 1.0115 | +5.7% (+3.9% to +7.6%) | 0.0679 | 2.3 (2–3) |

Skill intervals use 2,000 seeded, fold-stratified match-bootstrap samples.

**Log loss by fold** (primary metric; lower is better; **bold** = best in fold):

| Model | EPL2023-24 | EPL2024-25 | EPL2025-26 |
|---|---:|---:|---:|
| climatological (baseline) | 1.0551 | 1.0822 | 1.0823 |
| Elo ordinal-logit | 0.9634 | **1.0075** | 1.0487 |
| independent Poisson | **0.9494** | 1.0451 | 1.0370 |
| time-decayed Dixon-Coles | 0.9587 | 1.0452 | **1.0298** |
| bivariate Poisson | 0.9494 | 1.0451 | 1.0370 |
| Dixon-Coles with per-club home advantage and rest days | 0.9582 | 1.0428 | 1.0336 |

Every candidate beats the climatological baseline on log loss on every fold; the best model varies by fold and none is crowned a champion.

**Calibration — most recent fold (EPL2025-26):**

| Model | Brier | ECE | RPS |
|---|---:|---:|---:|
| climatological (baseline) | 0.6551 | 0.0224 | 0.2276 |
| Elo ordinal-logit | 0.6322 | 0.0390 | 0.2164 |
| independent Poisson | 0.6236 | 0.0438 | 0.2120 |
| time-decayed Dixon-Coles | 0.6183 | 0.0591 | 0.2100 |
| bivariate Poisson | 0.6236 | 0.0438 | 0.2120 |
| Dixon-Coles with per-club home advantage and rest days | 0.6215 | 0.0806 | 0.2117 |

**Reliability — time-decayed Dixon-Coles on EPL2025-26** (Wilson 95% intervals; empty bins omitted):

| Confidence bin | n | Empirical | Wilson 95% |
|---|---:|---:|---|
| 0.3–0.4 | 71 | 0.493 | [0.38, 0.61] |
| 0.4–0.5 | 162 | 0.364 | [0.29, 0.44] |
| 0.5–0.6 | 90 | 0.544 | [0.44, 0.64] |
| 0.6–0.7 | 48 | 0.667 | [0.53, 0.78] |
| 0.7–0.8 | 9 | 0.778 | [0.45, 0.94] |

## La Liga

- **Scope:** La Liga (historical, completed seasons only — **not live**).
- **Source snapshot:** openfootball `a5dd38b3bcbe`, retrieved 2026-07-11 (CC0-1.0).
- **Folds:** LALIGA2022-23, LALIGA2023-24, LALIGA2025-26 — strictly chronological; fitting and decay selection use only rows before each fold's cutoff.

**Competition report cards** (positive skill means lower log loss than climatology):

**La Liga report card** (2022-08-01 to 2026-06-30):

| Model | Matches / folds | Log loss | Skill vs baseline (95% CI) | ECE | Fold rank |
|---|---:|---:|---:|---:|---:|
| climatological (baseline) | 1140 / 3 | 1.0590 | +0.0% (+0.0% to +0.0%) | 0.0241 | 6.0 (6–6) |
| Elo ordinal-logit | 1140 / 3 | 0.9994 | +5.6% (+4.1% to +7.2%) | 0.0663 | 5.0 (5–5) |
| independent Poisson | 1140 / 3 | 0.9830 | +7.2% (+5.3% to +9.0%) | 0.0457 | 2.0 (1–3) |
| time-decayed Dixon-Coles | 1140 / 3 | 0.9840 | +7.1% (+5.1% to +9.0%) | 0.0533 | 2.3 (1–3) |
| bivariate Poisson | 1140 / 3 | 0.9830 | +7.2% (+5.3% to +9.0%) | 0.0457 | 2.3 (1–4) |
| Dixon-Coles with per-club home advantage and rest days | 1140 / 3 | 0.9876 | +6.7% (+4.7% to +8.7%) | 0.0394 | 3.3 (2–4) |

Skill intervals use 2,000 seeded, fold-stratified match-bootstrap samples.

**Log loss by fold** (primary metric; lower is better; **bold** = best in fold):

| Model | LALIGA2022-23 | LALIGA2023-24 | LALIGA2025-26 |
|---|---:|---:|---:|
| climatological (baseline) | 1.0519 | 1.0767 | 1.0484 |
| Elo ordinal-logit | 1.0006 | 1.0030 | 0.9946 |
| independent Poisson | **0.9863** | 0.9743 | 0.9883 |
| time-decayed Dixon-Coles | 0.9936 | **0.9694** | 0.9891 |
| bivariate Poisson | 0.9863 | 0.9743 | **0.9883** |
| Dixon-Coles with per-club home advantage and rest days | 0.9986 | 0.9725 | 0.9917 |

Every candidate beats the climatological baseline on log loss on every fold; the best model varies by fold and none is crowned a champion.

**Calibration — most recent fold (LALIGA2025-26):**

| Model | Brier | ECE | RPS |
|---|---:|---:|---:|
| climatological (baseline) | 0.6314 | 0.0309 | 0.2232 |
| Elo ordinal-logit | 0.5915 | 0.0711 | 0.2049 |
| independent Poisson | 0.5870 | 0.0600 | 0.2032 |
| time-decayed Dixon-Coles | 0.5874 | 0.0578 | 0.2033 |
| bivariate Poisson | 0.5870 | 0.0600 | 0.2032 |
| Dixon-Coles with per-club home advantage and rest days | 0.5892 | 0.0557 | 0.2040 |

**Reliability — bivariate Poisson on LALIGA2025-26** (Wilson 95% intervals; empty bins omitted):

| Confidence bin | n | Empirical | Wilson 95% |
|---|---:|---:|---|
| 0.3–0.4 | 72 | 0.333 | [0.24, 0.45] |
| 0.4–0.5 | 143 | 0.483 | [0.40, 0.56] |
| 0.5–0.6 | 95 | 0.484 | [0.39, 0.58] |
| 0.6–0.7 | 40 | 0.775 | [0.62, 0.88] |
| 0.7–0.8 | 27 | 0.852 | [0.68, 0.94] |
| 0.8–0.9 | 3 | 1.000 | [0.44, 1.00] |

## Bundesliga

- **Scope:** Bundesliga (historical, completed seasons only — **not live**).
- **Source snapshot:** openfootball `a5dd38b3bcbe`, retrieved 2026-07-11 (CC0-1.0).
- **Folds:** BUNDESLIGA2023-24, BUNDESLIGA2024-25, BUNDESLIGA2025-26 — strictly chronological; fitting and decay selection use only rows before each fold's cutoff.

**Competition report cards** (positive skill means lower log loss than climatology):

**Bundesliga report card** (2023-08-01 to 2026-06-30):

| Model | Matches / folds | Log loss | Skill vs baseline (95% CI) | ECE | Fold rank |
|---|---:|---:|---:|---:|---:|
| climatological (baseline) | 918 / 3 | 1.0797 | +0.0% (+0.0% to +0.0%) | 0.0302 | 6.0 (6–6) |
| Elo ordinal-logit | 918 / 3 | 1.0144 | +6.0% (+4.5% to +7.7%) | 0.0405 | 3.0 (1–5) |
| independent Poisson | 918 / 3 | 1.0085 | +6.6% (+4.6% to +8.6%) | 0.0666 | 2.7 (1–4) |
| time-decayed Dixon-Coles | 918 / 3 | 1.0104 | +6.4% (+4.4% to +8.4%) | 0.0625 | 3.0 (2–4) |
| bivariate Poisson | 918 / 3 | 1.0085 | +6.6% (+4.7% to +8.6%) | 0.0666 | 3.7 (2–5) |
| Dixon-Coles with per-club home advantage and rest days | 918 / 3 | 1.0104 | +6.4% (+4.4% to +8.4%) | 0.0698 | 2.7 (1–5) |

Skill intervals use 2,000 seeded, fold-stratified match-bootstrap samples.

**Log loss by fold** (primary metric; lower is better; **bold** = best in fold):

| Model | BUNDESLIGA2023-24 | BUNDESLIGA2024-25 | BUNDESLIGA2025-26 |
|---|---:|---:|---:|
| climatological (baseline) | 1.0754 | 1.0930 | 1.0706 |
| Elo ordinal-logit | 1.0264 | **1.0237** | 0.9931 |
| independent Poisson | **1.0197** | 1.0353 | 0.9704 |
| time-decayed Dixon-Coles | 1.0287 | 1.0338 | 0.9687 |
| bivariate Poisson | 1.0197 | 1.0353 | 0.9704 |
| Dixon-Coles with per-club home advantage and rest days | 1.0369 | 1.0322 | **0.9621** |

Every candidate beats the climatological baseline on log loss on every fold; the best model varies by fold and none is crowned a champion.

**Calibration — most recent fold (BUNDESLIGA2025-26):**

| Model | Brier | ECE | RPS |
|---|---:|---:|---:|
| climatological (baseline) | 0.6478 | 0.0095 | 0.2314 |
| Elo ordinal-logit | 0.5916 | 0.0767 | 0.2039 |
| independent Poisson | 0.5740 | 0.0628 | 0.1957 |
| time-decayed Dixon-Coles | 0.5734 | 0.0593 | 0.1956 |
| bivariate Poisson | 0.5740 | 0.0628 | 0.1957 |
| Dixon-Coles with per-club home advantage and rest days | 0.5697 | 0.0476 | 0.1938 |

**Reliability — Dixon-Coles with per-club home advantage and rest days on BUNDESLIGA2025-26** (Wilson 95% intervals; empty bins omitted):

| Confidence bin | n | Empirical | Wilson 95% |
|---|---:|---:|---|
| 0.3–0.4 | 60 | 0.400 | [0.29, 0.53] |
| 0.4–0.5 | 108 | 0.426 | [0.34, 0.52] |
| 0.5–0.6 | 69 | 0.551 | [0.43, 0.66] |
| 0.6–0.7 | 45 | 0.800 | [0.66, 0.89] |
| 0.7–0.8 | 16 | 0.938 | [0.72, 0.99] |
| 0.8–0.9 | 8 | 0.750 | [0.41, 0.93] |

## Serie A

- **Scope:** Serie A (historical, completed seasons only — **not live**).
- **Source snapshot:** openfootball `a5dd38b3bcbe`, retrieved 2026-07-11 (CC0-1.0).
- **Folds:** SERIEA2022-23, SERIEA2023-24, SERIEA2025-26 — strictly chronological; fitting and decay selection use only rows before each fold's cutoff.

**Competition report cards** (positive skill means lower log loss than climatology):

**Serie A report card** (2022-08-01 to 2026-06-30):

| Model | Matches / folds | Log loss | Skill vs baseline (95% CI) | ECE | Fold rank |
|---|---:|---:|---:|---:|---:|
| climatological (baseline) | 1140 / 3 | 1.0855 | +0.0% (+0.0% to +0.0%) | 0.0214 | 6.0 (6–6) |
| Elo ordinal-logit | 1140 / 3 | 1.0108 | +6.9% (+5.4% to +8.3%) | 0.0439 | 2.7 (1–5) |
| independent Poisson | 1140 / 3 | 1.0085 | +7.1% (+5.2% to +9.0%) | 0.0398 | 3.0 (3–3) |
| time-decayed Dixon-Coles | 1140 / 3 | 1.0057 | +7.3% (+5.4% to +9.2%) | 0.0398 | 1.7 (1–2) |
| bivariate Poisson | 1140 / 3 | 1.0085 | +7.1% (+5.2% to +9.0%) | 0.0398 | 4.0 (4–4) |
| Dixon-Coles with per-club home advantage and rest days | 1140 / 3 | 1.0071 | +7.2% (+5.2% to +9.1%) | 0.0460 | 3.7 (1–5) |

Skill intervals use 2,000 seeded, fold-stratified match-bootstrap samples.

**Log loss by fold** (primary metric; lower is better; **bold** = best in fold):

| Model | SERIEA2022-23 | SERIEA2023-24 | SERIEA2025-26 |
|---|---:|---:|---:|
| climatological (baseline) | 1.0792 | 1.0880 | 1.0892 |
| Elo ordinal-logit | **1.0040** | 1.0182 | 1.0102 |
| independent Poisson | 1.0120 | 1.0029 | 1.0106 |
| time-decayed Dixon-Coles | 1.0091 | 0.9985 | **1.0096** |
| bivariate Poisson | 1.0120 | 1.0029 | 1.0106 |
| Dixon-Coles with per-club home advantage and rest days | 1.0136 | **0.9967** | 1.0109 |

Every candidate beats the climatological baseline on log loss on every fold; the best model varies by fold and none is crowned a champion.

**Calibration — most recent fold (SERIEA2025-26):**

| Model | Brier | ECE | RPS |
|---|---:|---:|---:|
| climatological (baseline) | 0.6609 | 0.0397 | 0.2341 |
| Elo ordinal-logit | 0.6042 | 0.0401 | 0.2063 |
| independent Poisson | 0.6048 | 0.0386 | 0.2064 |
| time-decayed Dixon-Coles | 0.6042 | 0.0193 | 0.2063 |
| bivariate Poisson | 0.6048 | 0.0386 | 0.2064 |
| Dixon-Coles with per-club home advantage and rest days | 0.6048 | 0.0358 | 0.2067 |

**Reliability — time-decayed Dixon-Coles on SERIEA2025-26** (Wilson 95% intervals; empty bins omitted):

| Confidence bin | n | Empirical | Wilson 95% |
|---|---:|---:|---|
| 0.3–0.4 | 69 | 0.304 | [0.21, 0.42] |
| 0.4–0.5 | 134 | 0.448 | [0.37, 0.53] |
| 0.5–0.6 | 104 | 0.548 | [0.45, 0.64] |
| 0.6–0.7 | 57 | 0.649 | [0.52, 0.76] |
| 0.7–0.8 | 16 | 0.875 | [0.64, 0.97] |

## Ligue 1

- **Scope:** Ligue 1 (historical, completed seasons only — **not live**).
- **Source snapshot:** openfootball `a5dd38b3bcbe`, retrieved 2026-07-11 (CC0-1.0).
- **Folds:** LIGUE1-2022-23, LIGUE1-2023-24, LIGUE1-2024-25 — strictly chronological; fitting and decay selection use only rows before each fold's cutoff.

**Competition report cards** (positive skill means lower log loss than climatology):

**Ligue 1 report card** (2022-08-01 to 2025-06-30):

| Model | Matches / folds | Log loss | Skill vs baseline (95% CI) | ECE | Fold rank |
|---|---:|---:|---:|---:|---:|
| climatological (baseline) | 992 / 3 | 1.0734 | +0.0% (+0.0% to +0.0%) | 0.0298 | 6.0 (6–6) |
| Elo ordinal-logit | 992 / 3 | 1.0198 | +5.0% (+3.4% to +6.5%) | 0.0485 | 3.7 (1–5) |
| independent Poisson | 992 / 3 | 1.0123 | +5.7% (+3.7% to +7.6%) | 0.0543 | 1.3 (1–2) |
| time-decayed Dixon-Coles | 992 / 3 | 1.0148 | +5.5% (+3.6% to +7.4%) | 0.0437 | 3.3 (3–4) |
| bivariate Poisson | 992 / 3 | 1.0123 | +5.7% (+3.9% to +7.6%) | 0.0543 | 2.3 (2–3) |
| Dixon-Coles with per-club home advantage and rest days | 992 / 3 | 1.0174 | +5.2% (+3.2% to +7.2%) | 0.0561 | 4.3 (4–5) |

Skill intervals use 2,000 seeded, fold-stratified match-bootstrap samples.

**Log loss by fold** (primary metric; lower is better; **bold** = best in fold):

| Model | LIGUE1-2022-23 | LIGUE1-2023-24 | LIGUE1-2024-25 |
|---|---:|---:|---:|
| climatological (baseline) | 1.0747 | 1.0917 | 1.0535 |
| Elo ordinal-logit | **1.0190** | 1.0445 | 0.9960 |
| independent Poisson | 1.0216 | **1.0337** | **0.9794** |
| time-decayed Dixon-Coles | 1.0229 | 1.0349 | 0.9844 |
| bivariate Poisson | 1.0216 | 1.0337 | 0.9794 |
| Dixon-Coles with per-club home advantage and rest days | 1.0230 | 1.0397 | 0.9883 |

Every candidate beats the climatological baseline on log loss on every fold; the best model varies by fold and none is crowned a champion.

**Calibration — most recent fold (LIGUE1-2024-25):**

| Model | Brier | ECE | RPS |
|---|---:|---:|---:|
| climatological (baseline) | 0.6363 | 0.0302 | 0.2358 |
| Elo ordinal-logit | 0.5938 | 0.0671 | 0.2147 |
| independent Poisson | 0.5820 | 0.0591 | 0.2099 |
| time-decayed Dixon-Coles | 0.5853 | 0.0626 | 0.2103 |
| bivariate Poisson | 0.5820 | 0.0591 | 0.2099 |
| Dixon-Coles with per-club home advantage and rest days | 0.5877 | 0.0660 | 0.2114 |

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
