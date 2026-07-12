---
title: Games & the Match Cockpit
description: The screens you'll use — the Games home, the Match Cockpit, sealing before kickoff, Leagues, the Model Lab, and the Commentator's Notebook.
---

Golavo opens on **games**, not on an audit form. The workbench is organized around four
surfaces: a Games-first home, the **Match Cockpit** for any indexed match, the **Leagues**
browse hub, and the **Model Lab** where the sealing, calibration, and evaluation machinery
lives. Every match also carries a **Commentator's Notebook**. Below is what each does today.

## Games (the home)

The landing page is football, offline, from the first launch. It shows:

- a **recent results** rail and an **upcoming fixtures** rail drawn from the local index;
- **search over every match** in the bundled index (~75,000 games — internationals and the
  five top European leagues), by team or competition;
- **league shortcuts** into the Leagues hub.

A fresh install with an empty record is still a full, useful page — the app opens on the
games, not on an empty ledger. The header carries Search, an **Aa** reading-comfort control,
and a Settings gear.

## Match Cockpit

Open **any** indexed match — past or upcoming, club or international — and Golavo computes a
leak-safe multi-model read **on demand**, at the seal's own `kickoff − 1s` cutoff. Nothing is
precomputed and nothing is stored: the cockpit is a live read, never a sealed artifact.

- **Replay** — a played match, reconstructed using only data available before kickoff. It is
  **not** a forecast that existed at the time and never enters the track record; it just shows
  what the models would have said with the pre-kickoff picture.
- **Preview** — a scheduled match, with no later data to exclude.

Either way you get:

- **Two voices** — Elo (ratings) and Dixon–Coles (goals) — shown side by side, with whether
  they **agree or disagree**. The Poisson variants are disclosed but never counted as extra
  opinions, and a **climatology baseline** is shown for reference. Nothing is averaged into a
  fake consensus — honest disagreement is the point.
- **Model-implied goals** (labelled *expected, not predicted*) and the goal model's coherent
  **exact-score grid**.
- An honest **abstain** state when either side has too little history to model.

The cockpit is machine-checked leak-safe: the cutoff proof rejects any training row dated at or
after `kickoff − 1s`.

## Seal before kickoff

The cockpit is the live read; **sealing** is how you put a genuine pre-kickoff prediction on the
record — from inside the app, no CLI required. For an **eligible** fixture (men's senior full
internationals, still scheduled, inside the seal window) the cockpit shows a **Seal before
kickoff** action; it runs the same deterministic engine as the CLI (byte-identical), freezes the
model version, seed, parameters, cutoff, and inputs, and writes an immutable `ForecastArtifact`.

The action is honest about scope. A fixture that can't be sealed shows a reason-specific message
— already played, seal window closed, internationals-only, or pack unavailable — rather than a
dead button. After full time, the seal is **scored** against the actual result as a separate
successor; the original seal's bytes never change. Golavo **never** shows a retro-forecast for a
match that already kicked off — a forecast is only honest if it was sealed *before* kickoff.

> The vendored packs are historical, so the upcoming rail and the seal window depend on the
> snapshot's freshness. There is no user-facing data-refresh control yet.

## Leagues

A browse hub for the five bundled club leagues and internationals. The club leagues are a
**historical backtesting** surface, not live club forecasting — their pages never imply a live
forecast. Forward sealing covers internationals only, because that is the single source that maps
to a pinned CC0 pack.

## Model Lab

The sealing, provenance, calibration, and evaluation machinery moved here, behind the product:

- **Track record** — the real forward calibration record, recomputed over genuine
  sealed → scored chains. It starts small because history is not available on back-order.
- **Backtests** — held-out chronological fold metrics (log loss, Brier, ECE, RPS) and reliability
  diagrams, kept strictly separate from the forward record.
- **Methodologies** — why three of the five model families are really one voice, and how
  abstention works.
- **Sealed forecasts** — the immutable forecast list.

Old `#/ledger` and `#/eval` links redirect into the Lab, so existing bookmarks keep working.

## Commentator's Notebook

Every match page carries the Notebook: deterministic, source-backed facts computed at the same
`kickoff − 1s` horizon, so it can never read the match's own result or anything later. Facts are
labelled **predictive / context / coincidence**, each with its sample, base rate, source, and
freshness. Coincidences are capped and quarantined ("for the pub, not the forecast") and are
never shown to the AI. Nothing here changes a forecast — the fact package has a machine-checked
rule that forbids it from importing any forecast, model, or calibration writer.

Since v0.3.1 the Notebook also surfaces **signature form stats** most scoreboards never show —
both-teams-scored rate, scoring momentum, clean-sheet rate, and the goal character of the
head-to-head — and it is **de-duplicated** from the "three things to know" insight cards, so the
Notebook is the deeper cut rather than a repeat. See the
[Fact & Coincidence engine](/Golavo/methodology/facts/) page.

## AI Analyst Read *(optional, off by default)*

An optional narrative and scenario synthesis, always subordinate to the deterministic numbers.
It reads and connects the match's notes and model council (and sealed forecasts), cites only the
engine's numbers, and can never change one — a single unsupported figure benches the whole
answer. It runs locally (Ollama / llama.cpp) or via BYOK cloud, and is enabled from
Settings → Local intelligence. See [AI providers](/Golavo/ai/providers/).
