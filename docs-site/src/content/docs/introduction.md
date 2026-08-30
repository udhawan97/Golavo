---
title: Introduction
description: What Golavo is, what it is not, and the principles that keep it trustworthy.
---

Golavo is a local-first, open-source football forecasting project. It implements reproducible sealing and scoring for men's senior full internationals and certified domestic fixtures, backtests the top-5 European leagues, exposes a compact deterministic Match Study Desk, competition-local analytics, honest outlook gates, and a separate women-first World Cup history archive, ships optional off-by-default AI narration plus BYOK Sportmonks outside-signal and bounded Transfer Desk panels, and builds an OS-unsigned desktop app whose updater and active data-pack manifests are authenticated. The local integrity workbench also has hash-chained ledger checkpoints, backward-compatible chain continuation, and a disposable recovery drill with explicit limits; optional external anchoring and any player-data model-input adapter remain gated.

## What Golavo is

- A **forward forecast pipeline**: sealed pre-kickoff JSON artifacts are replayable and never mutated when scored.
- A **provenance-first engine**: each artifact records the pinned source snapshot and content hashes, and can export a portable offline-verifiable lineage proof.
- A **local source-mode core, API, and desktop app**, with an optional AI layer that is off by default. A built-in Ollama guide can install and assign recommended Fast/Deep models with visible progress; the deterministic **fact engine** (the Commentator's Notebook) remains useful without AI.
- A **local integrity workbench**: proof inspection, an allowlisted ledger archive/restore path with checkpoint recovery rehearsal, application receipts, and checkpoints that detect changes relative to earlier local heads without claiming external authenticity or timing.

:::note[Release boundary]
v0.19.0 is the intended packaged milestone described here. Provider-backed panels still require
the user's own account, token, entitlement, and foreground fetch. Trust Center restore or checkpoint
creation specifically requires the installed desktop app's private launch token.
:::

## What Golavo is not

- Not a **livescore** app — open-core results are delayed.
- Not a **betting** tool — deterministic probabilities and optional provider odds are study context only. There is no ranked wager, expected-value comparison, bet placement, bookmaker/affiliate link, "value," staking, "locks," or bankroll advice.
- Not an **AI predictor** — the statistical engine owns every probability.
- Not a **restricted-feed redistributor** — every bundled pack has a verified open-data license and isolated attribution boundary; proprietary-feed adapters would remain bring-your-own-key and never be re-shared.

## Product principles

1. The statistical engine owns every probability.
2. Every displayed fact has a source id, or it doesn't ship.
3. Missing data is a first-class state, never silently interpolated.
4. AI explains, researches, and proposes typed facts — it never edits numbers.
5. Coincidence is not evidence, and the UI says which is which.
6. Local by default; network access is opt-in and visible.
7. No betting workflow: mathematical equivalents and outside odds/predictions stay unranked,
   attributed, opt-in, and structurally separate from Golavo forecasts.

## The words we use carefully

| Term | What it means in Golavo |
|---|---|
| **Local** | All computation runs on your machine over data already synced to disk. Staleness is always shown. |
| **Offline** | Forecasting and API reads work from the vendored snapshot; rebuilding a sourcepack requires network access. |
| **AI** | Implemented and **off by default**. Its contract permits cited narrative, never probability ownership; it cannot change or improve a number. |
| **Open** | The code is Apache-2.0; data packs declare their own license. Match-result packs are CC0-1.0, enrichment/research packs retain CC-BY attribution, and CC-BY-SA facts stay isolated. |
| **Free** | No payment to Golavo, ever. Optional third-party keys/AI are paid by you, to those providers. |
| **Live** | Golavo is not a livescore service. Core forecasts use pinned snapshots; optional outside signals are fetched only after a foreground click and show their capture time. |
