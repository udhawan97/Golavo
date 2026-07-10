---
title: Introduction
description: What Golavo is, what it is not, and the principles that keep it trustworthy.
---

Golavo is a local-first, open-source soccer match-intelligence application. It builds a probabilistic forecast for a match, **seals** it before kickoff, and **scores** it after full time — building a public calibration record of how well-calibrated it actually is.

## What Golavo is

- A **forecast ledger**: sealed pre-kickoff predictions, hash-chained and replayable.
- A **cited fact engine**: every commentator-style fact carries a source id and a base rate.
- A **local-first desktop app**: your data and keys stay on your machine.

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
| **Offline** | Everything works without network except sync, BYOK fetches, and cloud AI — and those degrade *labeled*, never silently. |
| **AI** | Optional local or cloud language models that write cited narrative. They never change a probability. |
| **Open** | The code is open source; the open-core dataset is CC0/CC-BY and redistributable. BYOK data is *not* open — it stays with you. |
| **Free** | No payment to Golavo, ever. Optional third-party keys/AI are paid by you, to those providers. |
| **Live** | Golavo is not live. Free-core results are delayed; "as of" timestamps appear everywhere. |
