---
title: The Prediction Ledger
description: How Golavo seals a forecast before kickoff and scores it after full time — and how you can verify a seal was never altered.
---

The Prediction Ledger is Golavo's accountability spine. A forecast is **sealed** before kickoff and **scored** after full time. Seals are append-only and hash-chained, so a past prediction cannot be quietly rewritten.

## What a seal records

Each seal is an immutable row:

```text
{ match_id, horizon, sealed_at,
  p_home, p_draw, p_away, score_matrix_ref, aux_markets,
  model_version, feature_version, snapshot_set_hash,
  lineup_state ∈ { none, probable, confirmed },
  data_quality_tier }
```

## Forecast horizons

| Horizon | When | Lineup state |
|---|---|---|
| **T-72h** | three days out | none |
| **T-24h** | day before | none / probable |
| **T-60m** | after team news | confirmed (BYOK required) |

The open core can honestly reach `lineup_state = none` only. `confirmed` requires a bring-your-own-key lineup source — and the seal records exactly that.

## After the whistle

Golavo scores the sealed forecast against the actual result: per-market outcome, the contribution to running calibration, and a side-by-side of sealed-vs-actual. Abandoned matches void their seals with a reason code; postponed matches void the old seal (kept, not deleted) and re-seal for the new kickoff.

## Verifying a seal

Because each seal carries the hash of its source snapshot set and is chained to the previous seal, anyone with the ledger can recompute the chain and confirm no row was altered after the fact. The verification procedure ships with the app and is documented here once the ledger lands (Phase 1).
