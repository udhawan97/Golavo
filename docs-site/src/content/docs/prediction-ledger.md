---
title: The Prediction Ledger
description: How Golavo seals a forecast before kickoff and scores it after full time — and how you can verify a seal was never altered.
---

Golavo's accountability spine is the versioned `ForecastArtifact` contract. A forecast is **sealed** before kickoff and a later result produces a separate **scored** artifact; the sealed file is never mutated. The forward loop supports men's senior full internationals and fixtures in certified domestic schedules. Club settlement remains stricter: it waits for two independent result sources to agree. A read-only calibration record aggregates what happened after the whistle. Source `main` can also create local hash-chained checkpoints over the immutable forecast files, with external-authenticity, timing, migration, and recovery limits kept explicit.

:::note[Availability]
The in-app proof verifier, forecast-ledger archive/restore, local checkpoints, refresh
application receipts, and guarded calibration slices are on repository `main` after v0.18.0.
They are not in the v0.18.0 desktop installers. See [Trust Center](/Golavo/trust-center/).
:::

:::note[Seals are not picks]
A **seal** freezes a model forecast for the expert trust record. A **pick** is your score call in
the local My Season game. Picks use simple 3 / 1 / +1 points and live under the ledger's `picks/`
directory, but never enter model calibration, log loss, Brier score, or the forecast artifact chain.
See [Picks, points & My Season](/Golavo/picks-and-points/).
:::

## What a seal records

Each seal is an immutable JSON artifact (contract 0.2.0, additive over 0.1.0). The abbreviated shape is:

```text
{ artifact_id, status, supersedes, void_reason?,
  match, forecast,
  model, inputs: { training_cutoff_utc, snapshots },
  provenance: { created_at_utc, generator,
                deterministic, payload_sha256 },
  evaluation }
```

## The forward loop, honestly

Each row declares `kickoff_precision`. Rows with a verified exact kickoff close at that
instant. Date-only rows use a conservative proxy at 00:00 UTC on match day, so their seal
window closes before that midnight. Golavo never invents a precise kickoff time.

Sealing enforces three invariants:

1. **The data state must predate the seal.** `as_of` must be at or after the snapshot's *data-state anchor* — the pinned upstream ref's commit time (`upstream_committed_at_utc`, recorded by the snapshot builder and verifiable against the public upstream repository), falling back to our own retrieval time for packs built before the anchor existed. Both times are recorded; neither is ever backdated.
2. **The seal must precede the row's cutoff.** `as_of < kickoff_utc`, using either the
   verified exact instant or the declared date-only proxy above.
3. **No training leakage.** Every training row is dated at or before the cutoff, and the target fixture must still be *scheduled* (no result) in the sealing snapshot — a played match is never re-forecast as if it were upcoming.

Snapshots are **immutable and retained**: refreshing the source builds a *new* pinned pack next to the old ones, and `packs/snapshots.json` records every retained `{ref, retrieved_at_utc, manifest sha256}`. That is what makes the loop reproducible — CI replays a real seal→score transition from two vendored refs in which the same fixture moves from scheduled to completed.

**What the artifact bytes can and cannot prove.** Artifacts are deterministic (no wall
clock), so the bytes and local checkpoint chain cannot externally attest *when* they were
created. At runtime, Golavo enforces the cutoff and leakage invariants before writing a
local seal. Publishing its digest or artifact to an independently timestamped public
channel before the declared cutoff can add external timing evidence, but publication is
not automatic and is not the definition of a valid local seal. Retrospective seals against
old data states remain possible for reproducible tests; they are test artifacts, not
forward forecasts.

## Forecast horizons

| Horizon | When | Lineup state |
|---|---|---|
| **T-72h** | three days out | none |
| **T-24h** | day before | none / probable |
| **T-60m** | after team news | confirmed (BYOK required) |

The horizon label states intent; the exact `sealed_at_utc` is in the artifact. With a dates-only source, T-60m is not usable for internationals (no kickoff times exist to anchor it); lineup-aware forecasting remains planned (ADR-0001).

## After the whistle

Scoring accepts an actual result only from a validated snapshot whose data state is **strictly newer** than the seal's, and writes a new superseding artifact with outcome, log loss, Brier, and assigned probability — the seal's bytes stay fixed. A fixture that is postponed or abandoned becomes a **voided** successor with a recorded `void_reason`; a missing result is never fabricated. One seal resolves exactly once.

Real chains are aggregated into a calibration record — counts, running log loss and Brier over scored seals, reliability bins, and every sealed→scored/voided pair — served read-only at `GET /api/v1/calibration` and rendered in the workbench's **Ledger** view, entirely separate from the backtest evaluation folds.

Competition and model-family slices are predeclared and withheld independently. A slice
shows metrics only after 30 scored seals. Reliability needs at least 100 scored seals and
three populated bins with at least 20 observations each. Every slice remains a descriptive
local cut with selection and cold-start effects—not a confidence interval or model comparison.

## Verifying a seal

Each artifact carries source hashes and a SHA-256 digest over canonical JSON, so its payload can be recomputed. The snapshot descriptors inside `inputs.snapshots` pin the exact upstream refs; `scripts/validate_provenance.py` re-verifies every retained pack byte-for-byte against its manifest and the registry. The append-only audit log (`audit.jsonl`) records every artifact append.

Forecast Detail also offers **Download proof**. Its `ForecastProof` JSON contains the
connected sealed/scored/voided lineage, source descriptors, any locally matching exact
manifest bytes, contract versions, and a canonical bundle digest. `golavo verify-proof
proof.json` validates it without a Golavo ledger, pack directory, or network connection.
Source entries without embedded manifest bytes are labelled `descriptor-only`; the proof
does not upgrade absent evidence. Trust Center can inspect the same proof locally without
persisting the selected file. It reports artifact and source counts while distinguishing
embedded-manifest checks from descriptor-only sources.

## Local checkpoints and backup

A checkpoint records the ids and file hashes of every verified `fa_*.json` artifact present,
then links that snapshot to the previous local checkpoint. Verification detects changed bytes,
cycles, explicitly missing artifacts, and new artifacts not yet in the current head. It does
not prove external authenticity, when an artifact was created, or that a later explicit removal
cannot happen. Format `0.2.0` can extend a verified `0.1.0` head without rewriting its hashed
history. Optional external anchoring remains a separate gate.

The Trust Center archive can export, preview, and restore forecast artifacts, picks,
followed-match state, and the verified head-reachable checkpoint chain when present. It
accepts legacy archives, stages the archived forecast/checkpoint bytes in a disposable ledger,
and withholds restore if the resulting chain would be invalid. Team favorites, credentials,
providers, licensed overlays, weather, research captures, refresh generations, and caches are
deliberately excluded. See [Trust Center](/Golavo/trust-center/) for the conflict and recovery
path.
