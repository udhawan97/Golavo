---
title: Model cards & calibration
description: Every shipped model carries a card with its data window, features, metrics, and calibration diagrams.
---

Every model Golavo ships carries a **model card**, generated per release. Model cards are how you audit the engine.

## What a model card contains

- **Scope** — competitions and seasons the model is fit for.
- **Data window** — training range and the decay rate `ξ`.
- **Features** — the exact typed features enabled, and each one's forward-evidence justification.
- **Metrics** — out-of-sample RPS, log loss, Brier, and (for counts) CRPS, per competition.
- **Calibration** — reliability diagrams with Wilson confidence intervals.
- **Baselines** — head-to-head vs league-average, Elo, and independent Poisson.
- **Data era** — for models using the CC-BY Wyscout priors (frozen at 2017/18), the era is stamped so drift is visible.
- **Known limits** — where the model abstains or widens.

## Promotion criteria for challengers

A black-box challenger (e.g. gradient boosting on engineered features, including the Dixon-Coles outputs) may replace or augment the champion only after:

1. at least **two full forward seasons** of evaluation,
2. better RPS **and** log loss (paired bootstrap, p < 0.05),
3. no calibration regression, and
4. a feature-attribution audit.

Until then it stays a lab exhibit, not a shipped model.

:::note[Status]
Model cards are generated starting in Phase 1, once the calibration harness lands. See the [Roadmap](/Golavo/roadmap/).
:::
