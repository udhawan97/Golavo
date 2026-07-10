---
title: Introduction
description: What Golavo is, what it is not, and the principles that keep it trustworthy.
---

Golavo is a local-first, open-source football forecasting project. Phase 0 implements reproducible sealing and scoring for men's senior full internationals; a public calibration ledger and desktop application are planned (ADR-0001).

## What Golavo is

- A **Phase 0 forecast artifact pipeline**: sealed pre-kickoff JSON artifacts are replayable and never mutated when scored.
- A **provenance-first engine**: each artifact records the pinned source snapshot and content hashes.
- A **local source-mode core and API**. The hash-chained ledger, fact engine, AI layer, and desktop app are planned (ADR-0001).

## What Golavo is not

- Not a **livescore** app — open-core results are delayed.
- Not a **betting** tool — no odds, picks, "locks," bankroll advice, or affiliate links.
- Not an **AI predictor** — the statistical engine owns every probability.
- Not a **data redistributor** — proprietary feeds are bring-your-own-key and never re-shared.

## Product principles

1. The statistical engine owns every probability.
2. Every displayed fact has a source id, or it doesn't ship.
3. Missing data is a first-class state, never silently interpolated.
4. AI explains, researches, and proposes typed facts — it never edits numbers.
5. Coincidence is not evidence, and the UI says which is which.
6. Local by default; network access is opt-in and visible.
7. No betting surface, ever.

## The words we use carefully

| Term | What it means in Golavo |
|---|---|
| **Local** | All computation runs on your machine over data already synced to disk. Staleness is always shown. |
| **Offline** | Phase 0 forecasting and API reads work from the vendored snapshot; rebuilding a sourcepack requires network access. |
| **AI** | Planned (ADR-0001), out of Phase 0. Its contract permits cited narrative, never probability ownership. |
| **Open** | The code is Apache-2.0; data packs declare their own license. The Phase 0 pack is CC0-1.0. |
| **Free** | No payment to Golavo, ever. Optional third-party keys/AI are paid by you, to those providers. |
| **Live** | Golavo is not live. Phase 0 uses a pinned snapshot and records its retrieval time. |
