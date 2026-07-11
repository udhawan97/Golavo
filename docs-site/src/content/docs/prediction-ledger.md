---
title: The Prediction Ledger
description: How Golavo seals a forecast before kickoff and scores it after full time — and how you can verify a seal was never altered.
---

Phase 0's accountability spine is the versioned `ForecastArtifact` contract. A forecast is **sealed** before kickoff and a later result produces a separate **scored** artifact. The sealed file is never mutated. A hash-chained multi-artifact ledger is planned (ADR-0001), not implemented in Phase 0.

## What a seal records

Each seal is an immutable JSON artifact. The abbreviated shape is:

```text
{ artifact_id, status, match, forecast,
  model, inputs: { training_cutoff_utc, snapshots },
  provenance: { created_at_utc, generator,
                deterministic, payload_sha256 },
  evaluation }
```

## Forecast horizons

| Horizon | When | Lineup state |
|---|---|---|
| **T-72h** | three days out | none |
| **T-24h** | day before | none / probable |
| **T-60m** | after team news | confirmed (BYOK required) |

Phase 0 does not ingest lineups. All three horizons are contract values for 1X2 regulation forecasts; lineup-aware forecasting is planned (ADR-0001).

## After the whistle

The Phase 0 scorer accepts an actual result only from a newer validated snapshot and writes a new artifact with outcome, log loss, Brier, and assigned probability. Voided sample artifacts exercise the canonical status contract; automated abandonment/postponement workflows are planned.

## Verifying a seal

Each artifact carries source hashes and a SHA-256 digest over canonical JSON, so its payload can be recomputed. Phase 0 also appends audit events. Cross-artifact chaining and its verifier remain planned for Phase 1 (ADR-0001).
