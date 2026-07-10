---
title: Prediction methodology
description: The statistical models behind Golavo's forecasts — baselines, the Dixon-Coles / bivariate-Poisson champion, calibration, and how nothing ships without forward evidence.
---

Golavo's probabilities come from a deterministic statistical engine, not from AI. This page is the honest, citable account of how they are produced.

## Baselines (kept forever as yardsticks)

1. **League-average** — empirical H/D/A frequencies over a rolling window.
2. **Elo** — `R' = R + K·G·(result − expected)`, with a margin-of-victory multiplier; internationals are seeded from the full result history since 1872.
3. **Independent Poisson** — `λ_home = exp(μ + h + attack_i − defence_j)`, `λ_away = exp(μ + attack_j − defence_i)`.

## Champion: time-decayed Dixon-Coles / bivariate Poisson

The primary model is a **time-decayed Dixon-Coles** model (Dixon & Coles, 1997) with the low-score dependence correction, fitted by weighted pseudo-likelihood with exponential time-decay weights `w(t) = exp(−ξ·Δt)`. A **bivariate Poisson** co-champion captures score correlation directly. This family is empirically among the best for forecasting from historical results (Ley, Van de Wiele & Van Eetvelde, 2019, on Rank Probability Score).

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

- **Goalscorers** — each team's goals are allocated to players by a decayed non-penalty goal share × expected minutes, with penalty takers boosted; `Σ player shares = 1` per team. A scorer's probability can never contradict the score matrix.
- **Corners** — a **negative-binomial** model (overdispersion beats plain Poisson). Ships only when a lawful data source is available; otherwise shown as *unavailable*.
- **Shots / shots-on-target** — a display-only funnel re-weighted so its implied goal distribution matches the score matrix.

## Typed features (candidate inputs, all behind a gate)

Rest, congestion, travel, altitude, weather, lineups/availability, and manager effects are **candidate** features. Each ships **off** until it improves forward RPS / log loss over at least two seasons.

> We do not claim AI, deep learning, head-to-head records, or a "new-manager bounce" improve accuracy without forward, out-of-sample evidence.

## Calibration

Primary calibration is the forward fit of `(ξ, ρ, γ, dispersion)`. A secondary temperature scaling is applied **to the score matrix** (power + renormalize) so that W/D/L, totals, and exact scores stay mutually coherent. Per scikit-learn's guidance, isotonic calibration is used only where there are well over ~1000 calibration samples; otherwise sigmoid/temperature scaling is preferred. Calibration is reported with reliability diagrams and Wilson intervals in the [model cards](/Golavo/methodology/model-cards/).

## Backtesting & leakage

- **Rolling-origin** evaluation by matchday.
- Features may use only data with `retrieved_at ≤ seal time`; a synthetic future-row injection test must fail closed.
- **Determinism**: the same snapshot set must produce a bit-identical forecast.

## Metrics

Rank Probability Score (headline), log loss, multiclass Brier, count log score (goals/corners), CRPS, and reliability diagrams — all published per competition.

## Minimum-data gates

Below ~8 in-window matches per team (or missing league priors), Golavo abstains from the exact-score matrix and widens the W/D/L interval with an "insufficient data" badge. If the fixtures themselves cannot be verified, no forecast is produced.

## References

- Dixon, M. J. & Coles, S. G. (1997). *Modelling Association Football Scores and Inefficiencies in the Football Betting Market.* JRSS Series C, 46(2), 265–280.
- Ley, C., Van de Wiele, T. & Van Eetvelde, H. (2019). *Ranking soccer teams on the basis of their current strength.* (arXiv:1705.09575.)
- scikit-learn, *Probability calibration.*
