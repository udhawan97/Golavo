---
title: Prediction methodology
description: Candidate models, chronological evaluation, calibration metrics, and leakage controls.
---

Golavo's probabilities come from a deterministic statistical engine, not from AI. This page is the honest, citable account of how they are produced.

## Baselines (kept forever as yardsticks)

1. **League-average** — empirical H/D/A frequencies over a rolling window.
2. **Elo** — `R' = R + K·G·(result − expected)`, with a margin-of-victory multiplier; internationals are seeded from the full result history since 1872.
3. **Independent Poisson** — `λ_home = exp(μ + h + attack_i − defence_j)`, `λ_away = exp(μ + attack_j − defence_i)`.

## Candidate models: time-decayed Dixon-Coles / bivariate Poisson

Golavo evaluates **time-decayed Dixon-Coles** and **bivariate Poisson** as candidates alongside climatological, Elo ordinal-logit, and independent-Poisson baselines. No model is a champion by declaration. The decay rate is selected on pre-test validation data only; tournament test folds are never used for tuning.

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

## Exact-score distribution & coherence

For the goal-based families (independent, Dixon-Coles, bivariate Poisson) the score matrix `M` above is not a throwaway intermediate — the sealed artifact carries it as an additive `forecast.score_matrix`. It is the exact-score distribution the 1X2 numbers **already implied**, surfaced honestly rather than recomputed.

**Representation.** A display grid of concrete scorelines `0..N` per side (`N = 7`) plus a single **`N+` tail bucket** decomposed by outcome (`home / draw / away`). Grid + tail is an exact re-bucketing of `M`, so the win/draw/loss cells reconstruct without ambiguity — no aggregated corner is left un-attributable.

**Coherence by shared source.** The sealed 1X2 probabilities, the expected goals, and the grid are all derived from **one** matrix, integrated to 20 goals per side (so truncation is below `1e-7` even at the rate clip). Because they come from the same object, they cannot drift apart. This is enforced as a machine-checked invariant, not a convention:

- **Artifact-level** (needs only the stored JSON): `validate_artifact` reproduces W/D/L from `grid + tail` on **every load** and rejects any matrix whose marginals miss `forecast.probs` by more than `1e-5`. A hand-edited or incoherent grid never renders.
- **Model-level** (checked at seal time and in tests): the matrix mean reproduces `forecast.expected_goals` to within `1e-4`, and re-deriving the model yields a byte-identical grid. An incoherent matrix **aborts the seal** rather than being written.

**No calibration transform to desync.** Golavo applies no post-hoc probability re-scaler to a seal; its "calibration" is the empirical reliability ledger (below), not a transform. The grid and the 1X2 are therefore both raw outputs of the same fitted model — there is nothing that could be applied to one and not the other. If a secondary calibration transform is ever introduced, it must act on the joint distribution and re-derive the marginals; the coherence checks would catch any asymmetric application.

**Honest absence.** Families that model outcomes rather than goals (climatological, Elo ordinal-logit) imply no exact-score distribution, so the field is **absent** — the UI shows "no grid for this model," never a fabricated one. Abstained seals carry no matrix at all.

## Coherent downstream markets

- **Goalscorers, corners, shots, and lineups** — still out. No accepted open source supplies the required full set of fields (club goalscorers, corners, and xG have **no** open feed at all; martj42 ships goalscorers for internationals only). The exact-score grid is the one coherent downstream market Golavo can derive from the sealed model without new data.

## Typed features (candidate inputs, all behind a gate)

Rest, congestion, travel, altitude, weather, lineups/availability, and manager effects are **candidate** features. Each ships **off** until it improves forward RPS / log loss over at least two seasons.

> We do not claim AI, deep learning, head-to-head records, or a "new-manager bounce" improve accuracy without forward, out-of-sample evidence.

## Calibration

Golavo reports expected calibration error plus reliability bins with Wilson intervals. Secondary calibration transforms are not enabled; they remain candidates for later forward validation.

## Backtesting & leakage

- **Rolling-origin** evaluation by matchday.
- Features may use only data with `retrieved_at ≤ seal time`; a synthetic future-row injection test must fail closed.
- **Determinism**: the same snapshot set must produce a bit-identical forecast.

## Metrics

**Log loss is primary.** Multiclass Brier, ECE with reliability bins and Wilson intervals, and RPS are reported per tournament fold. Count-market metrics are not reported.

## Minimum-data gates

If either team has fewer than 10 matches in the configured decay window, Golavo emits an abstained artifact with an explicit reason. If the match or cutoff cannot be verified, sealing fails closed.

## References

- Dixon, M. J. & Coles, S. G. (1997). *Modelling Association Football Scores and Inefficiencies in the Football Betting Market.* JRSS Series C, 46(2), 265–280.
- Ley, C., Van de Wiele, T. & Van Eetvelde, H. (2019). *Ranking soccer teams on the basis of their current strength.* (arXiv:1705.09575.)
- scikit-learn, *Probability calibration.*
