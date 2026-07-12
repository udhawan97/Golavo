---
title: Your matchday
description: The screens you'll use — Matchday, the Fixture Room, Forecast Theatre, the Commentator's Notebook, and After the Whistle.
---

Golavo is organized around the matchday. The workbench today ships the Matchday list, **Match Search** over every match in the index, the sealed **Forecast**, **After the Whistle** scoring, and the calibration **Ledger**; the richer surfaces below (dossiers, scorers/corners) are planned. Each item notes its status.

## Matchday

Your favorites first: today's and upcoming fixtures for the teams and countries you follow, each with a forecast summary and freshness stamp.

## Match Search *(shipped)*

Search **any** of the ~75,000 matches in the bundled index — internationals and the five top European leagues — by team or competition. Every match opens its own page, and **every match page carries a Commentator's Notebook**: the same deterministic, source-backed facts, computed at the **pre-kickoff horizon** (one second before kickoff), so the notebook can never read the match's own result or anything that happened later.

The page is honest about what it can and can't say:

- **Played matches show the recorded result** — but Golavo **never** shows a retro-forecast for a match that has already kicked off. A forecast is only honest if it was sealed *before* kickoff; see [how the models perform](/Golavo/methodology/prediction/) instead.
- **A match with a sealed forecast** links to it; nothing else invents one.
- **Club leagues are historical-backtest data**, so their pages never imply a live forecast. Forward sealing currently covers internationals; sealing from inside the app is a future release (today, seals are written by the engine CLI).
- Results the pinned data snapshot doesn't carry are shown as **"result not in snapshot"**, never guessed.

## Fixture Room

Everything for one match, in tabs:

- **Forecast** — the sealed forecast: a W/D/L probability bar with an uncertainty band and the exact-score matrix (with an honest tail bucket). Missing markets are shown as missing, not guessed. *Scorers and corners are planned — no accepted open source supplies them yet.*
- **Commentator's Notebook** — **shipped in Phase 7:** deterministic, cited, source-backed facts, each labelled predictive / context / coincidence and carrying its sample, base rate, source and freshness. Coincidences are capped and clearly quarantined ("for the pub, not the forecast") and are never shown to the AI. Nothing here changes a forecast. See the [Fact & Coincidence engine](/Golavo/methodology/facts/) page.
- **AI Deep Read** — optional narrative and scenario analysis, always visually subordinate to the sealed numbers. **Shipped in Phase 5, off by default;** it cites the engine's numbers and can never change one.
- **After the Whistle** — once full time arrives, the sealed forecast is scored against the actual result, with its contribution to the running calibration record.

## Team, player & manager dossiers *(planned)*

Factual profiles built from CC0 data — form, records, and history — with original artwork, never protected imagery. Not yet built; Wikidata is not a current dependency.

## Data & Model Health

Source freshness, the discrepancy queue, pack versions, and calibration status — so you can always see how current and how trustworthy the underlying data is.
