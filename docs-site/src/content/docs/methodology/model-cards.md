---
title: Model cards & calibration
description: Planned Phase 1 model cards and the evaluation evidence Phase 0 emits today.
---

Phase 0 emits `eval_report.md` and a schema-validated `eval_summary.json`. Full per-release **model cards** are planned for Phase 1; the fields below are their acceptance contract.

## What a model card contains

- **Scope** — competitions and seasons the model is fit for.
- **Data window** — training range and the decay rate `ξ`.
- **Features** — the exact typed features enabled, and each one's forward-evidence justification.
- **Metrics** — out-of-sample RPS, log loss, Brier, and (for counts) CRPS, per competition.
- **Calibration** — reliability diagrams with Wilson confidence intervals.
- **Baselines** — head-to-head vs league-average, Elo, and independent Poisson.
- **Data era** — snapshot commit, retrieval timestamp, and evaluation window. Wyscout is not a Phase 0 dependency.
- **Known limits** — where the model abstains or widens.

## Promotion criteria for challengers

A black-box challenger (e.g. gradient boosting on engineered features, including Dixon-Coles outputs) may be considered only after:

1. at least **two full forward seasons** of evaluation,
2. better RPS **and** log loss (paired bootstrap, p < 0.05),
3. no calibration regression, and
4. a feature-attribution audit.

Until then it stays a lab exhibit, not a shipped model.

:::note[Status]
Phase 0 emits an evaluation report and machine-readable summary. Full release model cards remain planned for Phase 1. See the [Roadmap](/Golavo/roadmap/).
:::
