---
title: Prediction methodology
description: Phase 0 candidate models, chronological evaluation, calibration metrics, and leakage controls.
---

Golavo's probabilities come from a deterministic statistical engine, not from AI. This page is the honest, citable account of how they are produced.

## Baselines (kept forever as yardsticks)

1. **League-average** — empirical H/D/A frequencies over a rolling window.
2. **Elo** — `R' = R + K·G·(result − expected)`, with a margin-of-victory multiplier; internationals are seeded from the full result history since 1872.
3. **Independent Poisson** — `λ_home = exp(μ + h + attack_i − defence_j)`, `λ_away = exp(μ + attack_j − defence_i)`.

## Candidate models: time-decayed Dixon-Coles / bivariate Poisson

Phase 0 evaluates **time-decayed Dixon-Coles** and **bivariate Poisson** as candidates alongside climatological, Elo ordinal-logit, and independent-Poisson baselines. No model is a champion by declaration. The decay rate is selected on pre-test validation data only; tournament test folds are never used for tuning.

```text
fit(matches, as_of):
    w = exp(-ξ · days_between(as_of, match_date) / 365)
    maximise Σ  w · log[ τ_ρ(x, y) · Poisson(x; λ_home) · Poisson(y; λ_away) ]

predict(home, away, venue, features):
    λ_home, λ_away = base_rates × exp(Σ β_k · feature_k)   # typed features enter HERE only
    M[x, y]        = τ_ρ(x, y) · Poisson(x; λ_home) · Poisson(y; λ_away)   # score matrix
    P(home win)    = Σ_{x > y} M[x, y]                     # every market derives from M
```

Identifiability is fixed with `Σ attack = Σ defence = 0`. The decay rate `ξ`, dependence `ρ`, and home advantage `γ` are chosen by **forward** grid-search, never in-sample.

## Coherent downstream markets

- **Goalscorers, corners, shots, and lineups** — out of Phase 0. No accepted open source supplies the required full set of fields.

## Typed features (candidate inputs, all behind a gate)

Rest, congestion, travel, altitude, weather, lineups/availability, and manager effects are **candidate** features. Each ships **off** until it improves forward RPS / log loss over at least two seasons.

> We do not claim AI, deep learning, head-to-head records, or a "new-manager bounce" improve accuracy without forward, out-of-sample evidence.

## Calibration

Phase 0 reports expected calibration error plus reliability bins with Wilson intervals. Secondary calibration transforms are not enabled in Phase 0; they remain candidates for later forward validation.

## Backtesting & leakage

- **Rolling-origin** evaluation by matchday.
- Features may use only data with `retrieved_at ≤ seal time`; a synthetic future-row injection test must fail closed.
- **Determinism**: the same snapshot set must produce a bit-identical forecast.

## Metrics

**Log loss is primary.** Multiclass Brier, ECE with reliability bins and Wilson intervals, and RPS are reported per tournament fold. Count-market metrics are out of Phase 0.

## Minimum-data gates

If either team has fewer than 10 matches in the configured decay window, Phase 0 emits an abstained artifact with an explicit reason. If the match or cutoff cannot be verified, sealing fails closed.

## References

- Dixon, M. J. & Coles, S. G. (1997). *Modelling Association Football Scores and Inefficiencies in the Football Betting Market.* JRSS Series C, 46(2), 265–280.
- Ley, C., Van de Wiele, T. & Van Eetvelde, H. (2019). *Ranking soccer teams on the basis of their current strength.* (arXiv:1705.09575.)
- scikit-learn, *Probability calibration.*
