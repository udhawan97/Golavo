---
title: Introduction
description: What Golavo is, what it is not, and the principles that keep it trustworthy.
---

Golavo is a local-first, open-source football forecasting project. It implements reproducible sealing and scoring for men's senior full internationals (a forward seal→score loop with a real calibration record), backtests the top-5 European leagues (historical), ships an optional off-by-default AI narration layer, and builds an unsigned desktop app. A **hash-chained** multi-artifact ledger and confirmed-lineup / BYOK data adapters remain planned (ADR-0001).

## What Golavo is

- A **forward forecast pipeline**: sealed pre-kickoff JSON artifacts are replayable and never mutated when scored.
- A **provenance-first engine**: each artifact records the pinned source snapshot and content hashes.
- A **local source-mode core, API, and desktop app**, with an optional AI layer that is off by default. A built-in Ollama guide can install and assign recommended Fast/Deep models with visible progress; the deterministic **fact engine** (the Commentator's Notebook) remains useful without AI. The hash-chained multi-artifact ledger remains planned (ADR-0001).

## What Golavo is not

- Not a **livescore** app — open-core results are delayed.
- Not a **betting** tool — no odds, picks, "locks," bankroll advice, or affiliate links.
- Not an **AI predictor** — the statistical engine owns every probability.
- Not a **data redistributor** — vendored packs are CC0; proprietary-feed adapters are planned as bring-your-own-key and would never be re-shared.

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
| **Offline** | Forecasting and API reads work from the vendored snapshot; rebuilding a sourcepack requires network access. |
| **AI** | Implemented and **off by default**. Its contract permits cited narrative, never probability ownership; it cannot change or improve a number. |
| **Open** | The code is Apache-2.0; data packs declare their own license. The vendored packs are CC0-1.0. |
| **Free** | No payment to Golavo, ever. Optional third-party keys/AI are paid by you, to those providers. |
| **Live** | Golavo is not live. It uses pinned snapshots and records their retrieval time. |
